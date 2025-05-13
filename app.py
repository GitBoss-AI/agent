# File: my_project/agent copy/app.py

import os
import logging

import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional # Added List

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta  # Ensure datetime is imported
from websocket_handler import WebSocketHandler
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from starlette.types import Scope, Receive, Send

# Load environment variables
load_dotenv()
ws_handler = WebSocketHandler()

# --- Import your tools and validator ---
try:
    from tools.pr_details import fetch_pull_request_details
    from tools.llm_pr_details import analyze_pr_contributions, PRAnalysis
    from tools.list_repo_pr import list_repository_pull_requests # Import the new tool
except ImportError as e:
    print(f"Error importing tools: {e}. Ensure 'tools' directory is in PYTHONPATH or structured as a package.")
    raise

try:
    from jwt_validator import JWTValidator
except ImportError as e:
    print(f"Error importing JWTValidator: {e}. Ensure 'jwt_validator.py' is in the same directory or PYTHONPATH.")
    raise

# --- Logging Configuration (as before) ---
log_dir = os.getenv("LOG_DIR", "./logs")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
os.makedirs(log_dir, exist_ok=True)
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, log_level, logging.INFO))
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
file_handler = logging.FileHandler(os.path.join(log_dir, "agent_api.log"))
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s"))
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)
logger = logging.getLogger(__name__)
logger.info("Logging configured for agent_api.")
logger.info(f"Log level set to: {log_level}")
logger.info(f"Logs will be written to: {os.path.join(log_dir, 'agent_api.log')}")


# --- FastAPI Application Setup ---
app = FastAPI(
    title="GitBoss Agent API",
    description="Provides API endpoints for GitHub repository analysis.",
    version="1.0.0"
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    # Add your deployed frontend URL here
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS middleware configured for origins: {origins}")

# --- Pydantic Models for PR Listing ---
class PRListItem(BaseModel):
    number: int
    title: str
    state: str
    url: str
    created_at: datetime

# --- JWT Authentication Setup (as before) ---
jwt_validator = JWTValidator()
bearer_scheme = HTTPBearer()
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Dict[str, Any]:
    token = credentials.credentials
    logger.debug(f"Attempting to validate token: {token[:20]}...")
    payload = jwt_validator.validate_token(token)
    if payload is None:
        logger.warning("Invalid or expired token provided for API request.")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"API request authenticated for user: {payload.get('username', 'Unknown User')}, ID: {payload.get('sub')}")
    return payload

