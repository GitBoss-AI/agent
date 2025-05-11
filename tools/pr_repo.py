import requests
import os
import warnings
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Suppress urllib3 warnings about LibreSSL compatibility
warnings.filterwarnings('ignore', category=Warning, module='urllib3')

# Global configuration variables
GITHUB_TOKEN = ''
REPOSITORY_URL = 'https://github.com/facebook/react'
BRANCH_NAME = 'main'

class ListRepositoryPullRequestsTool:
    """Tool to fetch a list of pull requests for a repository."""
    
    def __init__(self, github_token: str = None, repo_url: str = None, branch: str = None):
        """Initialize with GitHub token and repository URL.
        
        Args:
            github_token: GitHub access token (will use global if None)
            repo_url: Repository URL (will use global if None)
            branch: Repository branch (will use global if None)
        """
        self.github_token = github_token or GITHUB_TOKEN
        self.repo_url = repo_url or REPOSITORY_URL
        self.branch = branch or BRANCH_NAME
        
        if not self.github_token:
            raise ValueError("GitHub access token not provided")
            
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
    
    def list_repository_pull_requests(
        self,
        repository_owner: str = None,
        repository_name: str = None,
        date: str = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch a list of pull requests for a repository.
        
        Args:
            repository_owner: Repository owner (optional)
            repository_name: Repository name (optional)
            date: Date range in days (default: 7 days)
            
        Returns:
            Dictionary containing a list of basic PR objects
        """
        # Handle repository info
        owner, repo = None, None
        if repository_owner and repository_name:
            owner, repo = repository_owner, repository_name
        else:
            owner, repo = self._parse_repo_info()
            
        if not owner or not repo:
            raise ValueError("Repository information not provided and could not be parsed from global settings")
        
        # Calculate date range (default to 1 week)
        if date is None:
            date = "7"
        
        days = int(date)
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Make API request to list pull requests
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 100,
            "since": since_date
        }
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
            
        pull_requests_data = response.json()
        pull_requests = []
        
        for pr in pull_requests_data:
            pull_requests.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "url": pr["html_url"],
                "created_at": pr["created_at"]
            })
            
        return {"pull_requests": pull_requests}

# Test the functionality when script is run directly
if __name__ == "__main__":
    try:
        # Create an instance of the tool
        pr_tool = ListRepositoryPullRequestsTool()
        
        print("Fetching recent pull requests...")
        
        prs = pr_tool.list_repository_pull_requests(date="14")  # Last 2 weeks
        
        print(f"Found {len(prs['pull_requests'])} pull requests:")
        for i, pr in enumerate(prs['pull_requests'], 1):
            print(f"{i}. #{pr['number']}: {pr['title']} - {pr['state']} - Created: {pr['created_at']}")
            
        # Save results to JSON file
        output_file = "repository_pull_requests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(prs, f, indent=2, ensure_ascii=False)
            
        print(f"\nPull requests saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
