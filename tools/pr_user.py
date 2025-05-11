import requests
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress urllib3 warnings about LibreSSL compatibility


class FetchUserPullRequestsTool:
    """Tool to fetch pull requests associated with a specific user."""
    
    def __init__(self, github_token: str = None, repo_owner: str = None, repo_name: str = None, branch: str = None):
        """Initialize with GitHub token and repository information.
        
        Args:
            github_token: GitHub access token (will use global if None)
            repo_owner: Repository owner (will use global if None)
            repo_name: Repository name (will use global if None)
            branch: Repository branch (will use global if None)
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.repo_owner = repo_owner or os.getenv('REPO_OWNER')
        self.repo_name = repo_name or os.getenv('REPO_NAME')
        self.branch = branch or os.getenv('BRANCH_NAME')
        
        if not self.github_token:
            raise ValueError("GitHub access token not provided and not found in environment")
        if not self.repo_owner or not self.repo_name:
            raise ValueError("Repository owner and name not provided and not found in environment")
            
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def _parse_repo_info(self, repo_full_name: str = None) -> tuple:
        """Parse repository owner and name from URL or full name."""
        if repo_full_name:
            parts = repo_full_name.split('/')
            if len(parts) == 2:
                return parts[0], parts[1]
        
        # Extract from repo URL if full name not provided
        if self.repo_url:
            # Handle formats like https://github.com/owner/repo or git@github.com:owner/repo.git
            url = self.repo_url.rstrip('/')
            if 'github.com' in url:
                if url.startswith('git@'):
                    # Format: git@github.com:owner/repo.git
                    path = url.split('github.com:')[1]
                else:
                    # Format: https://github.com/owner/repo
                    path = url.split('github.com/')[1]
                
                path = path.replace('.git', '')
                parts = path.split('/')
                if len(parts) >= 2:
                    return parts[0], parts[1]
        
        return None, None
        
    def fetch_user_pull_requests(
        self,
        username: str,
        period: str = None,
        repository_owner: str = None,
        repository_name: str = None,
        role: str = "author",
        status: str = "open"
    ) -> List[Dict[str, Any]]:
        """Fetch pull requests associated with a user.
        
        Args:
            username: GitHub username
            period: Date range in format "YYYY-MM-DD:YYYY-MM-DD"
            repository_owner: Repository owner (optional)
            repository_name: Repository name (optional)
            role: User's role in PRs (author, assignee, etc.)
            status: PR status (open, closed, merged, etc.)
            
        Returns:
            List of PR objects with details
        """
        # Handle repository info
        owner = repository_owner or self.repo_owner
        repo = repository_name or self.repo_name
            
        if not owner or not repo:
            raise ValueError("Repository information not provided and could not be parsed from settings")
            
        # Parse period
        since, until = None, None
        if period:
            dates = period.split(':')
            if len(dates) == 2:
                since, until = dates[0], dates[1]
                
        # Build query parameters
        query = f"involves:{username}"
        if role == "author":
            query = f"author:{username}"
        elif role == "assignee":
            query = f"assignee:{username}"
            
        # Add repository filter
        query += f" repo:{owner}/{repo}"
        
        # Add status filter
        if status == "open":
            query += " is:open"
        elif status == "closed":
            query += " is:closed"
        elif status == "merged":
            query += " is:merged"
            
        # Add date filter
        if since:
            query += f" created:>={since}"
        if until:
            query += f" created:<={until}"
            
        # Make API request
        url = "https://api.github.com/search/issues"
        params = {
            "q": query,
            "sort": "created",
            "order": "desc",
            "per_page": 100
        }
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
            
        data = response.json()
        pull_requests = []
        
        for item in data.get("items", []):
            # Skip issues (we only want PRs)
            if "pull_request" not in item:
                continue
                
            # Get PR details
            pr_url = item["pull_request"]["url"]
            pr_response = requests.get(pr_url, headers=self._get_headers())
            if pr_response.status_code != 200:
                continue
                
            pr_data = pr_response.json()
            
            # Format the result
            pr_info = {
                "title": item["title"],
                "url": item["html_url"],
                "number": item["number"],
                "state": pr_data["state"],
                "repository": f"{owner}/{repo}",
                "author": item["user"]["login"],
                "created_at": item["created_at"],
                "merged_at": pr_data.get("merged_at"),
                "closed_at": item.get("closed_at"),
                "description": item["body"] if item.get("body") else ""
            }
            
            pull_requests.append(pr_info)
            
        return pull_requests
