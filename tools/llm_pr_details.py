from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from tools.pr_details import fetch_pull_request_details

pr_details = fetch_pull_request_details(
pr_number=33165,
repo_owner="facebook",
repo_name="react"
)

load_dotenv()



class PRAnalysis(BaseModel):
    prSummary: str = Field(description="A concise summary of the PR purpose and changes")
    contributionAnalysis: str = Field(description="A concise analysis of each contributor's activities and roles")
    linkedIssuesSummary: Optional[str] = Field(None, description="A summary of any linked issues, if present")

def analyze_pr_contributions(pr_details: Dict[str, Any]) -> PRAnalysis:
    """
    Analyze PR contributions using OpenAI
    
    Args:
        pr_details: The output from fetch_pull_request_details function
        
    Returns:
        PRAnalysis: Structured analysis of the PR
    """
    client = OpenAI()
    
    # System prompt that understands the PR data structure
    system_prompt = """
You are analyzing GitHub pull request data with a specific structure. The data includes:

1. Basic PR Information:
   - title: The title of the PR
   - description: Full description of the PR
   - state: Current state (open, closed, merged)
   - created_at: When the PR was created

2. Changed Files:
   - List of files modified in the PR

3. Linked Issues:
   - number: Issue number
   - title: Issue title
   - state: Issue state
   - created_at: When the issue was created
   - author: The username who created the issue
   - labels: Issue labels
   - assignees: People assigned to the issue
   - body: Issue description

4. Contributors:
   - Each contributor has:
     - activities: List of actions they performed (created PR, commented, reviewed, etc.)
     - profile_url: Link to their GitHub profile
     - roles: Their roles in the PR (Author, Reviewer, Assignee, etc.)

Your task is to provide:
1. A concise summary of the PR's purpose based on its title and description
2. A clear analysis of each contributor's activities, highlighting who did what (assignments, comments, reviews, merges)
3. A brief summary of any linked issues

Keep your analysis factual, specific about who did what, and focused on the collaborative process.
"""
    
    try:
        response = client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(pr_details)},
            ],
            text_format=PRAnalysis,
        )
        
        return response.output_parsed
    except Exception as e:
        print(f"Error analyzing PR contributions: {e}")
        raise e

# Example usage
if __name__ == "__main__":
    # Sample PR details (this would come from your fetch_pull_request_details function)
    pr_details = {
        "title": "Performance: remove memory allocations in useReducer",
        "description": "Fixes #12345\n\nThis PR optimizes the useReducer hook by removing unnecessary memory allocations. The changes include:\n- Removed redundant object creation\n- Optimized state updates\n- Added performance tests",
        "state": "merged",
        "created_at": "2024-02-15T10:30:00Z",
        "changed_files": [
            "packages/react-reconciler/src/ReactFiberHooks.js",
            "packages/react-reconciler/src/ReactFiberHooks.old.js",
            "packages/react-reconciler/src/__tests__/ReactFiberHooks-test.js"
        ],
        "linked_issues": [
            {
                "number": 12345,
                "title": "Performance issue in useReducer",
                "state": "open",
                "created_at": "2024-02-10T15:20:00Z",
                "author": {
                    "username": "sophiebits",
                    "profile_url": "https://github.com/sophiebits"
                },
                "labels": ["performance", "bug", "help wanted"],
                "assignees": ["rickhanlonii"],
                "body": "The useReducer hook is causing unnecessary memory allocations in certain scenarios..."
            }
        ],
        "contributors": {
            "rickhanlonii": {
                "activities": [
                    {
                        "type": "created PR",
                        "content": None,
                        "timestamp": "2024-02-15T10:30:00Z"
                    },
                    {
                        "type": "commented",
                        "content": "I've implemented the suggested optimizations. Please review the changes.",
                        "timestamp": "2024-02-15T11:45:00Z"
                    }
                ],
                "profile_url": "https://github.com/rickhanlonii",
                "roles": ["Author"]
            },
            "gaearon": {
                "activities": [
                    {
                        "type": "assigned",
                        "content": None,
                        "timestamp": "2024-02-15T10:35:00Z"
                    },
                    {
                        "type": "reviewed (APPROVED)",
                        "content": "The performance improvements look good. The benchmarks show significant improvement.",
                        "timestamp": "2024-02-15T12:30:00Z"
                    },
                    {
                        "type": "merged",
                        "content": None,
                        "timestamp": "2024-02-15T12:35:00Z"
                    }
                ],
                "profile_url": "https://github.com/gaearon",
                "roles": ["Assignee", "Reviewer", "Merger"]
            },
            "sophiebits": {
                "activities": [
                    {
                        "type": "requested to review",
                        "content": None,
                        "timestamp": "2024-02-15T10:35:00Z"
                    },
                    {
                        "type": "reviewed (COMMENTED)",
                        "content": "Have you considered the edge case where the reducer is called with the same state?",
                        "timestamp": "2024-02-15T11:15:00Z"
                    }
                ],
                "profile_url": "https://github.com/sophiebits",
                "roles": ["Requested Reviewer", "Reviewer"]
            }
        }
    }
    pr_details2 = fetch_pull_request_details(
pr_number=33165,
repo_owner="facebook",
repo_name="react"
)
    print(pr_details2)
    
    analysis = analyze_pr_contributions(pr_details2)
    print(f"PR Summary: {analysis.prSummary}")
    print(f"Contribution Analysis: {analysis.contributionAnalysis}")
    if analysis.linkedIssuesSummary:
        print(f"Linked Issues Summary: {analysis.linkedIssuesSummary}")