import requests
import os
import re
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_contributor_roles(activities: List[Dict[str, Any]]) -> List[str]:
    """Determine contributor roles based on their activities."""
    roles = set()
    
    for activity in activities:
        activity_type = activity["type"]
        if activity_type == "created PR":
            roles.add("Author")
        elif activity_type == "assigned":
            roles.add("Assignee")
        elif activity_type == "requested to review":
            roles.add("Requested Reviewer")
        elif activity_type.startswith("reviewed"):
            roles.add("Reviewer")
        elif activity_type == "merged":
            roles.add("Merger")
    
    return sorted(list(roles))

def extract_linked_issues(description: str) -> List[int]:
    """Extract issue numbers from PR description using common patterns."""
    patterns = [
        r'Fixes #(\d+)',
        r'Closes #(\d+)',
        r'Resolves #(\d+)',
        r'#(\d+)'
    ]
    
    issue_numbers = set()
    for pattern in patterns:
        matches = re.finditer(pattern, description, re.IGNORECASE)
        for match in matches:
            issue_numbers.add(int(match.group(1)))
    
    return sorted(list(issue_numbers))

def fetch_issue_details(issue_number: int, repo_owner: str, repo_name: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Fetch details for a specific issue."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    issue_data = response.json()
    return {
        "number": issue_data["number"],
        "title": issue_data["title"],
        "state": issue_data["state"],
        "created_at": issue_data["created_at"],
        "author": {
            "username": issue_data["user"]["login"],
            "profile_url": issue_data["user"]["html_url"]
        },
        "labels": [label["name"] for label in issue_data["labels"]],
        "assignees": [assignee["login"] for assignee in issue_data["assignees"]],
        "body": issue_data["body"],
        "url": url
    }

def get_all_paginated_data(url: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Fetch all paginated data from GitHub API."""
    all_data = []
    page = 1
    per_page = 100  # Maximum allowed by GitHub API
    
    while True:
        paginated_url = f"{url}?page={page}&per_page={per_page}"
        response = requests.get(paginated_url, headers=headers)
        
        if response.status_code != 200:
            break
            
        data = response.json()
        if not data:  # No more data
            break
            
        all_data.extend(data)
        page += 1
        
        # Check if we've reached the last page
        if len(data) < per_page:
            break
            
    return all_data

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
    
    # Get PR reviews with pagination
    reviews_url = f"{url}/reviews"
    reviews_data = get_all_paginated_data(reviews_url, headers)
    
    # Get PR comments with pagination
    comments_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
    comments_data = get_all_paginated_data(comments_url, headers)
    
    # Get review comments (comments on specific lines) with pagination
    review_comments_url = f"{url}/comments"
    review_comments_data = get_all_paginated_data(review_comments_url, headers)
    
    # Get changed files
    files_url = f"{url}/files"
    files_response = requests.get(files_url, headers=headers)
    changed_files = []
    if files_response.status_code == 200:
        files_data = files_response.json()
        changed_files = [file["filename"] for file in files_data]
    
    # Get linked issues
    linked_issues = []
    if pr_data.get("body"):
        issue_numbers = extract_linked_issues(pr_data["body"])
        for issue_number in issue_numbers:
            issue_details = fetch_issue_details(issue_number, repo_owner, repo_name, headers)
            if issue_details:
                linked_issues.append(issue_details)
    
    # Collect all contributor activities
    contributors = {}
    
    # Add PR author
    author = pr_data["user"]["login"]
    contributors[author] = {
        "activities": [{
            "type": "created PR",
            "content": pr_data.get("body", ""),  # Include PR description
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
    
    # Add reviews with full content
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
            "timestamp": review["submitted_at"],
            "review_id": review["id"]
        })
    
    # Add review comments (comments on specific lines)
    for comment in review_comments_data:
        username = comment["user"]["login"]
        if username not in contributors:
            contributors[username] = {
                "activities": [],
                "profile_url": comment["user"]["html_url"]
            }
        contributors[username]["activities"].append({
            "type": "review comment",
            "content": comment["body"],
            "timestamp": comment["created_at"],
            "path": comment["path"],
            "line": comment.get("line"),
            "position": comment.get("position")
        })
    
    # Add general comments
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
        # Add roles based on activities
        contributor["roles"] = get_contributor_roles(contributor["activities"])
    
    # Format the result
    pr_details = {
        "title": pr_data["title"],
        "description": pr_data["body"] if pr_data.get("body") else "",
        "state": pr_data["state"],
        "created_at": pr_data["created_at"],
        "changed_files": changed_files,
        "linked_issues": linked_issues,
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
        print(pr_details)
        
        # print("\nPull Request Information:")
        # print(f"Title: {pr_details['title']}")
        # print(f"State: {pr_details['state']}")
        # print(f"Created: {pr_details['created_at']}")
        # print(f"\nDescription:\n{pr_details['description']}")
        
        # print("\nChanged Files:")
        # for file in pr_details['changed_files']:
        #     print(f"- {file}")
        
        # if pr_details['linked_issues']:
        #     print("\nLinked Issues:")
        #     for issue in pr_details['linked_issues']:
        #         print(f"\nIssue #{issue['number']}: {issue['title']}")
        #         print(f"State: {issue['state']}")
        #         print(f"Created by: {issue['author']['username']}")
        #         print(f"Labels: {', '.join(issue['labels'])}")
        #         print(f"Assignees: {', '.join(issue['assignees'])}")
        
        # print("\nContributor Activities:")
        # for username, data in pr_details['contributors'].items():
        #     roles = ", ".join(data['roles'])
        #     print(f"\n{username} ({data['profile_url']}):")
        #     print(f"Roles: {roles}")
        #     for activity in data['activities']:
        #         print(f"- {activity['type']} at {activity['timestamp']}")
        #         if activity['content']:
        #             print(f"  Content: {activity['content']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