# --- Existing /analyze-pr/ Endpoint (as before) ---
@app.get(
    "/analyze-pr/",
    response_model=PRAnalysis,
    summary="Analyze Pull Request Contributions",
    # ... (rest of the endpoint definition as provided previously) ...
)
async def analyze_pull_request_endpoint(
    pr_number: int = Query(..., description="The Pull Request number", example=33165),
    repo_owner: str = Query(..., description="The owner of the repository (e.g., 'facebook')", example="facebook"),
    repo_name: str = Query(..., description="The name of the repository (e.g., 'react')", example="react"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User '{current_user.get('username')}' (ID: {current_user.get('sub')}) requesting analysis for PR #{pr_number} in {repo_owner}/{repo_name}")
    try:
        logger.debug(f"Fetching details for PR #{pr_number}...")
        pr_details_data = fetch_pull_request_details(
            pr_number=pr_number, repo_owner=repo_owner, repo_name=repo_name
        )
        if not pr_details_data:
            logger.warning(f"No details found for PR #{pr_number} in {repo_owner}/{repo_name}")
            raise HTTPException(status_code=404, detail=f"Details not found for PR #{pr_number}")
        logger.debug(f"Successfully fetched details for PR #{pr_number}")

        logger.debug(f"Analyzing contributions for PR #{pr_number}...")
        analysis_result = analyze_pr_contributions(pr_details_data)
        logger.info(f"Successfully analyzed PR #{pr_number} for {repo_owner}/{repo_name}")
        return analysis_result
    except ValueError as ve:
        logger.error(f"Value error during PR analysis for PR #{pr_number}: {str(ve)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing PR #{pr_number} for {repo_owner}/{repo_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred while analyzing the PR: {str(e)}")


# --- New Endpoint for Listing Repository PRs ---
@app.get(
    "/repository-prs/",
    response_model=List[PRListItem],
    summary="List Repository Pull Requests by Date Range",
    description="Fetches pull requests from the specified repository created within a given date range (YYYY-MM-DD). Requires JWT authentication."
)
async def get_repository_prs_endpoint(
    repo_owner: str = Query(..., description="The owner of the repository", example="facebook"),
    repo_name: str = Query(..., description="The name of the repository", example="react"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)", example="2024-01-01", regex=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)", example="2024-01-31", regex=r"^\d{4}-\d{2}-\d{2}$"),
    state: Optional[str] = Query("all", description="Filter by PR state: 'all', 'open', 'closed', 'merged'", enum=["all", "open", "closed", "merged"]),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(
        f"User '{current_user.get('username')}' requesting PRs for {repo_owner}/{repo_name} "
        f"from {start_date or 'any'} to {end_date or 'any'}, state: {state}"
    )

    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if start_dt > end_dt:
                raise HTTPException(status_code=400, detail="Start date cannot be after end date.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD.")
    elif start_date:
         try: datetime.strptime(start_date, "%Y-%m-%d")
         except ValueError: raise HTTPException(status_code=400, detail="Invalid start date format. Please use YYYY-MM-DD.")
    elif end_date:
         try: datetime.strptime(end_date, "%Y-%m-%d")
         except ValueError: raise HTTPException(status_code=400, detail="Invalid end date format. Please use YYYY-MM-DD.")


    try:
        result_dict = list_repository_pull_requests(
            repo_owner=repo_owner,
            repo_name=repo_name,
            start_date_str=start_date,
            end_date_str=end_date,
            pr_state_filter=state
        )
        pull_requests_data = result_dict.get("pull_requests", [])
        
        # Convert to list of PRListItem Pydantic models
        validated_prs = [PRListItem(**pr_data) for pr_data in pull_requests_data]
        
        logger.info(f"Successfully fetched {len(validated_prs)} PRs for {repo_owner}/{repo_name}.")
        return validated_prs

    except ValueError as ve:
        logger.error(f"Value error fetching PRs for {repo_owner}/{repo_name}: {str(ve)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error fetching PRs for {repo_owner}/{repo_name}: {str(e)}", exc_info=True)
        # Consider if the full error message should be exposed or a generic one
        detail_message = f"An internal error occurred: {type(e).__name__}"
        if "GitHub API error" in str(e): # Be more specific for known errors
            detail_message = str(e)
        raise HTTPException(status_code=500, detail=detail_message)

# --- Github API endpoints ---
@app.get("/repo/stats", summary="Repository Monthly Stats", description="Returns commit, PR, issue, and review stats for the last month and % difference from the month before.")
async def get_repo_stats(
    owner: str = Query(..., description="GitHub repository owner"),
    repo: str = Query(..., description="GitHub repository name"),
    range: str = Query("week", regex="^(week|month|quarter)$")
):
    logger.info(f"Fetching repo stats for {owner}/{repo}.")

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub token not set in environment.")

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    def get_time_range(period: str, offset: int = 0) -> tuple[str, str]:
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        if period == "week":
            start = now - timedelta(weeks=offset + 1)
            end = now - timedelta(weeks=offset)
        elif period == "month":
            start = (now.replace(day=1) - relativedelta(months=offset + 1)).replace(day=1)
            end = (start + relativedelta(months=1))
        elif period == "quarter":
            current_month = now.month - 1
            quarter = current_month // 3
            start_month = quarter * 3 + 1 - (offset * 3)
            year_adjust = (start_month - 1) // 12
            start_month = (start_month - 1) % 12 + 1
            start = now.replace(month=start_month, day=1, year=now.year + year_adjust)
            end = start + relativedelta(months=3)
        else:
            raise HTTPException(status_code=400, detail="Invalid range")

        return start.date().isoformat(), end.date().isoformat()

    def github_search_count(q: str) -> int:
        url = f"https://api.github.com/search/issues?q={q}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"GitHub API error: {response.text}")
        return response.json().get("total_count", 0)

    def github_commit_count(owner: str, repo: str, since: str, until: str) -> int:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": since, "until": until, "per_page": 100}
        count = 0

        while url:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"GitHub API error: {response.text}")
            commits = response.json()
            count += len(commits)

            if 'next' in response.links:
                url = response.links['next']['url']
                params = None
            else:
                url = None

        return count

    def percentage_change(current: int, previous: int) -> str:
        if previous == 0:
            return "+∞%" if current > 0 else "0%"
        return f"{((current - previous) / previous) * 100:.1f}%"

    def build_summary(metric: str, q_template: str):
        current_start, current_end = get_time_range(range, offset=0)
        previous_start, previous_end = get_time_range(range, offset=1)

        if metric == "Reviews":
            def count_reviews(start, end):
                q = f"repo:{owner}/{repo}+type:pr+created:{start}..{end}"
                url = f"https://api.github.com/search/issues?q={q}&per_page=50"
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"GitHub API error: {response.text}")
                prs = response.json().get("items", [])
                review_total = 0
                for pr in prs:
                    pr_number = pr["number"]
                    rev_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
                    rev_response = requests.get(rev_url, headers=headers)
                    if rev_response.status_code != 200:
                        continue
                    review_total += len(rev_response.json())
                return review_total

            current_count = count_reviews(current_start, current_end)
            previous_count = count_reviews(previous_start, previous_end)

        elif metric == "Commits":
            current_count = github_commit_count(owner, repo, current_start, current_end)
            previous_count = github_commit_count(owner, repo, previous_start, previous_end)

        else:
            q_current = q_template.format(start=current_start, end=current_end)
            q_previous = q_template.format(start=previous_start, end=previous_end)
            current_count = github_search_count(q_current)
            previous_count = github_search_count(q_previous)

        return {
            "metric": metric,
            "count": current_count,
            "change": percentage_change(current_count, previous_count),
        }

    try:
        return {
            "commits": build_summary("Commits", ""),  # handled separately
            "prs": build_summary("Pull Requests", f"repo:{owner}/{repo}+type:pr+created:{{start}}..{{end}}"),
            "issues": build_summary("Issues", f"repo:{owner}/{repo}+type:issue+created:{{start}}..{{end}}"),
            "reviews": build_summary("Reviews", ""),  # handled separately
        }
    except Exception as e:
        logger.error(f"Error fetching stats for {owner}/{repo}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch repository stats.")


