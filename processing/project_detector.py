"""
Project detection and management logic.

Implements conservative project creation rules and similarity detection
to avoid creating duplicate or unnecessary projects.
"""

import re
import logging
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict
from difflib import SequenceMatcher

from storage.database import Database, Activity
from config.settings import get_settings, Project

logger = logging.getLogger(__name__)


class ProjectDetector:
    """
    Detects when new projects should be created and manages project merging.
    
    Implements the "3+ activities across multiple days" rule for
    conservative project creation.
    """
    
    # Minimum similarity threshold for merging projects
    SIMILARITY_THRESHOLD = 0.75
    
    def __init__(self, db: Database):
        """
        Initialize the project detector.
        
        Args:
            db: Database instance for activity queries
        """
        self.db = db
        self.settings = get_settings()
    
    def should_create_project(
        self,
        project_name: str,
        activities: List[Dict[str, Any]],
    ) -> bool:
        """
        Determine if a project should be created based on the
        "3+ activities across multiple days" rule.
        
        Args:
            project_name: Name of the potential project
            activities: List of activities associated with this project
            
        Returns:
            True if project should be created, False otherwise
        """
        # Rule 1: Must have at least 3 activities
        if len(activities) < 3:
            logger.debug(
                f"Project '{project_name}' rejected: only {len(activities)} activities "
                f"(minimum 3 required)"
            )
            return False
        
        # Rule 2: Activities must span multiple days
        dates = set()
        for activity in activities:
            date_str = activity.get("date", "")
            if date_str:
                # Extract date portion (YYYY-MM-DD)
                date = date_str[:10]
                dates.add(date)
        
        if len(dates) < 2:
            logger.debug(
                f"Project '{project_name}' rejected: activities only on "
                f"{len(dates)} day(s) (minimum 2 required)"
            )
            return False
        
        # Rule 3: Check if similar project already exists
        existing_projects = list(self.settings.projects.keys())
        for existing in existing_projects:
            if self._similarity(project_name, existing) >= self.SIMILARITY_THRESHOLD:
                logger.info(
                    f"Project '{project_name}' rejected: too similar to existing "
                    f"'{existing}'"
                )
                return False
        
        logger.info(
            f"Project '{project_name}' approved: {len(activities)} activities across "
            f"{len(dates)} days"
        )
        return True
    
    def merge_similar_projects(
        self,
        projects: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group similar project names together and map to canonical names.
        
        Args:
            projects: List of project dictionaries with 'name' field
            
        Returns:
            Dictionary mapping canonical names to lists of similar projects
        """
        if not projects:
            return {}
        
        # Sort by name to have consistent canonical naming
        sorted_projects = sorted(projects, key=lambda p: p.get("name", "").lower())
        
        merged = defaultdict(list)
        canonical_map = {}
        
        for project in sorted_projects:
            name = project.get("name", "")
            if not name:
                continue
            
            # Normalize name for comparison
            normalized = self._normalize_name(name)
            
            # Check against existing canonical names
            matched = False
            for canonical, canonical_norm in canonical_map.items():
                similarity = self._similarity(normalized, canonical_norm)
                if similarity >= self.SIMILARITY_THRESHOLD:
                    merged[canonical].append(project)
                    matched = True
                    break
            
            if not matched:
                # This is a new canonical name
                merged[name].append(project)
                canonical_map[name] = normalized
        
        logger.debug(
            f"Merged {len(projects)} projects into {len(merged)} canonical groups"
        )
        return dict(merged)
    
    def get_project_keywords(
        self,
        project_name: str,
        activities: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Extract keywords from project activities.
        
        Analyzes technologies, descriptions, and project name to build
        a comprehensive keyword list for project matching.
        
        Args:
            project_name: Name of the project
            activities: List of activity dictionaries
            
        Returns:
            List of keywords
        """
        keywords = set()
        
        # Add words from project name
        name_words = re.findall(r'\b[a-zA-Z]+\b', project_name.lower())
        keywords.update(name_words)
        
        # Extract from activities
        all_technologies = []
        all_descriptions = []
        
        for activity in activities:
            # Technologies
            techs = activity.get("technologies", [])
            all_technologies.extend(techs)
            
            # Description
            desc = activity.get("description", "")
            all_descriptions.append(desc.lower())
            
            # Extract words from description
            desc_words = re.findall(r'\b[a-z]{3,}\b', desc.lower())
            # Filter common words
            common_words = {
                "the", "and", "for", "with", "was", "were", "this", "that",
                "from", "they", "have", "had", "what", "when", "where", "who",
                "how", "why", "but", "not", "all", "any", "can", "had", "her",
                "his", "has", "you", "your", "been", "being", "are", "said",
                "each", "which", "will", "about", "could", "would", "should",
                "there", "their", "them", "then", "than", "some", "time", "may",
                "way", "many", "may", "use", "her", "now", "him", "its", "two",
                "more", "very", "after", "back", "other", "many", "she", "may",
                "one", "all", "would", "there", "their", "what", "said", "each",
                "which", "will", "about", "could", "should", "only", "new", "years",
                "know", "also", "get", "through", "much", "before", "too", "any",
                "same", "look", "work", "life", "even", "most", "after", "think",
                "here", "make", "well", "down", "first", "where", "why", "right",
                "see", "him", "over", "such", "take", "come", "good", "few", "own",
                "under", "last", "find", "give", "does", "made", "part", "these",
            }
            keywords.update(w for w in desc_words if w not in common_words and len(w) > 3)
        
        # Add technologies (cleaned up)
        for tech in all_technologies:
            tech_clean = tech.lower().strip()
            if tech_clean and len(tech_clean) > 1:
                keywords.add(tech_clean)
        
        # Remove very common tech words that don't help distinguish
        generic_tech = {"api", "app", "web", "code", "data", "server", "client"}
        keywords -= generic_tech
        
        # Convert to sorted list for consistency
        result = sorted(keywords)
        
        # Limit to top 20 most relevant
        return result[:20]
    
    def suggest_project_for_activity(
        self,
        description: str,
        technologies: List[str],
        existing_projects: Dict[str, Project],
    ) -> str:
        """
        Suggest the best matching existing project for an activity.
        
        Args:
            description: Activity description
            technologies: List of technologies used
            existing_projects: Dictionary of existing projects
            
        Returns:
            Project name or "misc" if no good match
        """
        if not existing_projects:
            return "misc"
        
        # Normalize input
        desc_lower = description.lower()
        tech_set = set(t.lower() for t in technologies)
        
        scores = {}
        
        for name, project in existing_projects.items():
            score = 0
            
            # Check project name in description
            if name.lower() in desc_lower:
                score += 10
            
            # Check keywords match
            if project.keywords:
                keyword_matches = sum(1 for k in project.keywords if k.lower() in desc_lower)
                score += keyword_matches * 2
            
            # Check tags match
            if project.tags:
                tag_matches = sum(1 for t in project.tags if t.lower() in desc_lower)
                score += tag_matches * 3
            
            # Check technology overlap
            if project.keywords:
                project_techs = set(k.lower() for k in project.keywords)
                tech_overlap = len(tech_set & project_techs)
                score += tech_overlap * 2
            
            scores[name] = score
        
        # Find best match
        if scores:
            best_project = max(scores, key=scores.get)
            best_score = scores[best_project]
            
            # Require minimum threshold
            if best_score >= 5:
                return best_project
        
        return "misc"
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize project name for comparison.
        
        Args:
            name: Project name
            
        Returns:
            Normalized name
        """
        # Convert to lowercase
        normalized = name.lower()
        
        # Replace common separators with space
        normalized = re.sub(r'[-_]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _similarity(self, str1: str, str2: str) -> float:
        """
        Calculate string similarity using SequenceMatcher.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def get_conservative_recommendations(
        self,
        proposed_projects: List[Dict[str, Any]],
        activities_by_project: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        Filter proposed projects using conservative creation rules.
        
        Args:
            proposed_projects: List of project dictionaries from AI
            activities_by_project: Mapping of project names to activities
            
        Returns:
            Filtered list of projects that meet creation criteria
        """
        approved = []
        
        for project in proposed_projects:
            name = project.get("name", "")
            activities = activities_by_project.get(name, [])
            
            if self.should_create_project(name, activities):
                # Add keywords to the project
                keywords = self.get_project_keywords(name, activities)
                project["keywords"] = keywords
                approved.append(project)
        
        logger.info(
            f"Conservative filtering: {len(proposed_projects)} proposed, "
            f"{len(approved)} approved"
        )
        return approved
