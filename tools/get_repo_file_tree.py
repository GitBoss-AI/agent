import os
import requests
from typing import Dict, List, Any, Optional, Union

def create_tree_structure(tree_data: Dict[str, Any]) -> Dict:
    """
    Convert GitHub API tree data into a structured tree representation.
    Similar to the JS implementation but adapted for Python.
    """
    if not tree_data or 'tree' not in tree_data:
        return {}
    
    root = {}
    
    def add_path_to_tree(tree: Dict, path_parts: List[str], is_file: bool) -> None:
        if not path_parts:
            return
        
        part = path_parts[0]
        remaining = path_parts[1:]
        
        if len(path_parts) == 1 and is_file:
            if 'files' not in tree:
                tree['files'] = []
            tree['files'].append(part)
            tree['files'].sort()
        else:
            if 'directories' not in tree:
                tree['directories'] = {}
            if part not in tree['directories']:
                tree['directories'][part] = {}
            add_path_to_tree(tree['directories'][part], remaining, is_file)
    
    for item in tree_data['tree']:
        if item['type'] == 'commit':
            continue
        
        path_parts = item['path'].split('/')
        is_file = item['type'] == 'blob'
        add_path_to_tree(root, path_parts, is_file)
    
    return root

def get_file_tree(owner: str, repo: str, branch: Optional[str] = None) -> Dict[str, Any]:
    if branch is None:
        branch = 'main'

    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        raise Exception('GitHub token not configured')

    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        error_message = response.json().get('message', 'Unknown error')
        raise Exception(f"GitHub API error (status {response.status_code}): {error_message}")

    data = response.json()
    tree_structure = create_tree_structure(data)  # You must define this function

    return {
        'repository owner': owner,
        'repository name': repo,
        'branch': branch,
        'truncated': data.get('truncated', False),
        'tree': tree_structure
    }

if __name__ == "__main__":
    print(get_file_tree("alpsencer", "infrastack"))