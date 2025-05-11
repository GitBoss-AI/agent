import requests
import os
import warnings
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FetchPullRequestDetailsTool:
    """Tool to fetch detailed information about a specific pull request."""
    
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
    
    def fetch_pull_request_details(
        self,
        pr_number: int,
        repository_owner: str = None,
        repository_name: str = None
    ) -> Dict[str, Any]:
        """Fetch detailed information about a specific pull request.
        
        Args:
            pr_number: The pull request number
            repository_owner: Repository owner (optional)
            repository_name: Repository name (optional)
            
        Returns:
            Dictionary containing detailed PR information
        """
        # Handle repository info
        owner = repository_owner or self.repo_owner
        repo = repository_name or self.repo_name
            
        if not owner or not repo:
            raise ValueError("Repository information not provided and could not be parsed from settings")
        
        # Get basic PR information
        pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = requests.get(pr_url, headers=self._get_headers())
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
        
        pr_data = response.json()
        
        # Get PR files
        files_url = f"{pr_url}/files"
        files_response = requests.get(files_url, headers=self._get_headers())
        if files_response.status_code != 200:
            raise Exception(f"GitHub API error (files): {files_response.status_code} - {files_response.text}")
        
        files_data = files_response.json()
        
        # Fetch PR reviews and comments count
        reviews_url = f"{pr_url}/reviews"
        reviews_response = requests.get(reviews_url, headers=self._get_headers())
        
        comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        comments_response = requests.get(comments_url, headers=self._get_headers())
        
        # Get PR diff
        diff_headers = self._get_headers()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"
        diff_response = requests.get(pr_url, headers=diff_headers)
        diff_content = diff_response.text if diff_response.status_code == 200 else ""
        
        # Process PR changed files
        changed_files = []
        for file_data in files_data:
            changed_file = {
                "filename": file_data.get("filename"),
                "additions": file_data.get("additions"),
                "deletions": file_data.get("deletions"),
                "changes": file_data.get("changes"),
                "status": file_data.get("status"),
                "patch": file_data.get("patch", "")
            }
            changed_files.append(changed_file)
        
        # Process labels
        labels = [label.get("name") for label in pr_data.get("labels", [])]
        
        # Process assignees
        assignees = [assignee.get("login") for assignee in pr_data.get("assignees", [])]
        
        # Process requested reviewers
        requested_reviewers = [reviewer.get("login") for reviewer in pr_data.get("requested_reviewers", [])]
        
        # Compile the detailed PR object
        detailed_pr = {
            "title": pr_data.get("title"),
            "url": pr_data.get("html_url"),
            "number": pr_data.get("number"),
            "state": pr_data.get("state"),
            "repository": f"{owner}/{repo}",
            "author": pr_data.get("user", {}).get("login"),
            "created_at": pr_data.get("created_at"),
            "updated_at": pr_data.get("updated_at"),
            "description": pr_data.get("body") or "",
            "mergeable": pr_data.get("mergeable"),
            "merged_by": pr_data.get("merged_by", {}).get("login") if pr_data.get("merged_by") else None,
            "comments_count": pr_data.get("comments", 0) + (len(reviews_response.json()) if reviews_response.status_code == 200 else 0),
            "review_comments_count": pr_data.get("review_comments", 0),
            "commits_count": pr_data.get("commits", 0),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files_count": pr_data.get("changed_files", 0),
            "changed_files": changed_files,
            "labels": labels,
            "assignees": assignees,
            "requested_reviewers": requested_reviewers,
            "diff_content": diff_content
        }
        
        return detailed_pr

# Test the functionality when script is run directly
if __name__ == "__main__":
    try:
        # Create an instance of the tool
        pr_tool = FetchPullRequestDetailsTool()
        
        # Get the PR number from user input or use a default
        pr_number = input("Enter PR number: ")
        if not pr_number:
            pr_number = 25627  # Default PR number for testing
        else:
            pr_number = int(pr_number)
            
        print(f"Fetching details for PR #{pr_number}...")
        
        pr_details = pr_tool.fetch_pull_request_details(pr_number=pr_number)
        
        # Print a summary of the PR details
        print(f"\nPR #{pr_details['number']}: {pr_details['title']}")
        print(f"State: {pr_details['state']}")
        print(f"Author: {pr_details['author']}")
        print(f"Created: {pr_details['created_at']}")
        print(f"Repository: {pr_details['repository']}")
        print(f"URL: {pr_details['url']}")
        print(f"Comments: {pr_details['comments_count']}")
        print(f"Changed files: {pr_details['changed_files_count']}")
        print(f"Additions: {pr_details['additions']}, Deletions: {pr_details['deletions']}")
        
        if pr_details['labels']:
            print(f"Labels: {', '.join(pr_details['labels'])}")
        
        if pr_details['assignees']:
            print(f"Assignees: {', '.join(pr_details['assignees'])}")
            
        # Save the full details to a JSON file
        output_file = f"pr_{pr_number}_details.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(pr_details, f, indent=2, ensure_ascii=False)
            
        print(f"\nDetailed information saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
