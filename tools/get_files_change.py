import json
import os
from typing import List, Union, Dict, Any, Optional
from pydantic import BaseModel
from openai import OpenAI


class FileToChange(BaseModel):
    filePath: str
    reason: str


class FilesToChangeResponse(BaseModel):
    filesToChange: List[FileToChange]
    explanation: Optional[str] = None


def get_files_to_change(
        file_tree: Union[str, Dict[str, Any]],
        issue_description: str
) -> FilesToChangeResponse:
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        system_prompt = """
You are an expert software developer assistant. Your task is to analyze a file tree and an issue description,
then identify which files need to be modified to solve the issue.
Consider:
1. Which files are most likely relevant to the described issue
2. The typical architecture patterns for the kind of project shown in the tree
3. The minimum set of files needed to properly address the issue
Respond with a JSON object that includes:
- An array of files to change, each with a path and reason
- A brief explanation of your overall approach to solving the issue
- In the file Tree I only want the files path in the array without any other text.
"""

        # Handle both raw string or dict-based file tree
        if isinstance(file_tree, str):
            tree_str = file_tree
        elif isinstance(file_tree, dict) and "tree" in file_tree:
            tree_str = json.dumps(file_tree["tree"], indent=2)
        else:
            raise ValueError("Invalid file_tree format. Must be a string or dict with a 'tree' key.")

        user_prompt = f"""
# File Tree:
{tree_str}

# Issue Description:
{issue_description}
"""

        response = client.responses.parse(
            model="gpt-4o-2024-08-06",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            text_format=FilesToChangeResponse,
            temperature=0.1
        )

        return response.output_parsed

    except Exception as error:
        print(f"Error getting files to change: {error}")
        raise


# Example usage
if __name__ == "__main__":
    file_tree = """
src/
  components/
    Button.js
    Input.js
    Form.js
  pages/
    Login.js
    Dashboard.js
  utils/
    auth.js
    validation.js
  App.js
"""
    issue_description = "Users are reporting that after login, they sometimes get redirected to a blank page instead of the dashboard."

    try:
        result = get_files_to_change(file_tree, issue_description)
        print(result.model_dump_json(indent=2))
    except Exception as error:
        print(f"Main error: {error}")
