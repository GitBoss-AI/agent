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
    """Fetch contributor activities and basic PR information.
    
    Args:
        pr_number: Pull request number
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        
    Returns:
        Dictionary containing PR basic info and contributor activities
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
    
    # Get PR reviews
    reviews_url = f"{url}/reviews"
    reviews_response = requests.get(reviews_url, headers=headers)
    reviews_data = reviews_response.json() if reviews_response.status_code == 200 else []
    
    # Get PR comments
    comments_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
    comments_response = requests.get(comments_url, headers=headers)
    comments_data = comments_response.json() if comments_response.status_code == 200 else []
    
    # Get changed files
    files_url = f"{url}/files"
    files_response = requests.get(files_url, headers=headers)
    changed_files = []
    if files_response.status_code == 200:
        files_data = files_response.json()
        changed_files = [file["filename"] for file in files_data]
    
    # Collect all contributor activities
    contributors = {}
    
    # Add PR author
    author = pr_data["user"]["login"]
    contributors[author] = {
        "activities": [{
            "type": "created PR",
            "content": None,
            "timestamp": pr_data["created_at"]
        }],
        "profile_url": pr_data["user"]["html_url"]
    }
    
    # Add assignees
    for assignee in pr_data.get("assignees", []):
        username = assignee["login"]
        if username not in contributors:
            contributors[username] = {
                "activities": [],
                "profile_url": assignee["html_url"]
            }
        contributors[username]["activities"].append({
            "type": "assigned",
            "content": None,
            "timestamp": pr_data["updated_at"]
        })
    
    # Add reviewers
    for reviewer in pr_data.get("requested_reviewers", []):
        username = reviewer["login"]
        if username not in contributors:
            contributors[username] = {
                "activities": [],
                "profile_url": reviewer["html_url"]
            }
        contributors[username]["activities"].append({
            "type": "requested to review",
            "content": None,
            "timestamp": pr_data["updated_at"]
        })
    
    # Add reviews
    for review in reviews_data:
        username = review["user"]["login"]
        if username not in contributors:
            contributors[username] = {
                "activities": [],
                "profile_url": review["user"]["html_url"]
            }
        contributors[username]["activities"].append({
            "type": f"reviewed ({review['state']})",
            "content": review.get("body", ""),
            "timestamp": review["submitted_at"]
        })
    
    # Add comments
    for comment in comments_data:
        username = comment["user"]["login"]
        if username not in contributors:
            contributors[username] = {
                "activities": [],
                "profile_url": comment["user"]["html_url"]
            }
        contributors[username]["activities"].append({
            "type": "commented",
            "content": comment["body"],
            "timestamp": comment["created_at"]
        })
    
    # Add merger if PR was merged
    if pr_data.get("merged_by"):
        merger = pr_data["merged_by"]["login"]
        if merger not in contributors:
            contributors[merger] = {
                "activities": [],
                "profile_url": pr_data["merged_by"]["html_url"]
            }
        contributors[merger]["activities"].append({
            "type": "merged",
            "content": None,
            "timestamp": pr_data["merged_at"]
        })
    
    # Sort activities by timestamp for each contributor
    for contributor in contributors.values():
        contributor["activities"].sort(key=lambda x: x["timestamp"])
    
    # Format the result
    pr_details = {
        "title": pr_data["title"],
        "description": pr_data["body"] if pr_data.get("body") else "",
        "state": pr_data["state"],
        "created_at": pr_data["created_at"],
        "changed_files": changed_files,
        "contributors": contributors
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
        
        print("\nPull Request Information:")
        print(f"Title: {pr_details['title']}")
        print(f"State: {pr_details['state']}")
        print(f"Created: {pr_details['created_at']}")
        print(f"\nDescription:\n{pr_details['description']}")
        
        print("\nChanged Files:")
        for file in pr_details['changed_files']:
            print(f"- {file}")
        
        print("\nContributor Activities:")
        for username, data in pr_details['contributors'].items():
            print(f"\n{username} ({data['profile_url']}):")
            for activity in data['activities']:
                print(f"- {activity['type']} at {activity['timestamp']}")
                if activity['content']:
                    print(f"  Content: {activity['content']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
