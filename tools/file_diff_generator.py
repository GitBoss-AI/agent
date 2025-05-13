import os
from typing import List, Dict, Any, Union, Optional
from pydantic import BaseModel, Field
from openai import OpenAI


# Define models for input
class FileContentInput(BaseModel):
    filePath: str
    content: str  # Raw file content with newlines preserved


# Models for diff hunk
class DiffHunk(BaseModel):
    startLine: int
    lineCount: int
    content: str  # Contains the diff content with +/- prefixes
    originalLines: List[str]  # Original lines that are being modified
    newLines: List[str]  # New lines that are being added


# Model for a single file diff
class FileDiff(BaseModel):
    filePath: str
    hunks: List[DiffHunk]


# Model for the complete diff response
class DiffResponse(BaseModel):
    changes: List[FileDiff]
    explanation: str


def generate_diffs(
        file_contents: List[FileContentInput],
        issue_description: str,
        user_prompt: str,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-2024-08-06"
) -> DiffResponse:
    """
    Generate code diffs to solve a specific issue

    Args:
        file_contents: Array of file contents with their paths
        issue_description: Description of the issue to fix
        user_prompt: Additional instructions or context from the user
        api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
        model: OpenAI model to use

    Returns:
        DiffResponse object containing the generated diffs
    """
    try:
        # Use the provided API key or get from environment
        openai_api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError(
                "OpenAI API key is required. Provide it as an argument or set OPENAI_API_KEY environment variable.")

        client = OpenAI(api_key=openai_api_key)

        # Create a formatted string of all file contents with line numbers preserved
        files_context = []
        for file in file_contents:
            lines = file.content.split("\n")
            numbered_lines = "\n".join([f"{index + 1}: {line}" for index, line in enumerate(lines)])
            files_context.append(f"# File: {file.filePath}\n{numbered_lines}")

        files_context_str = "\n\n".join(files_context)

        # Construct the system prompt
        system_prompt = """
You are an expert software developer who specializes in fixing code issues. Your task is to analyze files with line numbers and generate precise Git-style diff patches to solve a specific issue.

Requirements:
1. Examine the provided files with their line numbers carefully
2. Identify the minimal changes needed to resolve the issue
3. Generate changes in standard Git diff format
4. Only modify the necessary lines to fix the issue
5. You must provide changes in the exact format specified below

For your response, provide:
- An array of file changes, where each change includes:
  - filePath: the path to the file being modified
  - hunks: an array of diff "hunks" where each hunk contains:
    - startLine: the line number where the change begins
    - lineCount: the number of lines in the original file being modified
    - content: the complete diff content with proper "+" and "-" prefixes
    - originalLines: array of the original lines being modified (without prefixes)
    - newLines: array of the new lines being added (without prefixes)
- A brief overall explanation of what the changes fix

Example of proper response format:
{
  "changes": [{
    "filePath": "test.js",
    "hunks": [{
      "startLine": 1,
      "lineCount": 2,
      "content": "- function add(a, b) {\\n+ function add(a: number, b: number) {\\n-   return a + b;\\n+   if (typeof a !== 'number' || typeof b !== 'number') {\\n+     throw new Error('Both arguments must be numbers');\\n+   }\\n+   return a + b;",
      "originalLines": [
        "function add(a, b) {",
        "  return a + b;"
      ],
      "newLines": [
        "function add(a: number, b: number) {",
        "  if (typeof a !== 'number' || typeof b !== 'number') {",
        "    throw new Error('Both arguments must be numbers');",
        "  }",
        "  return a + b;"
      ]
    }]
  }],
  "explanation": "Added type checking and input validation to the add function"
}

Your response will be parsed according to this structure, so follow it exactly.
"""

        # Construct the user message
        user_message = f"""
# Issue Description:
{issue_description}

# User Instructions:
{user_prompt}

# Files with Line Numbers:
{files_context_str}
"""

        # Make the API call
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            text_format=DiffResponse,
            temperature=0.1
        )

        if not response.output_parsed:
            raise ValueError("Failed to parse OpenAI response")

        return response.output_parsed

    except Exception as error:
        print(f"Error generating diffs: {error}")
        raise error


def format_git_diff(diff_response: DiffResponse) -> str:
    """
    Format the diff response in traditional Git diff format

    Args:
        diff_response: The parsed diff response from the LLM

    Returns:
        Formatted string in Git diff format
    """
    formatted_diff = f"# Code Changes\n\n{diff_response.explanation}\n\n"

    for file_diff in diff_response.changes:
        formatted_diff += f"diff --git a/{file_diff.filePath} b/{file_diff.filePath}\n"
        formatted_diff += f"--- a/{file_diff.filePath}\n"
        formatted_diff += f"+++ b/{file_diff.filePath}\n"

        for hunk in file_diff.hunks:
            # Calculate the number of lines in the modified version
            modified_lines = len(hunk.newLines)

            formatted_diff += f"@@ -{hunk.startLine},{hunk.lineCount} +{hunk.startLine},{modified_lines} @@\n"

            # Format the diff content with proper prefixes
            for line in hunk.originalLines:
                formatted_diff += f"-{line}\n"
            for line in hunk.newLines:
                formatted_diff += f"+{line}\n"

        formatted_diff += "\n"

    return formatted_diff


def generate_git_diffs(
        file_contents: List[FileContentInput],
        issue_description: str,
        user_prompt: str,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-2024-08-06"
) -> str:
    """
    Helper function to combine generating and formatting diffs

    Args:
        file_contents: Array of file contents with their paths
        issue_description: Description of the issue to fix
        user_prompt: Additional instructions or context from the user
        api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
        model: OpenAI model to use

    Returns:
        Formatted string in Git diff format
    """
    diff_response = generate_diffs(file_contents, issue_description, user_prompt, api_key, model)
    return format_git_diff(diff_response)


# Example usage
if __name__ == "__main__":
    test_files = [
        FileContentInput(
            filePath="test.js",
            content="""function add(a, b) {
  return a + b;
}"""
        )
    ]

    test_issue = "Add input validation to the add function"
    test_prompt = "Add type checking for numbers"

    try:
        git_diff = generate_git_diffs(test_files, test_issue, test_prompt)
        print(git_diff)
    except Exception as error:
        print(f"Error: {error}")
