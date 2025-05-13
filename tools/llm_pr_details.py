from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from pr_details import fetch_pull_request_details

load_dotenv()



class PRAnalysis(BaseModel):
    prSummary: str = Field(description="A concise summary of the PR's purpose based on its title and description")
    linkedIssuesSummary: Optional[str] = Field(None, description="A brief summary of any linked issues, if present")
    # discussionSummary: str = Field(description="A brief summary of the discussion focusing on contributors and their activities")
    contributionAnalysis: str = Field(description="A brief summary of contributors' contributions to this PR and their roles (assignments, comments, reviews, merges, comment reviews)")

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

{
    "title": str,  # Title of the pull request
    "description": str,  # Full description/body of the PR
    "state": str,  # Current state of PR (open, closed, merged)
    "created_at": str,  # ISO timestamp of PR creation
    "changed_files": List[str],  # List of file paths that were modified
    
    "linked_issues": List[{
        "number": int,  # Issue number
        "title": str,  # Issue title
        "state": str,  # Issue state (open, closed)
        "created_at": str,  # Issue creation timestamp
        "author": {
            "username": str,  # Author's GitHub username
            "profile_url": str  # Author's GitHub profile URL
        },
        "labels": List[str],  # List of issue labels
        "assignees": List[str],  # List of assigned usernames
        "body": str  # Full issue description
        "url": str  # Full issue URL
    }],
    
    "contributors": {
        "username": {  # GitHub username as key
            "activities": List[{
                "type": str,  # Type of activity (created PR, reviewed, commented, etc.)
                "content": str,  # Full text content of the activity
                "timestamp": str,  # When the activity occurred
                "review_id": int,  # Present only for reviews
                "path": str,  # Present only for review comments (file path)
                "line": int,  # Present only for review comments (line number)
                "position": int  # Present only for review comments (position in diff)
            }],
            "roles": List[str],  # List of roles (Author, Reviewer, Assignee, etc.)
            "profile_url": str  # Contributor's GitHub profile URL
        }
    }
}

Your task is to provide:
1. A concise summary of the PR's purpose based on its title and description
2. A brief summary of any linked issues
3. A summary of contributors contribution to this PR. Write the contributors' roles after their name in parentheses, write the category (feature additions, bug fixes, refactoring, documentation, commenting, reviewing, merging, etc.,) before explaining any contribution with bullet points under the contributor's name.


If a contrubutor is assigned to any and has not mentioned this in the contribution analysis yet, please do so. Do not talk too general. Read the description carefully and provide the spesific details in a concise manner.
If you are referring to contributors or linked issues, make sure you provide the url link as a href link on its name. Provide the categories, code pieces, issue numbers, contributor names as a bold.
Make the links another color. 
Provide the output in markdown format. Only provide the md file without any other text.
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