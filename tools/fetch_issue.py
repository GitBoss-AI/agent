import os
import requests
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def fetch_issue(
    issue_number: int,
    repo_owner: str = None,
    repo_name: str = None
) -> Dict[str, Any]:
    """Fetch a specific issue from the repository with its comments.
    
    Args:
        issue_number: The number of the issue to fetch.
        repo_owner: Repository owner/organization name. If None, uses REPO_OWNER from .env.
        repo_name: Repository name. If None, uses REPO_NAME from .env.
        
    Returns:
        Issue object with ID, title, description, and comments.
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Get repo info from parameters or environment variables
    if not repo_owner:
        repo_owner = os.getenv('REPO_OWNER')
        if not repo_owner:
            raise ValueError("Repository owner not provided and REPO_OWNER not found in .env file.")
    
    if not repo_name:
        repo_name = os.getenv('REPO_NAME')
        if not repo_name:
            raise ValueError("Repository name not provided and REPO_NAME not found in .env file.")
    
    # Build API URL for specific issue
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}"
    
    # Set headers with GitHub token
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Make API request for the issue
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    issue = response.json()
    
    # Skip if it's a pull request
    if "pull_request" in issue:
        raise ValueError(f"Issue #{issue_number} is actually a pull request, not an issue.")
    
    # Get comments for this issue
    comments_url = issue["comments_url"]
    comments_response = requests.get(comments_url, headers=headers)
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
        #"id": issue["id"],
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
        #"labels": [label["name"] for label in issue["labels"]],
        #"assignees": [assignee["login"] for assignee in issue["assignees"]],
        "url": issue["html_url"],
        "participants": list(set([
            comment["author"]["username"] for comment in comments
        ] + [issue["user"]["login"]]))  # Include issue author and all comment authors
    }
    
    return issue_obj

def fetch_repository_issues(
    state: str = "open", 
    limit: int = 20,
    repo_owner: str = None,
    repo_name: str = None
) -> list:
    """Fetch multiple issues from the repository with comments.
    
    Args:
        state: State of issues to fetch (open, closed, all). Default is open.
        limit: Maximum number of issues to fetch. Default is 20.
        repo_owner: Repository owner/organization name. If None, uses REPO_OWNER from .env.
        repo_name: Repository name. If None, uses REPO_NAME from .env.
        
    Returns:
        List of issue objects with ID, title, description, and comments.
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Get repo info from parameters or environment variables
    if not repo_owner:
        repo_owner = os.getenv('REPO_OWNER')
        if not repo_owner:
            raise ValueError("Repository owner not provided and REPO_OWNER not found in .env file.")
    
    if not repo_name:
        repo_name = os.getenv('REPO_NAME')
        if not repo_name:
            raise ValueError("Repository name not provided and REPO_NAME not found in .env file.")
    
    # Set headers with GitHub token
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Build API URL
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    params = {
        "state": state,
        "per_page": limit,
        "sort": "created",
        "direction": "desc"
    }
    
    # Make API request for issues
    response = requests.get(url, headers=headers, params=params)
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
        comments_response = requests.get(comments_url, headers=headers)
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
            #"id": issue["id"],
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
            #"labels": [label["name"] for label in issue["labels"]],
            #"assignees": [assignee["login"] for assignee in issue["assignees"]],
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
        # Example: Fetch a specific issue by number
        issue_number = 31722  # Replace with the issue number you want to fetch
        repo_owner = "facebook"  # Replace with the repository owner
        repo_name = "react"   # Replace with the repository name
        
        issue = fetch_issue(
            issue_number=issue_number,
            repo_owner=repo_owner,
            repo_name=repo_name
        )
        
        print(f"Issue #{issue['number']}: {issue['title']}")
        print(f"State: {issue['state']}")
        print(f"Created by: {issue['author']['username']}")
        print(f"Created at: {issue['created_at']}")
        print(f"Comments: {issue['comments_count']}")
        print(f"Participants: {', '.join(issue['participants'])}")
        
        if issue['description']:
            desc_preview = issue['description'][:100] + "..." if len(issue['description']) > 100 else issue['description']
            print(f"Description: {desc_preview}")
            
        if issue['comments']:
            print(f"Comments:")
            for i, comment in enumerate(issue['comments'], 1):
                comment_preview = comment['body'][:50] + "..." if len(comment['body']) > 50 else comment['body']
                print(f"  - {comment['author']['username']}: {comment_preview}")
        
        # Save results to JSON file
        output_file = f"issue_{issue_number}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(issue, f, indent=2, ensure_ascii=False)
            
        print(f"\nIssue saved to {output_file}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
