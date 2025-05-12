import os
import requests
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FetchRepositoryIssues:
    """Tool to fetch issues from a GitHub repository with comments."""
    
    def __init__(self):
        """Initialize with GitHub token from environment variables."""
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.repo_owner = os.getenv('REPO_OWNER')
        self.repo_name = os.getenv('REPO_NAME')
        
        if not self.github_token:
            raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
        if not self.repo_owner or not self.repo_name:
            raise ValueError("Repository information not found. Please set REPO_OWNER and REPO_NAME in .env file.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def fetch_repository_issues(self, state: str = "open", limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch issues from the repository with comments.
        
        Args:
            state: State of issues to fetch (open, closed, all). Default is open.
            limit: Maximum number of issues to fetch. Default is 20.
            
        Returns:
            List of issue objects with ID, title, description, and comments.
        """
        # Build API URL
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        params = {
            "state": state,
            "per_page": limit,
            "sort": "created",
            "direction": "desc"
        }
        
        # Make API request for issues
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
        
        issues_data = response.json()
        result = []
        
        # Process each issue
        for issue in issues_data:
            # Skip pull requests (which are also returned by the issues endpoint)
            if "pull_request" in issue:
                continue
                
            # Get comments for this issue
            comments_url = issue["comments_url"]
            comments_response = requests.get(comments_url, headers=self._get_headers())
            comments = []
            
            if comments_response.status_code == 200:
                comments_data = comments_response.json()
                for comment in comments_data:
                    comments.append({
                        "author": {
                            "username": comment["user"]["login"],
                            "profile_url": comment["user"]["html_url"]
                        },
                        "created_at": comment["created_at"],
                        "body": comment["body"]
                    })
            
            # Build issue object
            issue_obj = {
                "id": issue["id"],
                "number": issue["number"],
                "title": issue["title"],
                "description": issue["body"] or "",
                "state": issue["state"],
                "created_at": issue["created_at"],
                "author": {
                    "username": issue["user"]["login"],
                    "profile_url": issue["user"]["html_url"]
                },
                "comments": comments,
                "comments_count": len(comments),
                "labels": [label["name"] for label in issue["labels"]],
                "assignees": [assignee["login"] for assignee in issue["assignees"]],
                "url": issue["html_url"],
                "participants": list(set([
                    comment["author"]["username"] for comment in comments
                ] + [issue["user"]["login"]]))  # Include issue author and all comment authors
            }
            
            result.append(issue_obj)
        
        return result

# Example usage
if __name__ == "__main__":
    try:
        issues_tool = FetchRepositoryIssues()
        
        # Fetch issues 
        issues = issues_tool.fetch_repository_issues(limit=50)
        
        print(f"Found {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"\n{i}. Issue #{issue['number']}: {issue['title']}")
            print(f"   State: {issue['state']}")
            print(f"   Created by: {issue['author']['username']}")
            print(f"   Created at: {issue['created_at']}")
            print(f"   Comments: {issue['comments_count']}")
            print(f"   Participants: {', '.join(issue['participants'])}")
            
            if issue['description']:
                desc_preview = issue['description'][:100] + "..." if len(issue['description']) > 100 else issue['description']
                print(f"   Description: {desc_preview}")
                
            if issue['comments']:
                print(f"   Latest comments:")
                for j, comment in enumerate(issue['comments'], 1):
                    comment_preview = comment['body'][:50] + "..." if len(comment['body']) > 50 else comment['body']
                    print(f"     - {comment['author']['username']}: {comment_preview}")
        
        # Save results to JSON file
        output_file = "repository_issues.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(issues, f, indent=2, ensure_ascii=False)
            
        print(f"\nIssues saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
