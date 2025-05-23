# my_project/agent copy/app.py
import asyncio
import os
import logging

import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from fastapi import FastAPI, Depends, HTTPException, Query, Security, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import BaseModel
from datetime import datetime, timedelta  # Ensure datetime is imported

from starlette.responses import JSONResponse

from websocket_handler import WebSocketHandler
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from starlette.types import Scope, Receive, Send
from tools.get_repo_issues import get_repo_issues
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict # Ensure Dict is imported
from datetime import datetime



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
    from tools.get_repo_file_tree import get_file_tree
    from tools.get_files_change import get_files_to_change, FilesToChangeResponse, FileToChange
    from tools.get_file_content import get_files_content, FileContentResponse as GetFileContentResponseCP, FileContent as FileContentCP # Aliased to avoid conflict
    from tools.file_diff_generator import FileContentInput, generate_git_diffs
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

class LoginRequest(BaseModel):
    username: str
    password: str


class IssueUser(BaseModel):
    login: str
    id: int
    html_url: str
    avatar_url: str

class IssueLabel(BaseModel):
    name: str
    color: str

class IssueItem(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    html_url: str
    user: IssueUser
    labels: List[IssueLabel]

class RepoIssuesResponse(BaseModel):
    repository: str
    time_period: str
    state_filter: str
    total_issues: int
    issues: List[IssueItem]
    error: Optional[str] = None # To handle potential errors from the script
    status_code: Optional[int] = None # To handle potential errors from the script
    details: Optional[str] = None # To handle potential errors from the script
# --- API Endpoints ---
# --- Pydantic Models for the New Workflow ---

class GenerateIssueSolutionRequest(BaseModel):
    repo_owner: str = Field(..., description="Owner of the repository", example="alpsencer")
    repo_name: str = Field(..., description="Name of the repository", example="infrastack")
    issue_number: int = Field(..., description="The number of the issue to generate a solution for", example=123)
    issue_title: str = Field(..., description="Title of the issue", example="Fix login button")
    issue_description: str = Field(..., description="Full description of the issue")
    # branch: Optional[str] = Field("main", description="Branch to operate on") # Future: allow branch selection

class FileTreeStepResponseData(BaseModel):
    repository_owner: str = Field(alias="repository owner")
    repository_name: str = Field(alias="repository name")
    branch: str
    truncated: bool
    tree: Dict[str, Any]

    class Config:
        populate_by_name = True # Allows using alias for field names

class StepResponse(BaseModel):
    step_name: str
    status: str # "success", "error", "skipped"
    data: Optional[Any] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None

class IssueSolutionOverallResponse(BaseModel):
    message: str
    workflow_id: Optional[str] = None # For potential future tracking
    steps: List[StepResponse]
    final_diff: Optional[str] = None
    error: Optional[str] = None


# --- Pydantic Models (Existing - ensure these are comprehensive for your app) ---
# ... (Keep all your existing Pydantic models: PRListItem, ContributorItem, PRAnalysis etc.)
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

class IssueInfo(BaseModel): # This is a general IssueInfo, might differ from RepoIssuesResponse's IssueItem
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

class ContributorItem(BaseModel):
    username: str
    contributions: int
    avatar_url: Optional[str] = Field(None, examples=["https://avatars.githubusercontent.com/u/1?v=4"])
    profile_url: str = Field(..., examples=["https://github.com/octocat"])

class IssueUser(BaseModel):
    login: str
    id: int
    html_url: str
    avatar_url: str

class IssueLabel(BaseModel):
    name: str
    color: str

class IssueItem(BaseModel): # Used by RepoIssuesResponse
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    html_url: str
    user: IssueUser
    labels: List[IssueLabel]

class RepoIssuesResponse(BaseModel):
    repository: str
    time_period: str
    state_filter: str
    total_issues: int
    issues: List[IssueItem]
    error: Optional[str] = None
    status_code: Optional[int] = None
    details: Optional[str] = None


# --- API Endpoints ---

@app.get("/health", summary="Health Check")
async def health_check():
    # ... (implementation as before) ...
    logger.info("Health check endpoint was called.")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/generate-issue-solution", response_model=IssueSolutionOverallResponse, summary="Generates a potential code solution for a GitHub issue")
async def generate_issue_solution_endpoint(
    request_data: GenerateIssueSolutionRequest,
    #§current_user: dict = Depends(get_current_user)
):
    #user_id = current_user.get("id", "UnknownID") # Get user ID from token
    #logger.info(f"User ID '{user_id}' initiating solution generation for issue #{request_data.issue_number} in {request_data.repo_owner}/{request_data.repo_name}")

    steps_results: List[StepResponse] = []
    start_time_workflow = datetime.now()

    # --- Helper to add step result ---
    def add_step_result(name: str, status: str, data: Optional[Any] = None, error_msg: Optional[str] = None, start_time: datetime = datetime.now()):
        duration = (datetime.now() - start_time).total_seconds() * 1000
        steps_results.append(StepResponse(step_name=name, status=status, data=data, error_message=error_msg, duration_ms=duration))

    # --- Step 1: Get repository file tree ---
    step_name_tree = "Get Repository File Tree"
    start_time_step = datetime.now()
    file_tree_data_raw: Optional[Dict[str, Any]] = None
    try:
        file_tree_data_raw = get_file_tree(
            owner=request_data.repo_owner,
            repo=request_data.repo_name
            # branch=request_data.branch # Add if branch selection is implemented
        )
        # Validate with Pydantic model if desired, or use as dict
        # file_tree_validated = FileTreeStepResponseData(**file_tree_data_raw) 
        add_step_result(step_name_tree, "success", data=file_tree_data_raw, start_time=start_time_step)
        logger.info(f"Step 1 ({step_name_tree}) successful for issue #{request_data.issue_number}.")
    except Exception as e:
        logger.error(f"Error in Step 1 ({step_name_tree}) for issue #{request_data.issue_number}: {str(e)}", exc_info=True)
        add_step_result(step_name_tree, "error", error_msg=str(e), start_time=start_time_step)
        return IssueSolutionOverallResponse(
            message="Workflow failed at 'Get Repository File Tree' step.",
            steps=steps_results,
            error=f"Error getting file tree: {str(e)}"
        )

    # --- Step 2: Identify files to change ---
    step_name_files_change = "Identify Files to Change"
    start_time_step = datetime.now()
    files_to_change_data: Optional[FilesToChangeResponse] = None
    try:
        files_to_change_data = get_files_to_change(
            file_tree=file_tree_data_raw, # Pass the raw dict as it might be what the tool expects
            issue_description=request_data.issue_description
        )
        add_step_result(step_name_files_change, "success", data=files_to_change_data.model_dump(), start_time=start_time_step)
        logger.info(f"Step 2 ({step_name_files_change}) successful for issue #{request_data.issue_number}. Files: {[f.filePath for f in files_to_change_data.filesToChange]}")
        
        if not files_to_change_data.filesToChange:
            logger.warning(f"No files identified to change for issue #{request_data.issue_number}.")
            add_step_result("Generate Git Diffs", "skipped", data="No files were identified as needing changes.")
            return IssueSolutionOverallResponse(
                message="Workflow completed: No files identified for changes.",
                steps=steps_results,
                final_diff="No changes needed."
            )
    except Exception as e:
        logger.error(f"Error in Step 2 ({step_name_files_change}) for issue #{request_data.issue_number}: {str(e)}", exc_info=True)
        add_step_result(step_name_files_change, "error", error_msg=str(e), start_time=start_time_step)
        return IssueSolutionOverallResponse(
            message="Workflow failed at 'Identify Files to Change' step.",
            steps=steps_results,
            error=f"Error identifying files to change: {str(e)}"
        )

    # --- Step 3: Get content of identified files ---
    step_name_content = "Get File Content"
    start_time_step = datetime.now()
    file_content_data: Optional[GetFileContentResponseCP] = None
    try:
        file_paths_to_fetch = [f.filePath for f in files_to_change_data.filesToChange]
        file_content_data = get_files_content(
            repo_owner=request_data.repo_owner,
            repo_name=request_data.repo_name,
            file_paths=file_paths_to_fetch
            # branch=request_data.branch
        )
        add_step_result(step_name_content, "success", data=file_content_data.model_dump(), start_time=start_time_step)
        logger.info(f"Step 3 ({step_name_content}) successful for issue #{request_data.issue_number}. Fetched content for {len(file_content_data.files)} files.")
    except Exception as e:
        logger.error(f"Error in Step 3 ({step_name_content}) for issue #{request_data.issue_number}: {str(e)}", exc_info=True)
        add_step_result(step_name_content, "error", error_msg=str(e), start_time=start_time_step)
        return IssueSolutionOverallResponse(
            message="Workflow failed at 'Get File Content' step.",
            steps=steps_results,
            error=f"Error getting file content: {str(e)}"
        )

    # --- Step 4: Generate git diffs ---
    step_name_diff = "Generate Git Diffs"
    start_time_step = datetime.now()
    git_diff_output: Optional[str] = None
    try:
        file_inputs_for_diff = [
            FileContentInput(filePath=f.path, content=f.content) for f in file_content_data.files
        ]
        # Construct a user prompt for the diff generator.
        user_prompt_for_diff = f"Resolve issue #{request_data.issue_number} titled '{request_data.issue_title}'. The core problem is: {request_data.issue_description.split('.', 1)[0]}"
        
        git_diff_output = generate_git_diffs(
            file_contents=file_inputs_for_diff,
            issue_description=request_data.issue_description,
            user_prompt=user_prompt_for_diff
        )
        add_step_result(step_name_diff, "success", data={"diff": git_diff_output}, start_time=start_time_step) # Wrap diff in a dict for consistency if needed
        logger.info(f"Step 4 ({step_name_diff}) successful for issue #{request_data.issue_number}.")
    except Exception as e:
        logger.error(f"Error in Step 4 ({step_name_diff}) for issue #{request_data.issue_number}: {str(e)}", exc_info=True)
        add_step_result(step_name_diff, "error", error_msg=str(e), start_time=start_time_step)
        return IssueSolutionOverallResponse(
            message="Workflow failed at 'Generate Git Diffs' step.",
            steps=steps_results,
            error=f"Error generating git diffs: {str(e)}"
        )

    workflow_duration = (datetime.now() - start_time_workflow).total_seconds()
    logger.info(f"Issue solution workflow for #{request_data.issue_number} completed in {workflow_duration:.2f} seconds.")
    return IssueSolutionOverallResponse(
        message="Workflow completed successfully.",
        steps=steps_results,
        final_diff=git_diff_output
    )

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

    # Helper: find bin for a date
    def find_bin(date_str):
        date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").date()
        for d in reversed(bins):
            if date_obj >= d:
                return bin_label(d)
        return None

    # Commits
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    url = commits_url
    params = {"since": bins[0].isoformat(), "per_page": 100}
    while url:
        resp = requests.get(url, headers=headers, params=params)
        if not resp.ok:
            break
        for c in resp.json():
            ts = c.get("commit", {}).get("author", {}).get("date")
            b = find_bin(ts) if ts else None
            if b:
                activity[b]["commits"] += 1
        url = resp.links["next"]["url"] if "next" in resp.links else None
        params = None

    # PRs
    pr_q = f"repo:{owner}/{repo} type:pr created:>={bins[0].isoformat()}"
    pr_url = f"https://api.github.com/search/issues?q={pr_q}&per_page=100"
    resp = requests.get(pr_url, headers=headers)
    for pr in resp.json().get("items", []):
        b = find_bin(pr.get("created_at"))
        if b:
            activity[b]["prs"] += 1

    # Reviews (optional — approximated via PR list)
    for pr in resp.json().get("items", []):
        pr_number = pr["number"]
        rev_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        rev_resp = requests.get(rev_url, headers=headers)
        if not rev_resp.ok:
            continue
        for review in rev_resp.json():
            b = find_bin(review.get("submitted_at"))
            if b:
                activity[b]["reviews"] += 1

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

    activity_log = []

    # --- Commits ---
    commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=5"
    commit_resp = requests.get(commit_url, headers=headers)
    if commit_resp.ok:
        for commit in commit_resp.json():
            ts = commit["commit"]["author"]["date"]
            msg = commit["commit"]["message"].split("\n")[0]
            author = commit["commit"]["author"]["name"]
            activity_log.append({
                "type": "commit",
                "username": author,
                "message": msg,
                "timestamp": ts,
                "url": commit.get("html_url")
            })

    # --- PRs ---
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=5"
    pr_resp = requests.get(pr_url, headers=headers)
    if pr_resp.ok:
        for pr in pr_resp.json():
            activity_log.append({
                "type": "pr",
                "username": pr["user"]["login"],
                "message": f"{pr['user']['login']} {pr['state']} PR: {pr['title']}",
                "timestamp": pr["created_at"],
                "url": pr["html_url"]
            })

    # --- Reviews ---
    # We'll fetch reviews of the last 5 PRs only to limit requests
    for pr in pr_resp.json()[:5]:
        pr_number = pr["number"]
        rev_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        rev_resp = requests.get(rev_url, headers=headers)
        if rev_resp.ok:
            for review in rev_resp.json():
                if review.get("submitted_at"):
                    activity_log.append({
                        "type": "review",
                        "username": review["user"]["login"],
                        "message": f"{review['user']['login']} reviewed PR #{pr_number}",
                        "timestamp": review["submitted_at"],
                        "url": f"https://github.com/{owner}/{repo}/pull/{pr_number}#pullrequestreview-{review['id']}"
                    })

    # Sort all activity by timestamp descending
    activity_log.sort(key=lambda x: x["timestamp"], reverse=True)

    # Return last 5 entries
    return {"activity": activity_log[:5]}





# --- Dummy login endpoint ---
@app.post("/login", summary="Basic login accepting any credentials")
async def login(request: LoginRequest = Body(...)):
    logger.info(f"Login accepted for user: {request.username}")
    return JSONResponse(content={
        "message": "Login successful.",
        "username": request.username
    })

@app.options("/login")
async def options_login():
    return JSONResponse(content={"message": "OK"})

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


@app.get(
    "/repository-issues/",
    response_model=RepoIssuesResponse, # Use the Pydantic model
    summary="List Repository Issues by Date Range and State",
    description="Fetches issues from a GitHub repository within a specified time range and state."
)
async def list_repository_issues_endpoint(
    repo_owner: str = Query(..., description="Repository owner", example="facebook"),
    repo_name: str = Query(..., description="Repository name", example="react"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)", regex=r"^\d{4}-\d{2}-\d{2}$"),
    state: Optional[str] = Query("all", description="Filter by issue state", enum=["all", "open", "closed"]),
    # If you're using authentication, uncomment the next line
    # current_user: dict = Depends(get_current_user) # Assuming you have a get_current_user dependency
):
    # logger.info(f"User '{current_user['username']}' requesting issues for {repo_owner}/{repo_name} from {start_date} to {end_date}, state: {state}")
    logger.info(f"Requesting issues for {repo_owner}/{repo_name} from {start_date} to {end_date}, state: {state}") # If no auth

    try:
        # Basic date validation (optional, as your script handles it, but good for early exit)
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        if datetime.strptime(end_date, "%Y-%m-%d") < datetime.strptime(start_date, "%Y-%m-%d"):
            raise ValueError("End date must be after start date.")

        issues_data = get_repo_issues(
            repo_owner=repo_owner,
            repo_name=repo_name,
            start_date=start_date,
            end_date=end_date,
            state=state
        )

        if "error" in issues_data:
             # Log the error from the tool
            logger.error(f"Error from get_repo_issues for {repo_owner}/{repo_name}: {issues_data.get('error')} - Status: {issues_data.get('status_code')} - Details: {issues_data.get('details')}")
            # Re-raise as HTTPException or return a specific Pydantic model with error details
            # For simplicity, we'll let the Pydantic model handle the error fields if present.
            # However, it's often better to raise an HTTPException for client clarity.
            # Example:
            # raise HTTPException(
            #     status_code=issues_data.get("status_code", 500), 
            #     detail=issues_data.get("error", "Failed to fetch issues.")
            # )
            # For now, we'll assume the RepoIssuesResponse model can carry error details
            # If using the model to carry errors, make sure the frontend checks for the 'error' field.
            return RepoIssuesResponse(**issues_data)

        logger.info(f"Successfully fetched {issues_data.get('total_issues', 0)} issues for {repo_owner}/{repo_name}.")
        return RepoIssuesResponse(**issues_data)

    except ValueError as ve:
        logger.error(f"Validation error for issues request {repo_owner}/{repo_name}: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error fetching issues for {repo_owner}/{repo_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {type(e).__name__}")


@app.get("/repo/builds")
async def get_builds(
    owner: str = Query(...),
    repo: str = Query(...),
    range: str = Query("week", regex="^(week|month|quarter)$")
):
    headers = {
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
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
        return start.isoformat(), now.isoformat()

    since_iso, until_iso = get_time_range(range)
    since = datetime.fromisoformat(since_iso)
    until = datetime.fromisoformat(until_iso)

    builds = []
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=100"

    while url:
        response = requests.get(url, headers=headers)
        if not response.ok:
            raise HTTPException(status_code=500, detail="GitHub API error")

        runs = response.json().get("workflow_runs", [])
        for run in runs:
            started_at_str = run.get("run_started_at")
            if not started_at_str:
                continue

            try:
                started_at = datetime.fromisoformat(started_at_str[:-1])
            except Exception:
                continue

            if started_at < since:
                url = None  # Stop paginating if we've gone beyond the range
                break

            if started_at <= until:
                builds.append({
                    "id": run["id"],
                    "status": run.get("conclusion"),
                    "duration_seconds": (
                        datetime.fromisoformat(run["updated_at"][:-1]) - started_at
                    ).seconds,
                    "started_at": started_at_str,
                    "build_url": run["html_url"],
                    "triggered_by": run["actor"]["login"] if run.get("actor") else "unknown"
                })

        if url:  # Only fetch next page if still paginating
            url = response.links.get("next", {}).get("url")

    return builds