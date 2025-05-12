# File: my_project/agent copy/app.py

import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional # Added List

from fastapi import FastAPI, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime # Ensure datetime is imported

# Load environment variables
load_dotenv()

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
# --- Health Check Endpoint (as before) ---
@app.get("/health", summary="Health Check", description="Simple health check endpoint.")
async def health_check():
    logger.info("Health check endpoint was called.")
    return {"status": "ok"}

# --- How to Run (as before) ---
# uvicorn app:app --host 0.0.0.0 --port 8003 --reload