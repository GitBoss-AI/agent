import os
import sys
from typing import List, Dict, Any, Optional

# Make sure all tools are in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all required modules
from tools.get_repo_file_tree import get_file_tree
from tools.get_files_change import get_files_to_change, FilesToChangeResponse
from tools.get_file_content import get_files_content
from tools.file_diff_generator import FileContentInput, generate_git_diffs

repo_owner = "alpsencer"
repo_name = "infrastack"

issue_description = """Goal:
Improve the conciseness and clarity of the UI by shortening the title of our main issues view in the Activity Bar.

Current Behavior:
The view displaying GitHub issues under the "InfraStack" Activity Bar container is titled "InfraStack GitHub Issues".

Desired Behavior:
The title of this view should be changed to simply "GitHub Issues". The context that it's part of the "InfraStack" extension is already clear from its placement within our custom Activity Bar container.

Reasoning:
- Reduces redundancy, as "InfraStack" is already the name of the sidebar container.
- Makes the UI cleaner and less cluttered.
- "GitHub Issues" is a standard and easily recognizable term.

Files to be Modified:
- package.json: The name property for the view contribution under contributes.views["infrastack-sidebar-container"] (or similar path) needs to be updated.

Example (Illustrative change in package.json):
// package.json
...
    "views": {
      "infrastack-sidebar-container": [
        {
          "id": "infrastack.issuesView",
-         "name": "InfraStack GitHub Issues",  // Current title
+         "name": "GitHub Issues",             // Desired new title
          "type": "tree",
          "icon": "resources/issues-icon.svg"
        },
...

Acceptance Criteria:
- When the extension is active, the view within the "InfraStack" sidebar container that lists GitHub issues is titled "GitHub Issues".
- This is a straightforward change, mostly involving an update to the package.json file.
"""

# Step 1: Get file tree 
print("Getting repository file tree...")
file_tree_response = get_file_tree(repo_owner, repo_name)
# Convert tree to string format for the LLM
print(file_tree_response)

# Step 2: Get files to change
files_to_change = get_files_to_change(file_tree_response, issue_description)
print(files_to_change)

# Step 3: Get file content
file_content = get_files_content(repo_owner, repo_name, files_to_change.filesToChange)
print(file_content)

# Step 4: Generate git diffs
git_diffs = generate_git_diffs(file_content, issue_description, "Update the package.json to change the view name from 'InfraStack GitHub Issues' to 'GitHub Issues'")
print(git_diffs)
