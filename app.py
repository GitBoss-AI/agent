# my_project/agent copy/app.py
import asyncio
import os
import logging

import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import BaseModel
from datetime import datetime, timedelta  # Ensure datetime is imported
from websocket_handler import WebSocketHandler
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from starlette.types import Scope, Receive, Send

import httpx


# Load environment variables
load_dotenv()
ws_handler = WebSocketHandler()

# --- Import your tools ---
try:
    from tools.pr_details import fetch_pull_request_details
    from tools.llm_pr_details import analyze_pr_contributions, PRAnalysis
    from tools.list_repo_pr import list_repository_pull_requests
    from tools.get_contributor_activity import fetch_contributor_activity
    from tools.get_contributors import get_repo_contributors # NEW IMPORT
except ImportError as e:
    print(f"Critical Error importing tools: {e}. Ensure 'tools' directory is in PYTHONPATH or structured as a package.")
    raise

try:
    from jwt_validator import JWTValidator
except ImportError as e:
    print(f"Critical Error importing JWTValidator: {e}. Ensure 'jwt_validator.py' is accessible.")
    raise

# --- Logging Configuration (as before) ---
# ... (keep your existing logging setup)
log_dir = os.getenv("LOG_DIR", "./logs")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
os.makedirs(log_dir, exist_ok=True)
root_logger = logging.getLogger()
if root_logger.hasHandlers(): # Clear existing handlers to prevent duplicate logs on reload
    root_logger.handlers.clear()
root_logger.setLevel(getattr(logging, log_level, logging.INFO))
file_handler = logging.FileHandler(os.path.join(log_dir, "agent_api.log"))
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s"))
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)
logger = logging.getLogger(__name__)
logger.info("Logging configured for agent_api.")


# --- FastAPI Application Setup (as before) ---
app = FastAPI(
    title="GitBoss Agent API",
    description="Provides API endpoints for GitHub repository analysis and contributor activity.",
    version="1.2.0" # Incremented version
)

# --- CORS Middleware (as before) ---
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


# --- Pydantic Models (include all previously defined models + new ContributorItem) ---
class CommitInfo(BaseModel):
    sha: str
    message: str
    html_url: str
    date: datetime
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[List[str]] = None

class PRInfo(BaseModel):
    number: int
    title: str
    description: Optional[str] = None
    state: str
    html_url: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None

class PRActivityDetail(BaseModel):
    type: str
    state: Optional[str] = None
    body: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    html_url: str
    path: Optional[str] = None
    line: Optional[int] = None

class PRWithReviewActivity(BaseModel):
    pr_number: int
    pr_title: str
    pr_html_url: str
    pr_description: Optional[str] = None
    activities: List[PRActivityDetail]

class GeneralPRComment(BaseModel):
    body: str
    created_at: datetime
    html_url: str

class PRWithGeneralComments(BaseModel):
    pr_number: int
    pr_title: str
    pr_html_url: str
    pr_description: Optional[str] = None
    comments: List[GeneralPRComment]

class IssueInfo(BaseModel):
    number: int
    title: str
    description: Optional[str] = None
    state: str
    html_url: str
    created_at: datetime
    closed_at: Optional[datetime] = None

class ContributorActivityResponse(BaseModel):
    total_commits: int
    commits: List[CommitInfo]
    total_lines_changed: int
    unique_files_changed_in_commits: List[str]
    authored_prs: List[PRInfo]
    reviews_and_review_comments: List[PRWithReviewActivity]
    general_pr_comments: List[PRWithGeneralComments]
    created_issues: List[IssueInfo]
    closed_issues_by_user: List[IssueInfo]

class PRListItem(BaseModel):
    number: int
    title: str
    state: str
    url: str
    created_at: datetime

# New model for contributor list item
class ContributorItem(BaseModel):
    username: str
    contributions: int
    avatar_url: Optional[str] = Field(None, examples=["https://avatars.githubusercontent.com/u/1?v=4"])
    profile_url: str = Field(..., examples=["https://github.com/octocat"])

