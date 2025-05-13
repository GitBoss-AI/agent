# my_project/agent copy/tools/list_repo_pr.py
import requests
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import time # For potential rate limit handling

# Load environment variables from .env file
load_dotenv()

def list_repository_pull_requests(
    repo_owner: str,
    repo_name: str,
    start_date_str: Optional[str] = None, # YYYY-MM-DD
    end_date_str: Optional[str] = None,   # YYYY-MM-DD
    pr_state_filter: str = "all" # "all", "open", "closed", "merged"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch a list of pull requests for a repository within a date range,
    handling pagination.
    
    Args:
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        start_date_str: Start date in "YYYY-MM-DD" format
        end_date_str: End date in "YYYY-MM-DD" format
        pr_state_filter: Filter PRs by state ("all", "open", "closed", "merged")
        
    Returns:
        Dictionary containing a list of PR objects
    """
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")

    all_pull_requests_data: List[Dict[str, Any]] = []
    page = 1
    per_page = 100  # Max allowed by GitHub API for search

    # Construct search query
    query_parts = [f"repo:{repo_owner}/{repo_name}", "is:pr"]

    # Date range filtering
    # GitHub search API uses 'YYYY-MM-DDTHH:MM:SSZ' or 'YYYY-MM-DD'
    # For created qualifier, YYYY-MM-DD..YYYY-MM-DD works
    date_filter_parts = []
    if start_date_str:
        date_filter_parts.append(f">={start_date_str}")
    if end_date_str:
        # To include the end_date, we search for items created up to the end of that day.
        # Alternatively, if the API treats YYYY-MM-DD as start of day,
        # using YYYY-MM-DD..YYYY-MM-DD might exclude items on the end_date itself if time is a factor.
        # For simplicity, YYYY-MM-DD..YYYY-MM-DD generally includes the whole days.
        if start_date_str and len(date_filter_parts) > 0 : # if start_date also exists
             date_filter_parts[0] = f"{start_date_str}..{end_date_str}" #  replace >=start_date with start..end
        else:
            date_filter_parts.append(f"<={end_date_str}")


    if date_filter_parts:
        # If both start and end, they are already combined like "YYYY-MM-DD..YYYY-MM-DD"
        # If only one, it's like ">=YYYY-MM-DD" or "<=YYYY-MM-DD"
        if ".." in date_filter_parts[0]: # if it's a range
            query_parts.append(f"created:{date_filter_parts[0]}")
        elif len(date_filter_parts) == 2 : # Should not happen with current logic, but as a fallback
            query_parts.append(f"created:{date_filter_parts[0]}")
            query_parts.append(f"created:{date_filter_parts[1]}")
        elif len(date_filter_parts) == 1:
             query_parts.append(f"created:{date_filter_parts[0]}")

    # State filtering (GitHub search uses is:open, is:closed, is:merged)
    if pr_state_filter == "open":
        query_parts.append("is:open")
    elif pr_state_filter == "closed": # This implies not merged or merged
        query_parts.append("is:closed") # search API 'is:closed' means not open.
    elif pr_state_filter == "merged":
        query_parts.append("is:merged")
    # "all" means no specific state filter beyond is:pr

    final_query = " ".join(query_parts)
    
    search_url = "https://api.github.com/search/issues"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    max_retries = 3
    retry_delay = 5 # seconds

    while True:
        params = {
            "q": final_query,
            "sort": "created",
            "order": "desc", # Or "asc" if preferred
            "per_page": per_page,
            "page": page
        }
        
        retries = 0
        response = None
        while retries < max_retries:
            try:
                response = requests.get(search_url, headers=headers, params=params, timeout=10)
                response.raise_for_status()  # Raises an exception for 4XX/5XX errors
                break # Success
            except requests.exceptions.RequestException as e:
                retries += 1
                print(f"Error fetching page {page} (attempt {retries}/{max_retries}): {e}")
                if retries >= max_retries:
                    raise Exception(f"GitHub API error after {max_retries} retries: {e}")
                if response is not None and response.status_code == 403: # Rate limit
                    print(f"Rate limit hit. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay * retries) # Exponential backoff
        
        if response is None: # Should not happen if raise_for_status is working
             raise Exception("Failed to get response from GitHub API")

        data = response.json()
        items = data.get("items", [])
        
        if not items and page > 1: # No more items on subsequent pages
            break
        if not items and page == 1: # No items at all
            # print(f"No PRs found for query: {final_query}")
            break

        for item in items:
            # The search API returns issue-like objects for PRs.
            # We need to ensure the 'state' reflects PR state (open, closed, merged).
            # 'item["state"]' is the issue state.
            pr_api_state = item.get("state") # 'open' or 'closed' (for the issue)
            
            # Check if the PR is merged
            # The pull_request object in search results might not always have merged_at immediately.
            # A more reliable way if "is:merged" isn't used in query is to rely on the issue state
            # and potentially a separate call if exact merge status is critical and not directly available.
            # For now, we'll use the info available. `item.get("pull_request", {}).get("merged_at")`
            # can be None even for merged PRs in search results if not explicitly requested via specific PR endpoint.
            # If "is:merged" is in query, then these are merged.
            # If "is:closed" is in query, these could be merged or just closed.
            
            actual_pr_state = pr_api_state
            if item.get("pull_request", {}).get("merged_at"):
                 actual_pr_state = "merged"
            elif pr_state_filter == "merged" and not item.get("pull_request", {}).get("merged_at"):
                # If specifically filtering for "merged" but merged_at is not present, this might be an issue with GitHub's search API response.
                # Or it implies it's just closed without merge. For safety, if "is:merged" was queried, assume merged.
                if "is:merged" in final_query:
                    actual_pr_state = "merged"


            all_pull_requests_data.append({
                "number": item["number"],
                "title": item["title"],
                "state": actual_pr_state, # Use the determined state
                "url": item["html_url"],
                "created_at": item["created_at"] # ISO 8601 format
            })

        # Stop if we fetched less than per_page, meaning it's the last page
        if len(items) < per_page:
            break
        
        page += 1
        # GitHub's search API has a rate limit (typically 30 requests/min for authenticated users)
        # Be mindful if fetching many pages. Add a small delay if necessary.
        # time.sleep(1) # Optional: to be kinder to the API if expecting many pages

    return {"pull_requests": all_pull_requests_data}


# Example usage (optional, for testing this script directly)
if __name__ == "__main__":
    try:
        owner = "owner_name" # Replace with actual owner
        repo = "repo_name"   # Replace with actual repo
        
        print(f"Fetching PRs for {owner}/{repo} (last 7 days, all states)...")
        prs_last_week = list_repository_pull_requests(
            repo_owner=owner,
            repo_name=repo,
            # Default is last 7 days if start/end not provided
        )
        print(f"Found {len(prs_last_week['pull_requests'])} PRs.")
        # for pr in prs_last_week['pull_requests'][:5]:
        #     print(f"  #{pr['number']}: {pr['title']} ({pr['state']}) - Created: {pr['created_at']}")

        print(f"\nFetching PRs for {owner}/{repo} (2024-01-01 to 2024-01-15, open)...")
        prs_date_range_open = list_repository_pull_requests(
            repo_owner=owner,
            repo_name=repo,
            start_date_str="2024-01-01",
            end_date_str="2024-01-15",
            pr_state_filter="open"
        )
        print(f"Found {len(prs_date_range_open['pull_requests'])} open PRs in range.")

    except Exception as e:
        print(f"Error: {str(e)}")