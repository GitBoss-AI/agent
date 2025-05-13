# my_project/agent copy/app.py
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

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


# --- JWT Authentication Setup (as before) ---
jwt_validator = JWTValidator()
bearer_scheme = HTTPBearer()
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Dict[str, Any]:
    # ... (implementation as before) ...
    token = credentials.credentials
    payload = jwt_validator.validate_token(token)
    if payload is None:
        logger.warning("Invalid or expired token provided for API request.")
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    logger.info(f"API request authenticated for user: {payload.get('username', 'Unknown')}, ID: {payload.get('sub')}")
    return payload

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
    current_user_payload: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"User '{current_user_payload.get('username')}' requesting analysis for PR #{pr_number} in {repo_owner}/{repo_name}")
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
    current_user_payload: Dict[str, Any] = Depends(get_current_user)
):
    # ... (date validation and logic as before) ...
    logger.info(f"User '{current_user_payload.get('username')}' requesting PRs for {repo_owner}/{repo_name}")
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
    current_user_payload: Dict[str, Any] = Depends(get_current_user)
):
    # ... (date validation and logic as before) ...
    logger.info(f"User '{current_user_payload.get('username')}' requesting activity for '{username}' in {repo_owner}/{repo_name}")
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
    current_user_payload: Dict[str, Any] = Depends(get_current_user) # Protected
):
    logger.info(
        f"User '{current_user_payload.get('username')}' requesting contributors for {repo_owner}/{repo_name}"
    )
    try:
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
# uvicorn app:app --host 0.0.0.0 --port 8003 --reload