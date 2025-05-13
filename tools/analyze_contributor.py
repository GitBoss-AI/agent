import os
import json
from typing import Dict, Any, List
import google.generativeai as genai
from dotenv import load_dotenv
from tools.get_contributor_activity import fetch_contributor_activity

# Load environment variables
load_dotenv()

# Configure the Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

def create_prompt_from_activity(activity_data: Dict[str, Any]) -> str:
    """
    Create a prompt for Gemini based on contributor activity data
    """
    # Extract key stats for the prompt
    total_commits = activity_data["total_commits"]
    total_lines = activity_data["total_lines_changed"]
    files_changed = len(activity_data["unique_files_changed_in_commits"])
    authored_prs = len(activity_data["authored_prs"])
    review_prs = len(activity_data["reviews_and_review_comments"])
    commented_prs = len(activity_data["general_pr_comments"])
    created_issues = len(activity_data["created_issues"])
    closed_issues = len(activity_data["closed_issues_by_user"])
    
    prompt = f"""
input structure:
{
    "total_commits": 0,
    "commits": [
        {
            "sha": "commit_sha",
            "message": "commit message",
            "html_url": "https://github.com/...",
            "date": "ISO timestamp",
            "additions": 10,
            "deletions": 5,
            "changed_files": ["path/to/file1.ext", "path/to/file2.ext"]
        },
        # More commits...
    ],
    "total_lines_changed": 0,
    "unique_files_changed_in_commits": ["path/to/file1.ext", "path/to/file2.ext"],
    "authored_prs": [
        {
            "number": 123,
            "title": "PR title",
            "description": "PR description",
            "state": "open/closed/merged",
            "html_url": "https://github.com/...",
            "created_at": "ISO timestamp",
            "closed_at": "ISO timestamp",
            "merged_at": "ISO timestamp"
        },
        # More PRs...
    ],
    "reviews_and_review_comments": [
        {
            "pr_number": 123,
            "pr_title": "PR title",
            "pr_html_url": "https://github.com/...",
            "pr_description": "PR description",
            "activities": [
                {
                    "type": "review",
                    "state": "APPROVED/CHANGES_REQUESTED/COMMENTED",
                    "body": "Review message",
                    "submitted_at": "ISO timestamp",
                    "html_url": "https://github.com/..."
                },
                {
                    "type": "review_comment",
                    "body": "Comment message",
                    "created_at": "ISO timestamp",
                    "html_url": "https://github.com/...",
                    "path": "path/to/file.ext",
                    "line": 42
                },
                # More activities...
            ]
        },
        # More PRs with reviews...
    ],
    "general_pr_comments": [
        {
            "pr_number": 123,
            "pr_title": "PR title",
            "pr_html_url": "https://github.com/...",
            "pr_description": "PR description",
            "comments": [
                {
                    "body": "Comment message",
                    "created_at": "ISO timestamp",
                    "html_url": "https://github.com/..."
                },
                # More comments...
            ]
        },
        # More PRs with comments...
    ],
    "created_issues": [
        {
            "number": 123,
            "title": "Issue title",
            "description": "Issue description",
            "state": "open/closed",
            "html_url": "https://github.com/...",
            "created_at": "ISO timestamp",
            "closed_at": "ISO timestamp"
        },
        # More issues...
    ],
    "closed_issues_by_user": [
        {
            "number": 123,
            "title": "Issue title",
            "description": "Issue description",
            "state": "closed",
            "html_url": "https://github.com/...",
            "created_at": "ISO timestamp",
            "closed_at": "ISO timestamp"
        },
        # More issues...
    ]
}
"""
    
    # Add detailed information about commits (limited to avoid token limits)
    if activity_data["commits"]:
        prompt += "\nSample commit messages:\n"
        commit_samples = activity_data["commits"][:10]  # Limit to 10 samples
        for commit in commit_samples:
            # Get first line of commit message
            message_first_line = commit["message"].split("\n")[0]
            prompt += f"- {message_first_line}\n"
    
    # Add some PR titles
    if activity_data["authored_prs"]:
        prompt += "\nSample PRs authored:\n"
        pr_samples = activity_data["authored_prs"][:5]  # Limit to 5 samples
        for pr in pr_samples:
            prompt += f"- {pr['title']}\n"
    
    # Add some issue information
    if activity_data["created_issues"]:
        prompt += "\nSample issues created:\n"
        issue_samples = activity_data["created_issues"][:5]  # Limit to 5 samples
        for issue in issue_samples:
            prompt += f"- {issue['title']}\n"
    
    # Add file paths changed (limited sample)
    if activity_data["unique_files_changed_in_commits"]:
        prompt += "\nSample files changed:\n"
        file_samples = activity_data["unique_files_changed_in_commits"][:15]  # Limit to 15 samples
        for file_path in file_samples:
            prompt += f"- {file_path}\n"
            
    return prompt

def analyze_contributor_activity(
    repo_owner: str,
    repo_name: str,
    contributor_username: str,
    start_date: str,
    end_date: str,
    save_activity_to_file: bool = False
) -> Dict[str, Any]:
    """
    Fetch and analyze contributor activity using Gemini API
    
    Args:
        repo_owner: GitHub repository owner
        repo_name: GitHub repository name
        contributor_username: GitHub username of the contributor
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        save_activity_to_file: Whether to save raw activity data to a file
        
    Returns:
        Dictionary containing analysis and raw activity data
    """
    # Fetch contributor activity
    activity_data = fetch_contributor_activity(
        repo_owner, 
        repo_name, 
        contributor_username, 
        start_date, 
        end_date
    )
    
    # Save raw activity data to file if requested
    if save_activity_to_file:
        filename = f"{contributor_username}_{repo_owner}_{repo_name}_{start_date}_to_{end_date}.json"
        with open(filename, 'w') as f:
            json.dump(activity_data, f, indent=2)
        print(f"Raw activity data saved to {filename}")
    
    # Create prompt for Gemini
    prompt = create_prompt_from_activity(activity_data)
    
    # Call Gemini API for analysis
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    
    # Return results
    return {
        "contributor": contributor_username,
        "repo": f"{repo_owner}/{repo_name}",
        "period": f"{start_date} to {end_date}",
        "analysis": response.text,
        "raw_activity": activity_data
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze GitHub contributor activity")
    parser.add_argument("owner", help="GitHub repository owner")
    parser.add_argument("repo", help="GitHub repository name")
    parser.add_argument("username", help="GitHub username of the contributor")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--save-raw", action="store_true", help="Save raw activity data to file")
    
    args = parser.parse_args()
    
    try:
        result = analyze_contributor_activity(
            args.owner,
            args.repo,
            args.username,
            args.start_date,
            args.end_date,
            args.save_raw
        )
        
        print("\n=== CONTRIBUTOR ANALYSIS ===\n")
        print(f"Contributor: {result['contributor']}")
        print(f"Repository: {result['repo']}")
        print(f"Period: {result['period']}")
        print("\n=== ANALYSIS ===\n")
        print(result['analysis'])
        
    except Exception as e:
        print(f"An error occurred: {e}") 