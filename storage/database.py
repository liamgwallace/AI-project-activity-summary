"""
SQLite database operations for the Personal Activity Intelligence System.
Handles all CRUD operations and table management.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RawEvent:
    id: Optional[int] = None
    source: str = ""
    event_type: str = ""
    raw_data: str = ""
    event_time: str = ""
    processed: bool = False
    created_at: Optional[str] = None


@dataclass
class ProcessingBatch:
    id: Optional[int] = None
    start_time: str = ""
    end_time: Optional[str] = None
    total_events: int = 0
    processed_count: int = 0
    status: str = "running"
    error_message: Optional[str] = None
    model_used: str = ""
    tokens_used: int = 0


@dataclass
class Activity:
    id: Optional[int] = None
    timestamp: str = ""
    project_name: str = ""
    activity_type: str = ""
    description: str = ""
    source_refs: str = ""
    tweet_draft_id: Optional[int] = None
    raw_event_ids: str = ""
    embedding: Optional[bytes] = None
    created_at: Optional[str] = None


@dataclass
class TweetDraft:
    id: Optional[int] = None
    content: str = ""
    project_name: str = ""
    activity_ids: str = ""
    timestamp: str = ""
    generated_at: str = ""
    posted: bool = False
    posted_at: Optional[str] = None
    engagement_stats: str = "{}"


@dataclass
class Entity:
    id: Optional[int] = None
    entity_type: str = ""
    name: str = ""
    display_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    mention_count: int = 0


@dataclass
class Relationship:
    id: Optional[int] = None
    from_type: str = ""
    from_id: int = 0
    to_type: str = ""
    to_id: int = 0
    rel_type: str = ""
    confidence: float = 1.0
    created_at: Optional[str] = None


class Database:
    """SQLite database manager with all required operations."""
    
    def __init__(self, db_path: str = "data/activity_system.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self) -> None:
        """Create all required database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Raw events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                raw_data TEXT NOT NULL,
                event_time TEXT NOT NULL,
                processed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Processing batches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                total_events INTEGER DEFAULT 0,
                processed_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error_message TEXT,
                model_used TEXT,
                tokens_used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Activities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT NOT NULL,
                source_refs TEXT,
                tweet_draft_id INTEGER,
                raw_event_ids TEXT,
                embedding BLOB,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tweet_draft_id) REFERENCES tweet_drafts(id)
            )
        """)
        
        # Tweet drafts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tweet_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                project_name TEXT NOT NULL,
                activity_ids TEXT,
                timestamp TEXT NOT NULL,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                posted INTEGER DEFAULT 0,
                posted_at TEXT,
                engagement_stats TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                keywords TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Token usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                operation TEXT NOT NULL,
                model TEXT NOT NULL,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                cost_estimate REAL DEFAULT 0.0
            )
        """)
        
        # Entities table for graph system
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                display_name TEXT,
                metadata TEXT DEFAULT '{}',
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                mention_count INTEGER DEFAULT 1,
                UNIQUE(entity_type, name)
            )
        """)
        
        # Relationships table for graph system
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_type TEXT NOT NULL,
                from_id INTEGER NOT NULL,
                to_type TEXT NOT NULL,
                to_id INTEGER NOT NULL,
                rel_type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_type, from_id, to_type, to_id, rel_type)
            )
        """)
        
        # Entity aliases table for name variations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                alias TEXT UNIQUE NOT NULL,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_events_processed 
            ON raw_events(processed)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_events_time 
            ON raw_events(event_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activities_project 
            ON activities(project_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activities_time 
            ON activities(timestamp)
        """)
        
        # Indexes for graph tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_type 
            ON entities(entity_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_name 
            ON entities(name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_from 
            ON relationships(from_type, from_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_to 
            ON relationships(to_type, to_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_type 
            ON relationships(rel_type)
        """)
        
        conn.commit()
        conn.close()

    # Graph system methods

    def _normalize_entity_name(self, name: str) -> str:
        """Normalize entity name: lowercase and replace spaces with hyphens."""
        return name.lower().strip().replace(" ", "-")

    def get_or_create_entity(
        self,
        name: str,
        entity_type: str,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Get existing or create new entity. Updates last_seen and mention_count if exists.
        
        Args:
            name: Entity name (will be normalized).
            entity_type: Type of entity (e.g., 'person', 'project', 'technology').
            display_name: Optional display name (uses normalized name if not provided).
            metadata: Optional dictionary of metadata.
            
        Returns:
            Entity ID.
        """
        normalized_name = self._normalize_entity_name(name)
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Try to get existing entity
            cursor.execute(
                "SELECT id, mention_count FROM entities WHERE entity_type = ? AND name = ?",
                (entity_type, normalized_name),
            )
            row = cursor.fetchone()
            
            if row:
                entity_id = row["id"]
                new_count = row["mention_count"] + 1
                
                # Update existing entity
                cursor.execute(
                    "UPDATE entities SET last_seen = ?, mention_count = ? WHERE id = ?",
                    (now, new_count, entity_id),
                )
                conn.commit()
                return entity_id
            
            # Create new entity
            metadata_json = json.dumps(metadata) if metadata else "{}"
            cursor.execute(
                """
                INSERT INTO entities (entity_type, name, display_name, metadata, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entity_type, normalized_name, display_name or name, metadata_json, now, now),
            )
            
            entity_id = cursor.lastrowid
            conn.commit()
            return entity_id if entity_id is not None else 0

    def create_relationship(
        self,
        from_type: str,
        from_id: int,
        to_type: str,
        to_id: int,
        rel_type: str,
        confidence: float = 1.0,
    ) -> int:
        """Create a relationship between two entities with unique constraint.
        
        Args:
            from_type: Type of the source entity.
            from_id: ID of the source entity.
            to_type: Type of the target entity.
            to_id: ID of the target entity.
            rel_type: Type of relationship.
            confidence: Confidence score (0.0 to 1.0).
            
        Returns:
            Relationship ID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR IGNORE INTO relationships (from_type, from_id, to_type, to_id, rel_type, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (from_type, from_id, to_type, to_id, rel_type, confidence),
            )
            
            conn.commit()
            
            # If insert was ignored due to conflict, get existing ID
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    SELECT id FROM relationships
                    WHERE from_type = ? AND from_id = ? AND to_type = ? AND to_id = ? AND rel_type = ?
                    """,
                    (from_type, from_id, to_type, to_id, rel_type),
                )
                row = cursor.fetchone()
                return row["id"] if row else 0
            
            return cursor.lastrowid if cursor.lastrowid is not None else 0

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Get entity by normalized name.
        
        Args:
            name: Entity name to search for (will be normalized).
            
        Returns:
            Entity if found, None otherwise.
        """
        normalized_name = self._normalize_entity_name(name)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, entity_type, name, display_name, metadata, first_seen, last_seen, mention_count FROM entities WHERE name = ?",
                (normalized_name,),
            )
            row = cursor.fetchone()
            
            if row:
                return Entity(
                    id=row["id"],
                    entity_type=row["entity_type"],
                    name=row["name"],
                    display_name=row["display_name"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    mention_count=row["mention_count"],
                )
            
            return None

    def get_related_entities(
        self,
        entity_id: int,
        rel_type: Optional[str] = None,
    ) -> List[Entity]:
        """Get entities related to the given entity.
        
        Args:
            entity_id: ID of the entity to find relations for.
            rel_type: Optional relationship type filter.
            
        Returns:
            List of related entities.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if rel_type:
                cursor.execute(
                    """
                    SELECT e.id, e.entity_type, e.name, e.display_name, e.metadata, e.first_seen, e.last_seen, e.mention_count
                    FROM entities e
                    JOIN relationships r ON (e.id = r.to_id OR e.id = r.from_id)
                    WHERE (r.from_id = ? OR r.to_id = ?) AND r.rel_type = ? AND e.id != ?
                    """,
                    (entity_id, entity_id, rel_type, entity_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT e.id, e.entity_type, e.name, e.display_name, e.metadata, e.first_seen, e.last_seen, e.mention_count
                    FROM entities e
                    JOIN relationships r ON (e.id = r.to_id OR e.id = r.from_id)
                    WHERE (r.from_id = ? OR r.to_id = ?) AND e.id != ?
                    """,
                    (entity_id, entity_id, entity_id),
                )
            
            rows = cursor.fetchall()
            
            return [
                Entity(
                    id=row["id"],
                    entity_type=row["entity_type"],
                    name=row["name"],
                    display_name=row["display_name"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    mention_count=row["mention_count"],
                )
                for row in rows
            ]

    def get_project_entities(
        self,
        project_name: str,
        days: int = 30,
    ) -> List[Entity]:
        """Get all entities used by a project in the last N days.
        
        Args:
            project_name: Name of the project.
            days: Number of days to look back.
            
        Returns:
            List of entities associated with the project.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT DISTINCT e.id, e.entity_type, e.name, e.display_name, e.metadata, e.first_seen, e.last_seen, e.mention_count
                FROM entities e
                JOIN relationships r ON (e.id = r.to_id OR e.id = r.from_id)
                JOIN entities proj ON (proj.id = r.from_id OR proj.id = r.to_id)
                WHERE proj.entity_type = 'project' AND proj.name = ? AND e.last_seen >= ?
                """,
                (self._normalize_entity_name(project_name), since),
            )
            
            rows = cursor.fetchall()
            
            return [
                Entity(
                    id=row["id"],
                    entity_type=row["entity_type"],
                    name=row["name"],
                    display_name=row["display_name"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    mention_count=row["mention_count"],
                )
                for row in rows
            ]

    def get_recent_entities(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> List[Entity]:
        """Get recently mentioned entities.
        
        Args:
            days: Number of days to look back.
            limit: Maximum number of entities to return.
            
        Returns:
            List of recently mentioned entities.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, entity_type, name, display_name, metadata, first_seen, last_seen, mention_count
                FROM entities
                WHERE last_seen >= ?
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                (since, limit),
            )
            
            rows = cursor.fetchall()
            
            return [
                Entity(
                    id=row["id"],
                    entity_type=row["entity_type"],
                    name=row["name"],
                    display_name=row["display_name"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    mention_count=row["mention_count"],
                )
                for row in rows
            ]

    def get_recent_relationships(
        self,
        days: int = 30,
        limit: int = 30,
    ) -> List[Relationship]:
        """Get recent relationships.
        
        Args:
            days: Number of days to look back.
            limit: Maximum number of relationships to return.
            
        Returns:
            List of recent relationships.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, from_type, from_id, to_type, to_id, rel_type, confidence, created_at
                FROM relationships
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (since, limit),
            )
            
            rows = cursor.fetchall()
            
            return [
                Relationship(
                    id=row["id"],
                    from_type=row["from_type"],
                    from_id=row["from_id"],
                    to_type=row["to_type"],
                    to_id=row["to_id"],
                    rel_type=row["rel_type"],
                    confidence=row["confidence"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def insert_event(self, source: str, event_type: str, raw_data: str, event_time: str) -> int:
        """Insert a single raw event. Returns the event ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO raw_events (source, event_type, raw_data, event_time)
            VALUES (?, ?, ?, ?)
        """, (source, event_type, raw_data, event_time))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id if event_id is not None else 0
    
    def insert_events(self, events: List[Tuple[str, str, str, str]]) -> int:
        """Insert multiple raw events. Returns number of events inserted."""
        if not events:
            return 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO raw_events (source, event_type, raw_data, event_time)
            VALUES (?, ?, ?, ?)
        """, events)
        
        inserted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return inserted
    
    def get_unprocessed_events(self, limit: int = 100) -> List[RawEvent]:
        """Get unprocessed events for batch processing."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, source, event_type, raw_data, event_time, processed, created_at
            FROM raw_events
            WHERE processed = 0
            ORDER BY event_time ASC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            RawEvent(
                id=row["id"],
                source=row["source"],
                event_type=row["event_type"],
                raw_data=row["raw_data"],
                event_time=row["event_time"],
                processed=bool(row["processed"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
    
    def get_events_since(self, since: datetime) -> List[RawEvent]:
        """Get all events since a specific datetime."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since_str = since.isoformat()
        
        cursor.execute("""
            SELECT id, source, event_type, raw_data, event_time, processed, created_at
            FROM raw_events
            WHERE event_time >= ?
            ORDER BY event_time DESC
        """, (since_str,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            RawEvent(
                id=row["id"],
                source=row["source"],
                event_type=row["event_type"],
                raw_data=row["raw_data"],
                event_time=row["event_time"],
                processed=bool(row["processed"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
    
    def mark_events_processed(self, event_ids: List[int]) -> int:
        """Mark events as processed. Returns number of events updated."""
        if not event_ids:
            return 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ",".join(["?"] * len(event_ids))
        cursor.execute(f"""
            UPDATE raw_events
            SET processed = 1
            WHERE id IN ({placeholders})
        """, event_ids)
        
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        return updated
    
    def create_batch(self, total_events: int, model_used: str) -> int:
        """Create a new processing batch and return batch ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        start_time = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO processing_batches (start_time, total_events, model_used)
            VALUES (?, ?, ?)
        """, (start_time, total_events, model_used))
        
        batch_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return batch_id if batch_id is not None else 0
    
    def complete_batch(self, batch_id: int, processed_count: int, tokens_used: int) -> None:
        """Mark a batch as completed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        end_time = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE processing_batches
            SET end_time = ?,
                processed_count = ?,
                status = 'completed',
                tokens_used = ?
            WHERE id = ?
        """, (end_time, processed_count, tokens_used, batch_id))
        
        conn.commit()
        conn.close()
    
    def fail_batch(self, batch_id: int, error_message: str) -> None:
        """Mark a batch as failed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        end_time = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE processing_batches
            SET end_time = ?,
                status = 'failed',
                error_message = ?
            WHERE id = ?
        """, (end_time, error_message, batch_id))
        
        conn.commit()
        conn.close()
    
    def insert_activity(
        self,
        timestamp: str,
        project_name: str,
        activity_type: str,
        description: str,
        source_refs: str = "",
        raw_event_ids: str = "",
        embedding: Optional[bytes] = None,
    ) -> int:
        """Insert an activity record and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO activities 
            (timestamp, project_name, activity_type, description, source_refs, raw_event_ids, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, project_name, activity_type, description, source_refs, raw_event_ids, embedding))
        
        activity_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return activity_id if activity_id is not None else 0
    
    def get_activities_for_period(
        self,
        start: datetime,
        end: datetime,
        project_name: Optional[str] = None,
    ) -> List[Activity]:
        """Get activities within a time period, optionally filtered by project."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        start_str = start.isoformat()
        end_str = end.isoformat()
        
        if project_name:
            cursor.execute("""
                SELECT id, timestamp, project_name, activity_type, description, 
                       source_refs, tweet_draft_id, raw_event_ids, embedding, created_at
                FROM activities
                WHERE timestamp >= ? AND timestamp <= ? AND project_name = ?
                ORDER BY timestamp DESC
            """, (start_str, end_str, project_name))
        else:
            cursor.execute("""
                SELECT id, timestamp, project_name, activity_type, description, 
                       source_refs, tweet_draft_id, raw_event_ids, embedding, created_at
                FROM activities
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """, (start_str, end_str))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Activity(
                id=row["id"],
                timestamp=row["timestamp"],
                project_name=row["project_name"],
                activity_type=row["activity_type"],
                description=row["description"],
                source_refs=row["source_refs"],
                tweet_draft_id=row["tweet_draft_id"],
                raw_event_ids=row["raw_event_ids"],
                embedding=row["embedding"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    
    def get_or_create_project(self, name: str, description: str = "", keywords: str = "") -> Tuple[int, bool]:
        """
        Get project ID or create if not exists.
        Returns tuple of (project_id, created_new).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Try to get existing
        cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        
        if row:
            conn.close()
            return row["id"], False
        
        # Create new
        cursor.execute("""
            INSERT INTO projects (name, description, keywords)
            VALUES (?, ?, ?)
        """, (name, description, keywords))
        
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return (project_id if project_id is not None else 0), True
    
    def insert_tweet_draft(
        self,
        content: str,
        project_name: str,
        activity_ids: str,
        timestamp: str,
    ) -> int:
        """Insert a tweet draft and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        generated_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO tweet_drafts (content, project_name, activity_ids, timestamp, generated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (content, project_name, activity_ids, timestamp, generated_at))
        
        draft_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return draft_id if draft_id is not None else 0
    
    def get_token_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get token usage statistics for the specified period."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_operations,
                SUM(tokens_input) as total_input,
                SUM(tokens_output) as total_output,
                SUM(tokens_input + tokens_output) as total_tokens,
                SUM(cost_estimate) as total_cost,
                model
            FROM token_usage
            WHERE timestamp >= ?
            GROUP BY model
        """, (since,))
        
        rows = cursor.fetchall()
        
        stats = {
            "period_days": days,
            "total_operations": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "by_model": {},
        }
        
        for row in rows:
            model = row["model"]
            stats["by_model"][model] = {
                "operations": row["total_operations"],
                "input_tokens": row["total_input"],
                "output_tokens": row["total_output"],
                "total_tokens": row["total_tokens"],
                "cost": row["total_cost"],
            }
            stats["total_operations"] += row["total_operations"]
            stats["total_input_tokens"] += row["total_input"]
            stats["total_output_tokens"] += row["total_output"]
            stats["total_tokens"] += row["total_tokens"]
            stats["total_cost"] += row["total_cost"]
        
        # Get batch statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_batches,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_batches,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_batches,
                SUM(tokens_used) as total_batch_tokens
            FROM processing_batches
            WHERE start_time >= ?
        """, (since,))
        
        batch_row = cursor.fetchone()
        stats["batches"] = {
            "total": batch_row["total_batches"],
            "completed": batch_row["completed_batches"],
            "failed": batch_row["failed_batches"],
            "total_tokens": batch_row["total_batch_tokens"],
        }
        
        conn.close()
        
        return stats
    
    def record_token_usage(
        self,
        operation: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost_estimate: float,
    ) -> None:
        """Record token usage for tracking."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO token_usage (operation, model, tokens_input, tokens_output, cost_estimate)
            VALUES (?, ?, ?, ?, ?)
        """, (operation, model, tokens_input, tokens_output, cost_estimate))
        
        conn.commit()
        conn.close()
