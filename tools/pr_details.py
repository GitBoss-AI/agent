import requests
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def fetch_pull_request_details(
    pr_number: int,
    repo_owner: str,
    repo_name: str
) -> Dict[str, Any]:
    """Fetch detailed information about a specific pull request.
    
    Args:
        pr_number: Pull request number
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        
    Returns:
        Dictionary containing detailed PR information
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Make API request to get PR details
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
        
    pr_data = response.json()
    
    # Format the result
    pr_details = {
        "title": pr_data["title"],
        "number": pr_data["number"],
        "state": pr_data["state"],
        "url": pr_data["html_url"],
        "repository": f"{repo_owner}/{repo_name}",
        "author": pr_data["user"]["login"],
        "created_at": pr_data["created_at"],
        "updated_at": pr_data["updated_at"],
        "merged_at": pr_data.get("merged_at"),
        "closed_at": pr_data.get("closed_at"),
        "description": pr_data["body"] if pr_data.get("body") else "",
        "base_branch": pr_data["base"]["ref"],
        "head_branch": pr_data["head"]["ref"],
        "additions": pr_data["additions"],
        "deletions": pr_data["deletions"],
        "changed_files": pr_data["changed_files"],
        "commits": pr_data["commits"],
        "comments": pr_data["comments"],
        "review_comments": pr_data["review_comments"]
    }
    
    return pr_details

# Example usage
if __name__ == "__main__":
    try:
        # Example: Get details for PR #33165 in react repository
        pr_details = fetch_pull_request_details(
            pr_number=33165,
            repo_owner="facebook",
            repo_name="react"
        )
        
        print("\nPull Request Details:")
        print(f"Title: {pr_details['title']}")
        print(f"Number: #{pr_details['number']}")
        print(f"State: {pr_details['state']}")
        print(f"URL: {pr_details['url']}")
        print(f"Author: {pr_details['author']}")
        print(f"Created: {pr_details['created_at']}")
        print(f"Updated: {pr_details['updated_at']}")
        if pr_details['merged_at']:
            print(f"Merged: {pr_details['merged_at']}")
        if pr_details['closed_at']:
            print(f"Closed: {pr_details['closed_at']}")
        print(f"\nDescription:\n{pr_details['description']}")
        print(f"\nBase Branch: {pr_details['base_branch']}")
        print(f"Head Branch: {pr_details['head_branch']}")
        print(f"\nChanges:")
        print(f"- Additions: {pr_details['additions']}")
        print(f"- Deletions: {pr_details['deletions']}")
        print(f"- Changed Files: {pr_details['changed_files']}")
        print(f"- Commits: {pr_details['commits']}")
        print(f"- Comments: {pr_details['comments']}")
        print(f"- Review Comments: {pr_details['review_comments']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
