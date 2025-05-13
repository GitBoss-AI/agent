# my_project/agent copy/tools/get_contributor_activity.py
import requests
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Set
from dotenv import load_dotenv
import time
import logging

load_dotenv()
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
API_CALL_DELAY = 0.3 # seconds to be kind to the API

# --- Helper function for robust API calls (keep as before) ---
def _make_github_api_request(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=20)
            # Log rate limit info
            # remaining = response.headers.get('X-RateLimit-Remaining')
            # limit = response.headers.get('X-RateLimit-Limit')
            # if remaining and limit:
            #     logger.debug(f"Rate limit: {remaining}/{limit}")
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.warning(f"API request to {url} failed (attempt {retries}/{MAX_RETRIES}): {e}")
            if retries >= MAX_RETRIES:
                logger.error(f"GitHub API error after {MAX_RETRIES} retries for URL {url}: {e}")
                raise
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 403:
                reset_time_str = e.response.headers.get('X-RateLimit-Reset')
                wait_time = RETRY_DELAY * retries * 2 # Default wait
                if reset_time_str:
                    reset_timestamp = int(reset_time_str)
                    current_timestamp = int(time.time())
                    wait_time = max(0, reset_timestamp - current_timestamp) + 5 # Add a small buffer
                logger.warning(f"Rate limit likely hit for {url}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                time.sleep(RETRY_DELAY * retries)
    raise Exception(f"Failed to get response from GitHub API for URL {url} after multiple retries.")


# --- Pydantic-like Dict structures (for clarity, actual Pydantic models in app.py) ---
class CommitInfo(Dict[str, Any]): pass
class PRActivityDetail(Dict[str, Any]): pass # For reviews/comments on a PR
class PRInfo(Dict[str, Any]): pass
class IssueInfo(Dict[str, Any]): pass
class ContributorActivity(Dict[str, Any]): pass


# --- Main Function ---
def fetch_contributor_activity(
    repo_owner: str,
    repo_name: str,
    contributor_username: str,
    start_date_str: str, # YYYY-MM-DD
    end_date_str: str    # YYYY-MM-DD
) -> ContributorActivity:
    if not GITHUB_TOKEN:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")

    logger.info(f"Fetching activity for {contributor_username} in {repo_owner}/{repo_name} from {start_date_str} to {end_date_str}")

    # ISO format for commit 'since'/'until'
    start_datetime_iso_commits = datetime.strptime(start_date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=timezone.utc).isoformat()
    # For 'until', GitHub includes commits up to, but not including, the 'until' timestamp.
    # So, to include the whole end_date_str, we go to the start of the next day.
    end_datetime_iso_commits = (datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)).replace(hour=0, minute=0, second=0, tzinfo=timezone.utc).isoformat()

    # YYYY-MM-DD format for search API 'created:'/'updated:'
    # The search range YYYY-MM-DD..YYYY-MM-DD is inclusive for days.

    activity: ContributorActivity = {
        "total_commits": 0,
        "commits": [],
        "total_lines_changed": 0,
        "unique_files_changed_in_commits": [],
        "authored_prs": [],
        "reviews_and_review_comments": [], # Will store PRs with user's review messages/states
        "general_pr_comments": [],         # Will store PRs with user's general (non-review) comments
        "created_issues": [],
        "closed_issues_by_user": []
    }
    
    unique_files_set: Set[str] = set()

    # 1. Fetch Commits (as before, ensuring commit message is stored)
    logger.info("Fetching commits...")
    commits_list: List[CommitInfo] = []
    page = 1
    while True:
        time.sleep(API_CALL_DELAY)
        commits_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
        params = {
            "author": contributor_username,
            "since": start_datetime_iso_commits,
            "until": end_datetime_iso_commits,
            "per_page": 100,
            "page": page
        }
        try:
            response = _make_github_api_request(commits_url, params=params)
            commits_data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch commits page {page}: {e}")
            break # Stop if commit fetching fails

        if not commits_data:
            break

        for commit_item in commits_data:
            time.sleep(API_CALL_DELAY) # Be kind before fetching commit detail
            commit_detail_url = commit_item["url"]
            additions, deletions = 0, 0
            changed_files_in_commit: List[str] = []
            try:
                commit_detail_response = _make_github_api_request(commit_detail_url)
                commit_detail_data = commit_detail_response.json()
                additions = commit_detail_data.get("stats", {}).get("additions", 0)
                deletions = commit_detail_data.get("stats", {}).get("deletions", 0)
                activity["total_lines_changed"] += (additions + deletions)
                changed_files_in_commit = [file_item["filename"] for file_item in commit_detail_data.get("files", []) if "filename" in file_item]
                for f_name in changed_files_in_commit: unique_files_set.add(f_name)
            except Exception as e_detail:
                logger.warning(f"Failed to fetch details for commit {commit_item['sha']}: {e_detail}")

            commits_list.append({
                "sha": commit_item["sha"],
                "message": commit_item["commit"]["message"], # Commit message already here
                "html_url": commit_item["html_url"],
                "date": commit_item["commit"]["author"]["date"],
                "additions": additions,
                "deletions": deletions,
                "changed_files": changed_files_in_commit
            })

        if len(commits_data) < 100:
            break
        page += 1
    activity["commits"] = commits_list
    activity["total_commits"] = len(commits_list)
    activity["unique_files_changed_in_commits"] = sorted(list(unique_files_set))


    # Helper for paginated search API calls (as before)
    def _search_github_paginated(base_query: str) -> List[Dict[str, Any]]:
        # ... (implementation from previous response, ensure it includes time.sleep(API_CALL_DELAY))
        results: List[Dict[str, Any]] = []
        search_page = 1
        while True:
            time.sleep(API_CALL_DELAY)
            search_params = {
                "q": base_query, "sort": "updated", "order": "desc", # Sort by updated for reviews/comments
                "per_page": 100, "page": search_page
            }
            search_url = "https://api.github.com/search/issues"
            try:
                response = _make_github_api_request(search_url, params=search_params)
                data = response.json()
                items = data.get("items", [])
                if not items: break
                results.extend(items)
                if len(items) < 100: break
                search_page += 1
            except Exception as e_search:
                logger.error(f"Error during GitHub search with query '{base_query}': {e_search}")
                break
        return results

    # 2. Fetch Authored PRs (with description)
    logger.info("Fetching authored PRs...")
    authored_pr_query = f"repo:{repo_owner}/{repo_name} is:pr author:{contributor_username} created:{start_date_str}..{end_date_str}"
    authored_pr_items = _search_github_paginated(authored_pr_query)
    for item in authored_pr_items:
        activity["authored_prs"].append({
            "number": item["number"],
            "title": item["title"],
            "description": item.get("body"), # PR description
            "state": "merged" if item.get("pull_request", {}).get("merged_at") else item["state"],
            "html_url": item["html_url"],
            "created_at": item["created_at"],
            "closed_at": item.get("closed_at"),
            "merged_at": item.get("pull_request", {}).get("merged_at")
        })
    
    # 3. Fetch PRs where user left reviews or review comments (and get those messages)
    logger.info("Fetching PRs reviewed by user...")
    reviewed_pr_query = f"repo:{repo_owner}/{repo_name} is:pr reviewed-by:{contributor_username} updated:{start_date_str}..{end_date_str}"
    reviewed_pr_items = _search_github_paginated(reviewed_pr_query)

    logger.info("Fetching PRs with review comments by user...")
    pr_commenter_query = f"repo:{repo_owner}/{repo_name} is:pr commenter:{contributor_username} updated:{start_date_str}..{end_date_str}"
    commenter_pr_items = _search_github_paginated(pr_commenter_query)

    # Combine and deduplicate based on PR number
    involved_pr_map = {item['number']: item for item in reviewed_pr_items}
    for item in commenter_pr_items:
        if item['number'] not in involved_pr_map:
            involved_pr_map[item['number']] = item
    
    involved_pr_items = list(involved_pr_map.values())
    
    processed_pr_for_reviews_comments = set()

    for item in involved_pr_items:
        pr_number = item["number"]
        if pr_number in processed_pr_for_reviews_comments:
            continue
        processed_pr_for_reviews_comments.add(pr_number)

        pr_activity_details: List[Dict[str, str]] = []

        # Fetch actual reviews by the user on this PR
        pr_reviews_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews"
        review_page = 1
        while True:
            time.sleep(API_CALL_DELAY)
            try:
                reviews_resp = _make_github_api_request(pr_reviews_url, params={"per_page": 100, "page": review_page})
                reviews_data = reviews_resp.json()
                if not reviews_data: break
                for review in reviews_data:
                    if review.get("user", {}).get("login") == contributor_username:
                        review_submitted_at = datetime.strptime(review["submitted_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if start_datetime_iso_commits <= review["submitted_at"] <= end_datetime_iso_commits: # Compare with ISO string
                            pr_activity_details.append({
                                "type": "review",
                                "state": review["state"], # APPROVED, CHANGES_REQUESTED, COMMENTED
                                "body": review.get("body") or "", # Review message
                                "submitted_at": review["submitted_at"],
                                "html_url": review["html_url"]
                            })
                if len(reviews_data) < 100: break
                review_page +=1
            except Exception as e_rev:
                logger.warning(f"Could not fetch reviews for PR #{pr_number}: {e_rev}")
                break
        
        # Fetch actual review comments (on diff) by the user on this PR
        pr_review_comments_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/comments"
        comment_page = 1
        while True:
            time.sleep(API_CALL_DELAY)
            try:
                # The 'since' param here is for comments created after a certain date
                params = {"per_page": 100, "page": comment_page, "since": start_datetime_iso_commits}
                comments_resp = _make_github_api_request(pr_review_comments_url, params=params)
                comments_data = comments_resp.json()
                if not comments_data: break
                for comment in comments_data:
                    if comment.get("user", {}).get("login") == contributor_username:
                        comment_created_at_iso = comment["created_at"]
                        if comment_created_at_iso <= end_datetime_iso_commits: # Check against end date
                             pr_activity_details.append({
                                "type": "review_comment",
                                "body": comment["body"],
                                "created_at": comment["created_at"],
                                "html_url": comment["html_url"],
                                "path": comment.get("path"),
                                "line": comment.get("line") or comment.get("original_line")
                            })
                if len(comments_data) < 100: break
                comment_page += 1
            except Exception as e_comm:
                logger.warning(f"Could not fetch review comments for PR #{pr_number}: {e_comm}")
                break

        if pr_activity_details:
            activity["reviews_and_review_comments"].append({
                "pr_number": pr_number,
                "pr_title": item["title"],
                "pr_html_url": item["html_url"],
                "pr_description": item.get("body"),
                "activities": pr_activity_details
            })

    # 4. Fetch General PR Comments (Issue Comments on a PR)
    logger.info("Fetching general PR comments by user...")
    # Search for PRs where user is a commenter (general comments, not review comments)
    # `is:issue` combined with `commenter` on a PR number also works.
    # The search API `commenter:` on `is:pr` already covers these, but let's specifically fetch them.
    # We will reuse involved_pr_items, but now fetch issue comments for each.
    processed_pr_for_general_comments = set()

    for item in involved_pr_items: # Re-iterate or use a smarter combined loop if performance is key
        pr_number = item["number"]
        if pr_number in processed_pr_for_general_comments:
            continue
        processed_pr_for_general_comments.add(pr_number)
        
        pr_issue_comments_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
        issue_comment_page = 1
        user_general_comments_on_pr: List[Dict[str, str]] = []
        while True:
            time.sleep(API_CALL_DELAY)
            try:
                params = {"per_page": 100, "page": issue_comment_page, "since": start_datetime_iso_commits}
                issue_comments_resp = _make_github_api_request(pr_issue_comments_url, params=params)
                issue_comments_data = issue_comments_resp.json()
                if not issue_comments_data: break
                for comment in issue_comments_data:
                    if comment.get("user", {}).get("login") == contributor_username:
                        comment_created_at_iso = comment["created_at"]
                        if comment_created_at_iso <= end_datetime_iso_commits:
                            user_general_comments_on_pr.append({
                                "body": comment["body"],
                                "created_at": comment["created_at"],
                                "html_url": comment["html_url"]
                            })
                if len(issue_comments_data) < 100: break
                issue_comment_page += 1
            except Exception as e_issue_comm:
                logger.warning(f"Could not fetch issue comments for PR #{pr_number}: {e_issue_comm}")
                break
        
        if user_general_comments_on_pr:
            activity["general_pr_comments"].append({
                "pr_number": pr_number,
                "pr_title": item["title"],
                "pr_html_url": item["html_url"],
                "pr_description": item.get("body"),
                "comments": user_general_comments_on_pr
            })


    # 5. Fetch Created Issues (with description)
    logger.info("Fetching created issues...")
    created_issue_query = f"repo:{repo_owner}/{repo_name} is:issue author:{contributor_username} created:{start_date_str}..{end_date_str}"
    created_issue_items = _search_github_paginated(created_issue_query) # Re-using updated _search_github_paginated
    for item in created_issue_items:
        activity["created_issues"].append({
            "number": item["number"],
            "title": item["title"],
            "description": item.get("body"), # Issue description
            "state": item["state"],
            "html_url": item["html_url"],
            "created_at": item["created_at"],
            "closed_at": item.get("closed_at")
        })
        
    # 6. Fetch Issues Closed by User (with description)
    logger.info("Fetching issues closed by user...")
    closed_issues_query = f"repo:{repo_owner}/{repo_name} is:issue is:closed closed:{start_date_str}..{end_date_str}"
    potentially_closed_items = _search_github_paginated(closed_issues_query) # Re-using updated _search_github_paginated
    
    for item in potentially_closed_items:
        time.sleep(API_CALL_DELAY)
        events_url = item["events_url"]
        events_page = 1
        issue_closed_by_target_user_in_range = False
        while True: 
            time.sleep(API_CALL_DELAY / 2) 
            try:
                events_response = _make_github_api_request(events_url, params={"per_page": 100, "page": events_page})
                events_data = events_response.json()
                if not events_data: break
                for event_item in events_data: # Renamed to avoid conflict
                    if event_item["event"] == "closed" and event_item.get("actor", {}).get("login") == contributor_username:
                        event_created_at_iso = event_item["created_at"]
                        # Compare ISO strings directly for events as they are already in that format.
                        if start_datetime_iso_commits <= event_created_at_iso <= end_datetime_iso_commits:
                             issue_closed_by_target_user_in_range = True
                             break 
                if issue_closed_by_target_user_in_range or len(events_data) < 100: break
                events_page += 1
            except Exception as e_event:
                logger.warning(f"Could not fetch events for issue #{item['number']}: {e_event}")
                break 

        if issue_closed_by_target_user_in_range:
            activity["closed_issues_by_user"].append({
                "number": item["number"],
                "title": item["title"],
                "description": item.get("body"), # Issue description
                "state": "closed",
                "html_url": item["html_url"],
                "created_at": item["created_at"],
                "closed_at": item.get("closed_at") 
            })

    logger.info(f"Finished fetching activity for {contributor_username}.")
    return activity


if __name__ == '__main__':
    # Example usage for direct testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_owner = "facebook"
    test_repo = "react"
    test_user = "sammy-SC" 
    test_start = "2025-05-09" # Use a wider range for testing if octocat has recent activity
    test_end = datetime.now().strftime("%Y-%m-%d")

    if not GITHUB_TOKEN:
        print("Please set GITHUB_TOKEN environment variable for testing.")
    else:
        try:
            print(f"Fetching activity for {test_user} in {test_owner}/{test_repo} from {test_start} to {test_end}")
            result = fetch_contributor_activity(test_owner, test_repo, test_user, test_start, test_end)
            print(result)
            
  
        except Exception as e:
            print(f"An error occurred during test: {e}")
            import traceback
            traceback.print_exc()