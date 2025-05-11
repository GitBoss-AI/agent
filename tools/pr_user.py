import requests
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress urllib3 warnings about LibreSSL compatibility


def fetch_user_pull_requests(
    username: str,
    repo_owner: str,
    repo_name: str,
    period: str = None,
    role: str = "author",
    status: str = "open"
) -> List[Dict[str, Any]]:
    """Fetch pull requests associated with a user.
    
    Args:
        username: GitHub username
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        period: Date range in format "YYYY-MM-DD:YYYY-MM-DD"
        role: User's role in PRs (author, assignee, etc.)
        status: PR status (open, closed, merged, etc.)
        
    Returns:
        List of PR objects with details
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
            
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
    query += f" repo:{repo_owner}/{repo_name}"
    
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
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 100
    }
    
    response = requests.get(url, headers=headers, params=params)
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
        pr_response = requests.get(pr_url, headers=headers)
        if pr_response.status_code != 200:
            continue
            
        pr_data = pr_response.json()
        
        # Format the result
        pr_info = {
            "title": item["title"],
            "url": item["html_url"],
            "number": item["number"],
            "state": pr_data["state"],
            "repository": f"{repo_owner}/{repo_name}",
            "author": item["user"]["login"],
            "created_at": item["created_at"],
            "merged_at": pr_data.get("merged_at"),
            "closed_at": item.get("closed_at"),
            "description": item["body"] if item.get("body") else ""
        }
        
        pull_requests.append(pr_info)
        
    return pull_requests

# Example usage
if __name__ == "__main__":
    try:
        # Example: Get PRs for user "ezhulenev" in tensorflow repository
        prs = fetch_user_pull_requests(
            username="ezhulenev",
            repo_owner="tensorflow",
            repo_name="tensorflow",
            period="2025-01-01:2025-05-11",
            role="author",
            status="all"
        )
        
        print(f"\nFound {len(prs)} pull requests:")
        for i, pr in enumerate(prs, 1):
            print(f"{i}. #{pr['number']}: {pr['title']} - {pr['state']} - Created: {pr['created_at']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
