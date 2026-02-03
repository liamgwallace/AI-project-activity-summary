"""
GitHub data collector for PAIS.
Fetches commits and pull requests from accessible repositories.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import time

from github import Github
from github.RateLimit import RateLimit

from collectors.base import BaseCollector
from storage.database import Database


class GitHubCollector(BaseCollector):
    """Collects GitHub activity (commits and PRs)."""
    
    def __init__(self, token: str, username: str):
        """Initialize with PyGithub client."""
        super().__init__("github")
        self.token = token
        self.username = username
        self.github: Optional[Github] = None
        self.db = Database(self.settings.database.path)
        
        if token:
            try:
                self.github = Github(token)
                self.logger.info(f"Initialized GitHub collector for user: {username}")
            except Exception as e:
                self.logger.error(f"Failed to initialize GitHub client: {e}")
        else:
            self.logger.warning("No GitHub token provided")
    
    def _check_rate_limit(self) -> bool:
        """Check if we have API calls remaining. Returns True if we can proceed."""
        if not self.github:
            return False
        
        try:
            rate_limit = self.github.get_rate_limit()
            core_limit = rate_limit.core
            
            if core_limit.remaining < 10:
                reset_time = core_limit.reset.timestamp()
                wait_seconds = reset_time - time.time()
                
                if wait_seconds > 0:
                    self.logger.warning(
                        f"Rate limit almost exceeded. Waiting {wait_seconds:.0f} seconds."
                    )
                    time.sleep(min(wait_seconds, 60))  # Wait max 60 seconds
                
                return self.github.get_rate_limit().core.remaining > 0
            
            return True
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            return True  # Proceed anyway, let the actual call fail if needed
    
    def _get_user_repos(self) -> List[Any]:
        """Get all repositories accessible to the user."""
        if not self.github:
            return []
        
        repos = []
        
        try:
            user = self.github.get_user()
            
            # Get user's own repos
            self.logger.info("Fetching user's repositories...")
            for repo in user.get_repos():
                repos.append(repo)
            
            # Get repos from organizations
            for org in user.get_orgs():
                self.logger.info(f"Fetching repositories from organization: {org.login}")
                for repo in org.get_repos():
                    repos.append(repo)
            
        except Exception as e:
            self.logger.error(f"Error fetching repositories: {e}")
        
        return repos
    
    def _fetch_commits(self, repo: Any, since: datetime) -> List[Dict[str, Any]]:
        """Fetch commits from a repository since the given date."""
        commits = []
        
        try:
            if not self._check_rate_limit():
                return commits
            
            # Get commits by the user
            for commit in repo.get_commits(since=since, author=self.username):
                if not self._check_rate_limit():
                    break
                
                try:
                    commit_data = commit.commit
                    commit_time = commit_data.committer.date
                    
                    # Get files changed in this commit
                    files_changed = []
                    try:
                        for file in commit.files:
                            files_changed.append(file.filename)
                    except:
                        pass
                    
                    event = self._create_event(
                        timestamp=commit_time,
                        event_type="commit",
                        data={
                            "repo": repo.full_name,
                            "branch": commit_data.message.split("\n")[0][:50],
                            "message": commit_data.message,
                            "sha": commit.sha[:7],
                            "files_changed": files_changed,
                        }
                    )
                    commits.append(event)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing commit: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching commits from {repo.full_name}: {e}")
        
        return commits
    
    def _fetch_prs(self, repo: Any, since: datetime) -> List[Dict[str, Any]]:
        """Fetch pull requests from a repository since the given date."""
        prs = []
        
        try:
            if not self._check_rate_limit():
                return prs
            
            # Get PRs created or updated since the date
            for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
                if not self._check_rate_limit():
                    break
                
                # Check if PR is by the user and within time range
                if pr.user.login != self.username:
                    continue
                
                pr_time = pr.created_at
                if pr_time < since:
                    break  # PRs are sorted by updated, so we can break early
                
                try:
                    event = self._create_event(
                        timestamp=pr_time,
                        event_type="pr",
                        data={
                            "repo": repo.full_name,
                            "branch": pr.head.ref,
                            "message": pr.title,
                            "sha": f"PR#{pr.number}",
                            "files_changed": [],
                        }
                    )
                    prs.append(event)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing PR: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching PRs from {repo.full_name}: {e}")
        
        return prs
    
    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        """Collect commits and PRs from all accessible repositories."""
        events = []
        
        if not self.github:
            self.logger.error("GitHub client not initialized")
            return events
        
        self.logger.info(f"Starting GitHub collection since {since.isoformat()}")
        
        repos = self._get_user_repos()
        self.logger.info(f"Found {len(repos)} accessible repositories")
        
        # Filter repos if specific repos are configured
        target_repos = self.settings.github.repos
        if target_repos:
            repos = [r for r in repos if r.full_name in target_repos]
            self.logger.info(f"Filtered to {len(repos)} configured repositories")
        
        for repo in repos:
            self.logger.info(f"Processing repository: {repo.full_name}")
            
            # Fetch commits if enabled
            if self.settings.github.fetch_commits:
                commits = self._fetch_commits(repo, since)
                events.extend(commits)
                self.logger.info(f"Found {len(commits)} commits in {repo.full_name}")
            
            # Fetch PRs if enabled
            if self.settings.github.fetch_prs:
                prs = self._fetch_prs(repo, since)
                events.extend(prs)
                self.logger.info(f"Found {len(prs)} PRs in {repo.full_name}")
        
        self.logger.info(f"GitHub collection complete. Total events: {len(events)}")
        return events
    
    def test(self) -> Dict[str, Any]:
        """Test the collector by fetching recent sample activity."""
        result = {
            "success": False,
            "message": "",
            "sample_events": [],
        }
        
        if not self.github:
            result["message"] = "GitHub client not initialized - check token"
            return result
        
        try:
            # Get recent activity (last 7 days)
            since = datetime.now() - __import__("datetime").timedelta(days=7)
            sample_events = self.collect(since)
            
            # Limit to first 5 events
            result["sample_events"] = sample_events[:5]
            result["success"] = True
            result["message"] = f"Found {len(sample_events)} events in the last 7 days"
            
        except Exception as e:
            result["message"] = f"Test failed: {str(e)}"
            self.logger.error(f"GitHub collector test failed: {e}")
        
        return result
