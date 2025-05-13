import requests
import os
from typing import List, Dict
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_repo_contributors() -> List[Dict]:
    """
    Fetch contributors of a GitHub repository using environment variables.
    
    Returns:
        List[Dict]: List of contributors with their details
    """
    # Get environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    repo_owner = os.getenv('REPO_OWNER')
    repo_name = os.getenv('REPO_NAME')
    
    # Validate environment variables
    if not all([github_token, repo_owner, repo_name]):
        raise ValueError("Missing environment variables. Please ensure GITHUB_TOKEN, REPO_OWNER, and REPO_NAME are set in .env file.")
    
    # GitHub API endpoint for contributors
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contributors"
    
    # Headers with authentication
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        contributors = response.json()
        
        # Extract relevant information for each contributor
        contributor_list = []
        for contributor in contributors:
            contributor_info = {
                "username": contributor["login"],
                "contributions": contributor["contributions"],
                "profile_url": contributor["html_url"],
                "avatar_url": contributor["avatar_url"]
            }
            contributor_list.append(contributor_info)
            
        return contributor_list
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching contributors: {e}")
        return []

def main():
    try:
        # Fetch contributors using environment variables
        contributors = get_repo_contributors()
        
        if contributors:
            print(f"\nContributors for {os.getenv('REPO_OWNER')}/{os.getenv('REPO_NAME')}:")
            print(json.dumps(contributors, indent=2))
        else:
            print("No contributors found or an error occurred.")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 