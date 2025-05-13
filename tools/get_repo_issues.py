import os
import requests
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def get_repo_issues(
    repo_owner: str,
    repo_name: str,
    start_date: str,  # YYYY-MM-DD format
    end_date: str,    # YYYY-MM-DD format
    state: str = "all"  # all, open, or closed
) -> Dict[str, Any]:
    """
    Fetch issues from a GitHub repository within a specified time range.
    
    Args:
        repo_owner: GitHub repository owner
        repo_name: GitHub repository name
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        state: Issue state filter (all, open, or closed)
        
    Returns:
        Dictionary containing issues metadata and a list of issues
    """
    if not GITHUB_TOKEN:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Validate dates
    try:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        if end_datetime < start_datetime:
            raise ValueError("End date must be after start date")
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError(f"Invalid date format. Please use YYYY-MM-DD format. Error: {e}")
        else:
            raise e
            
    # We'll use the GitHub search API to find issues in the date range
    # The search API allows us to use the 'created:' or 'updated:' parameters with date ranges
    search_url = "https://api.github.com/search/issues"
    
    # Format query to search for issues in the specified repo within the date range
    query = f"repo:{repo_owner}/{repo_name} is:issue created:{start_date}..{end_date}"
    if state != "all":
        query += f" state:{state}"
    
    params = {
        "q": query,
        "sort": "created",
        "order": "desc",
        "per_page": 100
    }
    
    all_issues = []
    page = 1
    
    try:
        # GitHub search API pagination
        while True:
            params["page"] = page
            response = requests.get(search_url, headers=HEADERS, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            if not items:
                break
                
            for item in items:
                issue = {
                    "id": item["id"],
                    "number": item["number"],
                    "title": item["title"],
                    "body": item.get("body"),  # Some issues may not have a body
                    "state": item["state"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "closed_at": item.get("closed_at"),
                    "html_url": item["html_url"],
                    "user": {
                        "login": item["user"]["login"],
                        "id": item["user"]["id"],
                        "html_url": item["user"]["html_url"],
                        "avatar_url": item["user"]["avatar_url"]
                    },
                    "labels": [{"name": label["name"], "color": label["color"]} for label in item.get("labels", [])]
                }
                
                all_issues.append(issue)
            
            # Check if we've reached the last page
            if len(items) < 100 or page >= data.get("total_count", 0) // 100 + 1:
                break
                
            page += 1
            
            # Be kind to the API - avoid rate limiting
            if page % 10 == 0:
                import time
                time.sleep(1)
    
        return {
            "repository": f"{repo_owner}/{repo_name}",
            "time_period": f"{start_date} to {end_date}",
            "state_filter": state,
            "total_issues": len(all_issues),
            "issues": all_issues
        }
        
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500
        error_message = e.response.json().get('message', str(e)) if hasattr(e, 'response') else str(e)
        
        error_response = {
            "error": error_message,
            "status_code": status_code,
            "repository": f"{repo_owner}/{repo_name}",
            "time_period": f"{start_date} to {end_date}"
        }
        
        if status_code == 404:
            error_response["details"] = f"Repository not found: {repo_owner}/{repo_name}"
        elif status_code == 403 and "rate limit" in error_message.lower():
            error_response["details"] = "GitHub API rate limit exceeded. Please try again later."
            
        return error_response

if __name__ == "__main__":
    print(get_repo_issues("alpsencer", "infrastack", "2025-05-10", "2025-05-13"))