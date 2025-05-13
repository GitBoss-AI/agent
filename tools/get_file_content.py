import os
import requests
import base64
from typing import Dict, List, Any, Union, Optional
from pydantic import BaseModel

class FileContent(BaseModel):
    path: str
    content: str
    size: int

class FileContentResponse(BaseModel):
    files: List[FileContent]
    repoOwner: str
    repoName: str
    total_files_count: int

def get_repository_files(repo_owner: str, repo_name: str, branch: str = "main", 
                        path: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
    """
    Get a list of all files in a repository with pagination support.
    
    Args:
        repo_owner: GitHub repository owner/username
        repo_name: Repository name
        branch: Branch name (defaults to 'main')
        path: Path to specific directory (defaults to repository root)
        recursive: Whether to fetch files recursively from subdirectories
        
    Returns:
        List of dictionaries containing file information
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        raise Exception('GitHub token not configured')
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Start with an initial URL
    if recursive:
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees/{branch}?recursive=1"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code != 200:
            error_message = response.json().get('message', 'Unknown error')
            raise Exception(f"GitHub API error (status {response.status_code}): {error_message}")
        
        data = response.json()
        
        # Extract all file entries (type=blob)
        files = [item for item in data.get('tree', []) if item.get('type') == 'blob']
        return files
    else:
        # Non-recursive, navigate through directories
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}?ref={branch}"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code != 200:
            error_message = response.json().get('message', 'Unknown error')
            raise Exception(f"GitHub API error (status {response.status_code}): {error_message}")
        
        data = response.json()
        
        # Handle case when response is a list (directory) or a single file
        if isinstance(data, list):
            return [item for item in data if item.get('type') == 'file']
        elif data.get('type') == 'file':
            return [data]
        
        return []

def get_file_content_paginated(repo_owner: str, repo_name: str, file_path: str, 
                              branch: str = "main", chunk_size: int = 1024 * 1024) -> str:
    """
    Fetches content of a potentially large file with pagination.
    For very large files that exceed GitHub's API limits.
    
    Args:
        repo_owner: GitHub repository owner/username
        repo_name: Repository name
        file_path: Path to the file
        branch: Branch name (defaults to 'main')
        chunk_size: Maximum size of each chunk in bytes
        
    Returns:
        Complete file content as string
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        raise Exception('GitHub token not configured')
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3.raw'  # Get raw content instead of JSON
    }
    
    # For large files, we use the raw API endpoint
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}?ref={branch}"
    
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        error_message = "Unknown error"
        try:
            error_message = response.json().get('message', 'Unknown error')
        except:
            error_message = response.text
        raise Exception(f"GitHub API error (status {response.status_code}) for file {file_path}: {error_message}")
    
    # For regular size files, GitHub returns JSON with base64 content
    try:
        data = response.json()
        if isinstance(data, dict) and 'content' in data:
            encoded_content = data.get('content', '')
            return base64.b64decode(encoded_content.replace('\n', '')).decode('utf-8')
    except:
        # For raw content response, just return the text
        return response.text

def get_files_content(repo_owner: str, repo_name: str, file_paths: Optional[List[str]] = None, 
                      branch: str = "main", max_files: int = 50) -> FileContentResponse:
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        raise Exception('GitHub token not configured')

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    files = []
    total_files = 0

    if file_paths is None:
        all_repo_files = get_repository_files(repo_owner, repo_name, branch)  # You must define this
        total_files = len(all_repo_files)
        file_paths = [file_info['path'] for file_info in all_repo_files[:max_files]]
    else:
        total_files = len(file_paths)

    for file_path in file_paths:
        try:
            content = get_file_content_paginated(repo_owner, repo_name, file_path, branch)  # You must define this
            files.append(FileContent(path=file_path, content=content, size=len(content)))
        except Exception as e:
            print(f"Error fetching {file_path}: {str(e)}")
            continue

    return FileContentResponse(
        files=files,
        repoOwner=repo_owner,
        repoName=repo_name,
        total_files_count=total_files
    )


# Example usage
if __name__ == "__main__":
    
        # Example 1: Fetching specific files
    file_paths = ["README.md", "infrastack/.gitignore"]
    result = get_files_content("alpsencer", "infrastack", file_paths)
    print(result)
