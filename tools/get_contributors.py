import requests
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_repo_contributors(
    repo_owner: str,
    repo_name: str,
    per_page: int = 100  # Increase default page size
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch contributors for a GitHub repository.
    
    Args:
        repo_owner: Repository owner/organization name
        repo_name: Repository name
        per_page: Number of records per page (max 100)
        
    Returns:
        Dictionary containing a list of contributor objects
    """
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        raise ValueError("GitHub token not found. Please set GITHUB_TOKEN in .env file.")
    
    # Make API request to get contributors with pagination
    contributors = []
    page = 1
    
    while True:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contributors?per_page={per_page}&page={page}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
            
        page_data = response.json()
        
        # Break if no more results
        if not page_data:
            break
            
        for contributor in page_data:
            contributors.append({
                "username": contributor["login"],
                "contributions": contributor["contributions"],
                "avatar_url": contributor["avatar_url"],
                "profile_url": contributor["html_url"]
            })
        
        # Check if we've received less than the requested per_page
        if len(page_data) < per_page:
            break
            
        # Move to next page
        page += 1
        
    return {"contributors": contributors}

# Example usage
if __name__ == "__main__":
    try:
        # Example: Get contributors for tensorflow/tensorflow
        contributors = get_repo_contributors(
            repo_owner="tensorflow",
            repo_name="tensorflow"
        )
        
        print(f"\nFound {len(contributors['contributors'])} contributors:")
        for i, contributor in enumerate(contributors['contributors'], 1):
            print(f"{i}. {contributor['username']} - {contributor['contributions']} contributions")
            
    except Exception as e:
        print(f"Error: {str(e)}") 