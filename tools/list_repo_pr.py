import requests
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def list_repository_pull_requests(
    repo_owner: str,
    repo_name: str,
    days: int = 7
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch a list of pull requests for a repository.
    
    Args:
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        days: Number of days to look back (default: 7)
        
    Returns:
        Dictionary containing a list of basic PR objects
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Calculate date range
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Make API request to list pull requests
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {
        "state": "all",
        "sort": "created",
        "direction": "desc",
        "per_page": 100,
        "since": since_date
    }
    
    response = requests.get(url, headers=headers, params=params)
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

# Example usage
if __name__ == "__main__":
    try:
        # Example: Get PRs for tensorflow/tensorflow from last 2 days
        prs = list_repository_pull_requests(
            repo_owner="tensorflow",
            repo_name="tensorflow",
            days=2
        )
        
        print(f"Found {len(prs['pull_requests'])} pull requests:")
        for i, pr in enumerate(prs['pull_requests'], 1):
            print(f"{i}. #{pr['number']}: {pr['title']} - {pr['state']} - Created: {pr['created_at']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