@app.get("/repo/contributors/stats", summary="Top Contributors Stats")
async def get_top_contributors_stats(
        owner: str = Query(...),
        repo: str = Query(...),
        range: str = Query("week", regex="^(week|month|quarter)$"),
        limit: int = Query(10)
):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub token not set.")

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    def get_time_range(period: str) -> tuple[str, str]:
        now = datetime.utcnow()
        if period == "week":
            start = now - timedelta(weeks=1)
        elif period == "month":
            start = now - relativedelta(months=1)
        elif period == "quarter":
            start = now - relativedelta(months=3)
        else:
            raise HTTPException(status_code=400, detail="Invalid range")
        return start.isoformat(), now.isoformat()

    since, until = get_time_range(range)

    # Step 1: Get commit authors in the given time frame
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    commit_authors = {}
    params = {"since": since, "until": until, "per_page": 100}
    url = commits_url

    while url:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"GitHub error: {resp.text}")
        for commit in resp.json():
            author = commit.get("author")
            if author and author.get("login"):
                login = author["login"]
                commit_authors[login] = commit_authors.get(login, 0) + 1
        if 'next' in resp.links:
            url = resp.links['next']['url']
            params = None
        else:
            break

    # Step 2: Sort by commits and take top N
    top_contributors = sorted(commit_authors.items(), key=lambda x: -x[1])[:limit]

    # Step 3: Gather PRs and reviews
    contributors_stats = []

    for username, commit_count in top_contributors:
        # PR count
        pr_query = f"repo:{owner}/{repo} type:pr author:{username} created:{since}..{until}"
        pr_url = f"https://api.github.com/search/issues?q={pr_query}"
        pr_resp = requests.get(pr_url, headers=headers)
        pr_count = pr_resp.json().get("total_count", 0) if pr_resp.ok else 0

        # Reviews
        # This is expensive: we search PRs and then fetch reviews
        review_count = 0
        pr_list_url = f"https://api.github.com/search/issues?q=repo:{owner}/{repo}+type:pr+created:{since}..{until}"
        pr_list_resp = requests.get(pr_list_url, headers=headers)
        pr_items = pr_list_resp.json().get("items", []) if pr_list_resp.ok else []

        for pr in pr_items:
            pr_number = pr.get("number")
            if not pr_number:
                continue
            review_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
            rev_resp = requests.get(review_url, headers=headers)
            if not rev_resp.ok:
                continue
            reviews = rev_resp.json()
            review_count += sum(1 for r in reviews if r.get("user", {}).get("login") == username)

        contributors_stats.append({
            "username": username,
            "commits": commit_count,
            "prs": pr_count,
            "reviews": review_count,
        })

    return {"contributors": contributors_stats}


# --- Health Check Endpoint (as before) ---
@app.get("/health", summary="Health Check", description="Simple health check endpoint.")
async def health_check():
    logger.info("Health check endpoint was called.")
    return {"status": "ok"}

@app.websocket_route("/ws-dev")
async def websocket_endpoint(scope: Scope, receive: Receive, send: Send):
    await ws_handler.handle_websocket(scope, receive, send)


# --- How to Run (as before) ---
# uvicorn app:app --host 0.0.0.0 --port 8003 --reload