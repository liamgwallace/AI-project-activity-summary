"""Neo4j graph database operations for the Personal Activity Intelligence System.

Manages a knowledge graph of projects, activities, technologies, web pages,
commits, files, and calendar events with rich relationships between them.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from config import settings

logger = logging.getLogger("storage.graph")


class GraphManager:
    """Manages all Neo4j graph database operations for the activity intelligence
    knowledge graph.

    Stores entities such as projects, activities, technologies, web pages,
    commits, files, and calendar events, and links them via typed relationships
    like BELONGS_TO, USES, REFERENCES, PART_OF, IN_PROJECT, and RELATED_TO.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Initialize the Neo4j graph manager.

        Args:
            uri: Neo4j bolt URI. Falls back to config.settings.NEO4J_URI.
            user: Neo4j username. Falls back to config.settings.NEO4J_USER.
            password: Neo4j password. Falls back to config.settings.NEO4J_PASSWORD.
        """
        self._uri = uri or settings.NEO4J_URI
        self._user = user or settings.NEO4J_USER
        self._password = password or settings.NEO4J_PASSWORD

        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        logger.info("GraphManager connected to %s", self._uri)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the Neo4j driver and release all resources."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j driver closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def initialize_db(self) -> None:
        """Create indexes and uniqueness constraints for all node types.

        Idempotent -- safe to call multiple times.
        """
        logger.info("Initializing Neo4j indexes and constraints")

        constraints = [
            ("project_name_unique", "Project", "name"),
            ("technology_name_unique", "Technology", "name"),
            ("webpage_url_unique", "WebPage", "url"),
            ("commit_hash_unique", "Commit", "hash"),
        ]

        indexes = [
            ("activity_timestamp_idx", "Activity", "timestamp"),
            ("file_path_idx", "File", "path"),
            ("calendar_start_idx", "CalendarEvent", "start"),
        ]

        with self._driver.session() as session:
            for constraint_name, label, prop in constraints:
                try:
                    session.run(
                        f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                    logger.debug(
                        "Ensured constraint %s on %s.%s",
                        constraint_name,
                        label,
                        prop,
                    )
                except Neo4jError as exc:
                    logger.warning(
                        "Could not create constraint %s: %s",
                        constraint_name,
                        exc,
                    )

            for index_name, label, prop in indexes:
                try:
                    session.run(
                        f"CREATE INDEX {index_name} IF NOT EXISTS "
                        f"FOR (n:{label}) ON (n.{prop})"
                    )
                    logger.debug(
                        "Ensured index %s on %s.%s", index_name, label, prop
                    )
                except Neo4jError as exc:
                    logger.warning(
                        "Could not create index %s: %s", index_name, exc
                    )

        logger.info("Neo4j schema initialization complete")

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    def create_or_update_project(
        self,
        name: str,
        path: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Any]:
        """Create a Project node or update it if it already exists.

        Args:
            name: Unique project name.
            path: Filesystem path of the project.
            status: Current status (e.g. 'active', 'archived').

        Returns:
            A dict of the Project node properties.
        """
        now = datetime.utcnow().isoformat()

        query = """
            MERGE (p:Project {name: $name})
            ON CREATE SET
                p.path = $path,
                p.status = $status,
                p.created_at = $now,
                p.last_activity = $now
            ON MATCH SET
                p.path = COALESCE($path, p.path),
                p.status = $status,
                p.last_activity = $now
            RETURN p
        """

        with self._driver.session() as session:
            result = session.run(
                query, name=name, path=path, status=status, now=now
            )
            record = result.single()

        node_props = dict(record["p"]) if record else {}
        logger.info("Created/updated Project '%s'", name)
        return node_props

    def update_project_activity(
        self, project_name: str, timestamp: str
    ) -> None:
        """Update the last_activity timestamp on a project.

        Args:
            project_name: Name of the project to update.
            timestamp: ISO-format datetime string.
        """
        query = """
            MATCH (p:Project {name: $name})
            SET p.last_activity = $timestamp
        """

        with self._driver.session() as session:
            session.run(query, name=project_name, timestamp=timestamp)

        logger.debug("Updated activity for Project '%s' to %s", project_name, timestamp)

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Return all projects with status 'active'.

        Returns:
            A list of Project node property dicts.
        """
        query = "MATCH (p:Project {status: 'active'}) RETURN p ORDER BY p.last_activity DESC"

        with self._driver.session() as session:
            result = session.run(query)
            projects = [dict(record["p"]) for record in result]

        logger.debug("Retrieved %d active projects", len(projects))
        return projects

    def get_related_projects(self, project_name: str) -> List[Dict[str, Any]]:
        """Find projects related to the given project via shared technologies
        or explicit RELATED_TO relationships.

        Args:
            project_name: The reference project name.

        Returns:
            A list of related Project node property dicts.
        """
        query = """
            MATCH (p:Project {name: $name})-[:USES]->(t:Technology)<-[:USES]-(other:Project)
            WHERE other.name <> $name
            RETURN DISTINCT other AS p
            UNION
            MATCH (p1:Project {name: $name})-[:RELATED_TO]-(other:Project)
            WHERE other.name <> $name
            RETURN DISTINCT other AS p
        """

        with self._driver.session() as session:
            result = session.run(query, name=project_name)
            projects = [dict(record["p"]) for record in result]

        logger.debug(
            "Found %d projects related to '%s'", len(projects), project_name
        )
        return projects

    # ------------------------------------------------------------------
    # Activity operations
    # ------------------------------------------------------------------

    def create_activity(
        self,
        type: str,
        timestamp: str,
        description: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an Activity node and optionally link it to a project.

        Args:
            type: Activity type (e.g. 'coding', 'research', 'meeting').
            timestamp: ISO-format datetime string.
            description: Human-readable description of the activity.
            project_name: If provided, creates a BELONGS_TO relationship.

        Returns:
            A dict of the Activity node properties.
        """
        query = """
            CREATE (a:Activity {
                type: $type,
                timestamp: $timestamp,
                description: $description
            })
            RETURN a
        """

        with self._driver.session() as session:
            result = session.run(
                query, type=type, timestamp=timestamp, description=description
            )
            record = result.single()
            node_props = dict(record["a"]) if record else {}

            if project_name:
                session.run(
                    """
                    MATCH (a:Activity {timestamp: $timestamp, description: $description})
                    MATCH (p:Project {name: $project_name})
                    MERGE (a)-[:BELONGS_TO]->(p)
                    """,
                    timestamp=timestamp,
                    description=description,
                    project_name=project_name,
                )
                logger.debug("Linked Activity to Project '%s'", project_name)

        logger.info("Created Activity: type=%s, project=%s", type, project_name)
        return node_props

    # ------------------------------------------------------------------
    # Technology operations
    # ------------------------------------------------------------------

    def add_technology(
        self, name: str, project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Technology node and optionally link it to a project.

        Args:
            name: Technology name (e.g. 'Python', 'React').
            project_name: If provided, creates a USES relationship from the
                          project to the technology.

        Returns:
            A dict of the Technology node properties.
        """
        query = """
            MERGE (t:Technology {name: $name})
            RETURN t
        """

        with self._driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            node_props = dict(record["t"]) if record else {}

            if project_name:
                session.run(
                    """
                    MATCH (p:Project {name: $project_name})
                    MATCH (t:Technology {name: $tech_name})
                    MERGE (p)-[:USES]->(t)
                    """,
                    project_name=project_name,
                    tech_name=name,
                )
                logger.debug(
                    "Linked Technology '%s' to Project '%s'", name, project_name
                )

        logger.info("Added Technology '%s'", name)
        return node_props

    def link_technology_to_project(
        self, tech_name: str, project_name: str
    ) -> None:
        """Create a USES relationship between a project and a technology.

        Both nodes must already exist.

        Args:
            tech_name: The technology name.
            project_name: The project name.
        """
        query = """
            MATCH (p:Project {name: $project_name})
            MATCH (t:Technology {name: $tech_name})
            MERGE (p)-[:USES]->(t)
        """

        with self._driver.session() as session:
            session.run(query, project_name=project_name, tech_name=tech_name)

        logger.info(
            "Linked Technology '%s' -> Project '%s'", tech_name, project_name
        )

    def get_project_technologies(self, project_name: str) -> List[str]:
        """List all technologies used by a project.

        Args:
            project_name: The project to query.

        Returns:
            A list of technology name strings.
        """
        query = """
            MATCH (p:Project {name: $name})-[:USES]->(t:Technology)
            RETURN t.name AS name ORDER BY t.name
        """

        with self._driver.session() as session:
            result = session.run(query, name=project_name)
            techs = [record["name"] for record in result]

        logger.debug(
            "Project '%s' uses %d technologies", project_name, len(techs)
        )
        return techs

    def get_known_technologies(self) -> List[str]:
        """Return the names of all Technology nodes in the graph.

        Returns:
            A sorted list of technology name strings.
        """
        query = "MATCH (t:Technology) RETURN t.name AS name ORDER BY t.name"

        with self._driver.session() as session:
            result = session.run(query)
            techs = [record["name"] for record in result]

        logger.debug("Known technologies: %d", len(techs))
        return techs

    # ------------------------------------------------------------------
    # Web page operations
    # ------------------------------------------------------------------

    def create_webpage(
        self, url: str, title: str, summary: str
    ) -> Dict[str, Any]:
        """Create or update a WebPage node.

        Args:
            url: The page URL (unique).
            title: Page title.
            summary: AI-generated summary of the page content.

        Returns:
            A dict of the WebPage node properties.
        """
        query = """
            MERGE (w:WebPage {url: $url})
            SET w.title = $title,
                w.summary = $summary
            RETURN w
        """

        with self._driver.session() as session:
            result = session.run(query, url=url, title=title, summary=summary)
            record = result.single()

        node_props = dict(record["w"]) if record else {}
        logger.info("Created/updated WebPage: %s", url)
        return node_props

    # ------------------------------------------------------------------
    # Commit operations
    # ------------------------------------------------------------------

    def create_commit(
        self,
        message: str,
        repo: str,
        hash: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Commit node and optionally link it to a project.

        Args:
            message: The commit message.
            repo: Repository name or path.
            hash: Unique commit hash.
            project_name: If provided, creates a PART_OF relationship.

        Returns:
            A dict of the Commit node properties.
        """
        query = """
            MERGE (c:Commit {hash: $hash})
            SET c.message = $message,
                c.repo = $repo
            RETURN c
        """

        with self._driver.session() as session:
            result = session.run(query, hash=hash, message=message, repo=repo)
            record = result.single()
            node_props = dict(record["c"]) if record else {}

            if project_name:
                session.run(
                    """
                    MATCH (c:Commit {hash: $hash})
                    MATCH (p:Project {name: $project_name})
                    MERGE (c)-[:PART_OF]->(p)
                    """,
                    hash=hash,
                    project_name=project_name,
                )
                logger.debug("Linked Commit %s to Project '%s'", hash[:8], project_name)

        logger.info("Created Commit %s in repo '%s'", hash[:8], repo)
        return node_props

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def create_file(
        self,
        path: str,
        project_path: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a File node and optionally link it to a project.

        Args:
            path: Full file path.
            project_path: Root path of the project the file belongs to.
            project_name: If provided, creates an IN_PROJECT relationship.

        Returns:
            A dict of the File node properties.
        """
        query = """
            MERGE (f:File {path: $path})
            SET f.project_path = $project_path
            RETURN f
        """

        with self._driver.session() as session:
            result = session.run(query, path=path, project_path=project_path)
            record = result.single()
            node_props = dict(record["f"]) if record else {}

            if project_name:
                session.run(
                    """
                    MATCH (f:File {path: $path})
                    MATCH (p:Project {name: $project_name})
                    MERGE (f)-[:IN_PROJECT]->(p)
                    """,
                    path=path,
                    project_name=project_name,
                )

        logger.debug("Created File node: %s", path)
        return node_props

    # ------------------------------------------------------------------
    # Calendar event operations
    # ------------------------------------------------------------------

    def create_calendar_event(
        self,
        title: str,
        start: str,
        end: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a CalendarEvent node and optionally link it to a project.

        Args:
            title: Event title.
            start: ISO-format start datetime.
            end: ISO-format end datetime.
            project_name: If provided, creates a REFERENCES relationship.

        Returns:
            A dict of the CalendarEvent node properties.
        """
        query = """
            CREATE (ce:CalendarEvent {
                title: $title,
                start: $start,
                end: $end
            })
            RETURN ce
        """

        with self._driver.session() as session:
            result = session.run(query, title=title, start=start, end=end)
            record = result.single()
            node_props = dict(record["ce"]) if record else {}

            if project_name:
                session.run(
                    """
                    MATCH (ce:CalendarEvent {title: $title, start: $start})
                    MATCH (p:Project {name: $project_name})
                    MERGE (ce)-[:REFERENCES]->(p)
                    """,
                    title=title,
                    start=start,
                    project_name=project_name,
                )
                logger.debug(
                    "Linked CalendarEvent '%s' to Project '%s'",
                    title,
                    project_name,
                )

        logger.info("Created CalendarEvent: '%s' (%s)", title, start)
        return node_props

    # ------------------------------------------------------------------
    # Aliases for processor compatibility
    # ------------------------------------------------------------------

    def create_project(self, name: str, **kwargs) -> Dict[str, Any]:
        """Alias for create_or_update_project."""
        return self.create_or_update_project(name=name, **kwargs)

    def update_project(self, name: str, **kwargs) -> None:
        """Alias for update_project_activity."""
        self.update_project_activity(project_name=name, **kwargs)

    def get_technologies(self) -> List[str]:
        """Alias for get_known_technologies."""
        return self.get_known_technologies()
