# fetch_user_pull_requests_tool.py
import requests
import json

# Assume these are globally available, e.g., from a config.py
# from config import REPO_OWNER, REPO_NAME, GITHUB_ACCESS_TOKEN
# For demonstration, placeholders:
REPO_OWNER_GLOBAL = "default_owner"
REPO_NAME_GLOBAL = "default_repo"
GITHUB_ACCESS_TOKEN = "YOUR_GITHUB_TOKEN" # IMPORTANT: Replace with your token

class FetchUserPullRequestsTool:
    """
    Fetches PRs associated with a user.
    """
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {GITHUB_ACCESS_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

    def execute(self, username: str, period: str, repository_owner: str = None, repository_name: str = None, role: str = None, status: str = None):
        """
        Inputs:
            username (string): The GitHub username.
            period (string): Time period in "YYYY-MM-DD:YYYY-MM-DD" format.
            repository_owner (string, optional): Owner of the repository. Defaults to global REPO_OWNER.
            repository_name (string, optional): Name of the repository. Defaults to global REPO_NAME.
            role (string, optional): Role of the user (e.g., "author", "assignee", "mentions", "commenter", "involves"). Defaults to "involves".
            status (string, optional): Status of the PR (e.g., "open", "merged", "closed").
        Outputs: List of PR objects.
        """
        owner = repository_owner or REPO_OWNER_GLOBAL
        repo = repository_name or REPO_NAME_GLOBAL

        query_parts = [f"is:pr", f"repo:{owner}/{repo}"]

        if role:
            query_parts.append(f"{role}:{username}")
        else:
            query_parts.append(f"involves:{username}") # Default role

        if period:
            try:
                start_date, end_date = period.split(':')
                # GitHub search API uses '..' for date range for 'created', 'merged', 'closed' fields
                # Assuming period refers to creation date for simplicity
                query_parts.append(f"created:{start_date}..{end_date}")
            except ValueError:
                return {"error": "Invalid period format. Use YYYY-MM-DD:YYYY-MM-DD"}

        if status:
            if status == "merged": # GitHub API uses is:merged or state:closed for merged PRs in some contexts
                 query_parts.append(f"is:{status}")
            else:
                 query_parts.append(f"state:{status}")


        search_query = " ".join(query_parts)
        params = {"q": search_query, "per_page": 100} # Max 100 per page for search

        try:
            response = requests.get(f"{self.base_url}/search/issues", headers=self.headers, params=params)
            response.raise_for_status()
            search_results = response.json()
            
            prs_output = []
            for item in search_results.get("items", []):
                # Ensure it's a PR (search can return issues and PRs)
                if "pull_request" in item:
                    pr_details = {
                        "title": item.get("title"),
                        "url": item.get("html_url"),
                        "number": item.get("number"),
                        "state": item.get("state"), # "open", "closed" (merged PRs are 'closed')
                        "repository": f"{owner}/{repo}", # item.repository_url might point to API
                        "author": item.get("user", {}).get("login"),
                        "created_at": item.get("created_at"),
                        "merged_at": None, # Requires separate call or specific check
                        "closed_at": item.get("closed_at"),
                        "description": item.get("body", "")
                    }
                    # For merged_at, GitHub API state is 'closed' for merged PRs.
                    # A PR is merged if its `merged_at` field is not null.
                    # The search API might not directly return `merged_at` for all items.
                    # We might need to fetch individual PR to get this accurately if not present.
                    # For now, we will check if the state is closed and there's a closed_at timestamp.
                    # A more robust way is to fetch the PR individually if merged_at is critical.
                    # Let's assume if state is "closed" and "merged" was requested or implied, it's merged.
                    # The general PR object for a merged PR has a `merged_at` field.
                    # The search result item might not have it directly, you might need to fetch /repos/{owner}/{repo}/pulls/{pull_number}

                    # Simplified: if status was 'merged' and this PR is 'closed', we list it.
                    # Actual `merged_at` might need an additional API call per PR.
                    # For the example, let's try to get it if available.
                    # The pull_request object within the issue item might have merge details
                    # but often this is just a URL.
                    # For this example, we'll leave merged_at as potentially None from search.
                    # If a PR is merged, its state becomes "closed".

                    if item.get("pull_request", {}).get("merged_at"):
                        pr_details["merged_at"] = item["pull_request"]["merged_at"]
                        pr_details["state"] = "merged" # More explicit state for output

                    prs_output.append(pr_details)
            return prs_output
        except requests.exceptions.RequestException as e:
            return {"error": f"API request failed: {str(e)}", "details": e.response.text if e.response else "No response"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}

if __name__ == '__main__':
    tool = FetchUserPullRequestsTool()
    # Replace with actual test data
    # user_prs = tool.execute(username="Alperen", period="2025-05-01:2025-05-08", repository_owner="test-owner", repository_name="test-repo", role="author", status="merged")
    # print(json.dumps(user_prs, indent=2))
    print("FetchUserPullRequestsTool: Requires a running GitHub instance and valid token/repo/user for a live test.")
    print("Example usage structure provided in the class.")
    # Expected structure of one item in the output list:
    # {
    #   "title": "Feature: Implement new dashboard", "url": "...", "number": 123,
    #   "state": "merged", "repository": "owner/repo", "author": "Alperen",
    #   "created_at": "2025-05-01T10:00:00Z", "merged_at": "...", "closed_at": "...",
    #   "description": "Full description of the pull request, including its purpose, changes, and any related issue links."
    # }