# --- API Endpoints ---

@app.get("/health", summary="Health Check")
async def health_check():
    # ... (implementation as before) ...
    logger.info("Health check endpoint was called.")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/analyze-pr/", response_model=PRAnalysis, summary="Analyze Single Pull Request Contributions")
async def analyze_pull_request_endpoint(
    # ... (implementation as before) ...
    pr_number: int = Query(..., description="The Pull Request number"),
    repo_owner: str = Query(..., description="The owner of the repository"),
    repo_name: str = Query(..., description="The name of the repository"),
):
    try:
        pr_details_data = fetch_pull_request_details(pr_number=pr_number, repo_owner=repo_owner, repo_name=repo_name)
        if not pr_details_data:
            raise HTTPException(status_code=404, detail=f"Details not found for PR #{pr_number}")
        analysis_result = analyze_pr_contributions(pr_details_data)
        return analysis_result
    except ValueError as ve:
        logger.error(f"Value error during single PR analysis for PR #{pr_number}: {str(ve)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error analyzing PR #{pr_number}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")


@app.get("/repository-prs/",response_model=List[PRListItem], summary="List Repository Pull Requests by Date Range")
async def get_repository_prs_endpoint(
    # ... (implementation as before) ...
    repo_owner: str = Query(..., description="Repository owner"),
    repo_name: str = Query(..., description="Repository name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    state: Optional[str] = Query("all", description="Filter by PR state", enum=["all", "open", "closed", "merged"]),
):
    # ... (date validation and logic as before) ...
    try:
        result_dict = list_repository_pull_requests(repo_owner=repo_owner, repo_name=repo_name, start_date_str=start_date, end_date_str=end_date, pr_state_filter=state)
        pull_requests_data = result_dict.get("pull_requests", [])
        return [PRListItem(**pr_data) for pr_data in pull_requests_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching repo PRs for {repo_owner}/{repo_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error listing PRs: {type(e).__name__}")


@app.get("/contributor-activity/", response_model=ContributorActivityResponse, summary="Get Detailed Contributor Activity")
async def get_contributor_activity_endpoint(
    # ... (implementation as before) ...
    repo_owner: str = Query(..., description="Repository owner"),
    repo_name: str = Query(..., description="Repository name"),
    username: str = Query(..., description="GitHub username of the contributor"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
):
    # ... (date validation and logic as before) ...
    try:
        activity_data_dict = fetch_contributor_activity(repo_owner=repo_owner, repo_name=repo_name, contributor_username=username, start_date_str=start_date, end_date_str=end_date)
        return activity_data_dict
    except ValueError as ve:
        logger.error(f"Value error processing contributor activity for {username}: {str(ve)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error fetching contributor activity for {username}: {str(e)}", exc_info=True)
        detail_msg = str(e) if "GitHub API error" in str(e) else f"Internal error processing activity: {type(e).__name__}"
        raise HTTPException(status_code=500, detail=detail_msg)

# --- NEW ENDPOINT for Repository Contributors ---
@app.get(
    "/repository-contributors/",
    response_model=List[ContributorItem], # Returns a list of ContributorItem
    summary="List Repository Contributors",
    description="Fetches a list of contributors for the specified repository, ordered by a number of contributions. Requires JWT authentication."
)
async def list_repository_contributors_endpoint(
    repo_owner: str = Query(..., description="The owner of the repository", example="facebook"),
    repo_name: str = Query(..., description="The name of the repository", example="react"),
):
    try:
        print("GITHUB_TOKEN found:", os.getenv("GITHUB_TOKEN") is not None)
        # The get_repo_contributors tool returns a dict: {"contributors": [...]}
        # We want to return the list of contributors directly.
        result_dict = get_repo_contributors(
            repo_owner=repo_owner,
            repo_name=repo_name
        )
        contributors_data = result_dict.get("contributors", [])
        
        # Convert to list of ContributorItem Pydantic models
        # FastAPI will handle serialization.
        validated_contributors = [ContributorItem(**contrib_data) for contrib_data in contributors_data]
        
        logger.info(f"Successfully fetched {len(validated_contributors)} contributors for {repo_owner}/{repo_name}.")
        return validated_contributors

    except ValueError as ve: # e.g., GitHub token missing from tool
        logger.error(f"Value error fetching contributors for {repo_owner}/{repo_name}: {str(ve)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error fetching contributors for {repo_owner}/{repo_name}: {str(e)}", exc_info=True)
        detail_message = str(e) if "GitHub API error" in str(e) else f"An internal error occurred: {type(e).__name__}"
        raise HTTPException(status_code=500, detail=detail_message)

# --- Run Instructions (as before) ---

# --- Github API endpoints ---
@app.get("/repo/stats")
async def get_repo_stats(
    owner: str = Query(...),
    repo: str = Query(...),
    range: str = Query("week", regex="^(week|month|quarter)$")
):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(500, "GitHub token not set.")

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
            end = start + relativedelta(months=1)
        elif period == "quarter":
            current_month = now.month - 1
            quarter = current_month // 3
            start_month = quarter * 3 + 1 - (offset * 3)
            year_adjust = (start_month - 1) // 12
            start_month = (start_month - 1) % 12 + 1
            start = now.replace(month=start_month, day=1, year=now.year + year_adjust)
            end = start + relativedelta(months=3)
        else:
            raise HTTPException(400, "Invalid range")
        return start.date().isoformat(), end.date().isoformat()

    def percent_change(current: int, previous: int) -> str:
        if previous == 0:
            return "+∞%" if current > 0 else "0%"
        return f"{((current - previous) / previous) * 100:.1f}%"

    async def get_commit_count(client: httpx.AsyncClient, since, until):
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": since, "until": until, "per_page": 100}
        count = 0
        while url:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            count += len(resp.json())
            url = resp.links.get("next", {}).get("url")
            params = None
        return count

    async def get_issue_pr_count(client: httpx.AsyncClient, q):
        url = f"https://api.github.com/search/issues?q={q}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("total_count", 0)

    async def get_review_count(client: httpx.AsyncClient, start, end):
        q = f"repo:{owner}/{repo}+type:pr+created:{start}..{end}"
        url = f"https://api.github.com/search/issues?q={q}&per_page=30"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        total = 0
        for pr in resp.json().get("items", []):
            pr_num = pr.get("number")
            if pr_num:
                rev_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/reviews"
                rev_resp = await client.get(rev_url, headers=headers)
                if rev_resp.status_code == 200:
                    total += len(rev_resp.json())
        return total

    try:
        current_start, current_end = get_time_range(range, 0)
        previous_start, previous_end = get_time_range(range, 1)

        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                get_commit_count(client, current_start, current_end),
                get_commit_count(client, previous_start, previous_end),
                get_issue_pr_count(client, f"repo:{owner}/{repo}+type:pr+created:{current_start}..{current_end}"),
                get_issue_pr_count(client, f"repo:{owner}/{repo}+type:pr+created:{previous_start}..{previous_end}"),
                get_issue_pr_count(client, f"repo:{owner}/{repo}+type:issue+created:{current_start}..{current_end}"),
                get_issue_pr_count(client, f"repo:{owner}/{repo}+type:issue+created:{previous_start}..{previous_end}"),
                get_review_count(client, current_start, current_end),
                get_review_count(client, previous_start, previous_end),
            )

        return {
            "commits": {"count": results[0], "change": percent_change(results[0], results[1])},
            "prs": {"count": results[2], "change": percent_change(results[2], results[3])},
            "issues": {"count": results[4], "change": percent_change(results[4], results[5])},
            "reviews": {"count": results[6], "change": percent_change(results[6], results[7])},
        }

    except Exception as e:
        logger.error(f"Parallel GitHub stats fetch failed: {str(e)}")
        raise HTTPException(500, detail="Failed to fetch repository stats")


@app.get("/repo/contributor-stats", summary="Top Contributors Stats")
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

    async with httpx.AsyncClient(timeout=20) as client:
        # --- STEP 1: Fetch commits ---
        commit_authors = {}
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": since, "until": until, "per_page": 100}

        while url:
            resp = await client.get(url, headers=headers, params=params)
            if not resp.is_success:
                raise HTTPException(status_code=500, detail=f"GitHub error: {resp.text}")
            for commit in resp.json():
                author = commit.get("author")
                if author and author.get("login"):
                    login = author["login"]
                    commit_authors[login] = commit_authors.get(login, 0) + 1
            url = resp.links.get("next", {}).get("url")
            params = None

        top_contributors = sorted(commit_authors.items(), key=lambda x: -x[1])[:limit]

        # --- STEP 2: Fetch PR list (used for reviews) ---
        pr_query = f"repo:{owner}/{repo}+type:pr+created:{since}..{until}"
        pr_search_url = f"https://api.github.com/search/issues?q={pr_query}&per_page=100"
        pr_search_resp = await client.get(pr_search_url, headers=headers)
        pr_items = pr_search_resp.json().get("items", []) if pr_search_resp.is_success else []

        # Build map of PRs to be used in review counting
        pr_numbers = [pr["number"] for pr in pr_items if "number" in pr]

        # --- STEP 3: Concurrency-controlled review counting ---
        semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent requests

        async def count_reviews_by_user(pr_number: int, username: str):
            async with semaphore:
                review_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
                rev_resp = await client.get(review_url, headers=headers)
                if rev_resp.is_success:
                    return sum(1 for r in rev_resp.json() if r.get("user", {}).get("login") == username)
                return 0

        async def fetch_contributor_stats(username: str, commit_count: int):
            # Fetch PR count
            pr_q = f"repo:{owner}/{repo} type:pr author:{username} created:{since}..{until}"
            pr_url = f"https://api.github.com/search/issues?q={pr_q}"
            pr_resp = await client.get(pr_url, headers=headers)
            pr_count = pr_resp.json().get("total_count", 0) if pr_resp.is_success else 0

            # Count matching reviews
            review_counts = await asyncio.gather(*[
                count_reviews_by_user(pr_number, username) for pr_number in pr_numbers
            ])
            return {
                "username": username,
                "commits": commit_count,
                "prs": pr_count,
                "reviews": sum(review_counts),
            }

        contributor_stats = await asyncio.gather(*[
            fetch_contributor_stats(username, count) for username, count in top_contributors
        ])

    return {"contributors": contributor_stats}


@app.get("/repo/team-activity")
async def get_team_activity(
    owner: str = Query(...),
    repo: str = Query(...),
    time_range: str = Query("week", regex="^(week|month|quarter)$")
):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub token not set.")

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    def get_date_bins(period: str):
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        bins = []

        if period == "week":
            for i in range(7):
                day = now - timedelta(days=6 - i)
                bins.append(day.date())
        elif period == "month":
            for i in range(4):
                week_start = now - timedelta(days=(21 - i * 7))
                bins.append(week_start.date())
        elif period == "quarter":
            for i in range(12):
                week_start = now - timedelta(days=(77 - i * 7))
                bins.append(week_start.date())

        return bins

    def bin_label(date_obj):
        return date_obj.strftime("%Y-%m-%d")

    bins = get_date_bins(time_range)
    bin_labels = [bin_label(d) for d in bins]
    activity = {label: {"label": label, "commits": 0, "prs": 0, "reviews": 0} for label in bin_labels}

    def find_bin(date_str: str) -> Optional[str]:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").date()
        except Exception:
            return None
        for d in reversed(bins):
            if date_obj >= d:
                return bin_label(d)
        return None

    async with httpx.AsyncClient(timeout=15) as client:

        async def fetch_commits():
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {"since": bins[0].isoformat(), "per_page": 100}
            while url:
                resp = await client.get(url, headers=headers, params=params)
                if not resp.is_success:
                    break
                for c in resp.json():
                    ts = c.get("commit", {}).get("author", {}).get("date")
                    b = find_bin(ts) if ts else None
                    if b:
                        activity[b]["commits"] += 1
                url = resp.links.get("next", {}).get("url")
                params = None

        async def fetch_prs_and_reviews():
            pr_q = f"repo:{owner}/{repo} type:pr created:>={bins[0].isoformat()}"
            pr_url = f"https://api.github.com/search/issues?q={pr_q}&per_page=100"
            resp = await client.get(pr_url, headers=headers)
            if not resp.is_success:
                return
            pr_items = resp.json().get("items", [])

            for pr in pr_items:
                created_at = pr.get("created_at")
                b = find_bin(created_at)
                if b:
                    activity[b]["prs"] += 1

            async def fetch_review_counts(pr_number: int):
                rev_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
                rev_resp = await client.get(rev_url, headers=headers)
                if rev_resp.is_success:
                    for review in rev_resp.json():
                        submitted_at = review.get("submitted_at")
                        b = find_bin(submitted_at)
                        if b:
                            activity[b]["reviews"] += 1

            await asyncio.gather(*[
                fetch_review_counts(pr["number"]) for pr in pr_items if "number" in pr
            ])

        await asyncio.gather(
            fetch_commits(),
            fetch_prs_and_reviews()
        )

    return {"timeline": list(activity.values())}


@app.get("/repo/recent-activity")
async def get_recent_activity(
    owner: str = Query(..., description="GitHub repo owner"),
    repo: str = Query(..., description="GitHub repo name")
):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub token not set.")

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Parallel fetch for commits and PRs
        commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=5"
        prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=5"

        try:
            commits_resp, prs_resp = await asyncio.gather(
                client.get(commits_url, headers=headers),
                client.get(prs_url, headers=headers)
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"GitHub API request error: {e}")

        commits = commits_resp.json() if commits_resp.status_code == 200 else []
        prs = prs_resp.json() if prs_resp.status_code == 200 else []

        # Parallel fetch of reviews for top 5 PRs
        review_tasks = [
            client.get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}/reviews", headers=headers)
            for pr in prs[:5]
        ]
        review_responses = await asyncio.gather(*review_tasks, return_exceptions=True)

        activity_log = []

        for commit in commits:
            activity_log.append({
                "type": "commit",
                "username": commit["commit"]["author"]["name"],
                "message": commit["commit"]["message"].split("\n")[0],
                "timestamp": commit["commit"]["author"]["date"],
                "url": commit["html_url"]
            })

        for pr in prs:
            activity_log.append({
                "type": "pr",
                "username": pr["user"]["login"],
                "message": f"{pr['user']['login']} {pr['state']} PR: {pr['title']}",
                "timestamp": pr["created_at"],
                "url": pr["html_url"]
            })

        for i, resp in enumerate(review_responses):
            if isinstance(resp, Exception) or not resp.status_code == 200:
                continue
            reviews = resp.json()
            for review in reviews:
                if review.get("submitted_at"):
                    activity_log.append({
                        "type": "review",
                        "username": review["user"]["login"],
                        "message": f"{review['user']['login']} reviewed PR #{prs[i]['number']}",
                        "timestamp": review["submitted_at"],
                        "url": f"https://github.com/{owner}/{repo}/pull/{prs[i]['number']}#pullrequestreview-{review['id']}"
                    })

    activity_log.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"activity": activity_log[:5]}


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