# GitHub Contributor Analysis Tool

This tool fetches and analyzes GitHub contributor activity using the GitHub API and Google's Gemini AI.

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the root directory with the following keys:
   ```
   GITHUB_TOKEN=your_github_personal_access_token
   GEMINI_API_KEY=your_gemini_api_key
   ```

   - Get a GitHub personal access token from [GitHub Settings](https://github.com/settings/tokens)
   - Get a Gemini API key from [Google AI Studio](https://ai.google.dev/)

## Usage

### Analyze Contributor Activity

```bash
python -m tools.analyze_contributor [owner] [repo] [username] [start_date] [end_date] [--save-raw]
```

Parameters:
- `owner`: GitHub repository owner (organization or username)
- `repo`: Repository name
- `username`: GitHub username of the contributor to analyze
- `start_date`: Start date in YYYY-MM-DD format
- `end_date`: End date in YYYY-MM-DD format
- `--save-raw`: (Optional) Save the raw activity data to a JSON file

Example:
```bash
python -m tools.analyze_contributor facebook react gaearon 2023-01-01 2023-12-31 --save-raw
```

This will:
1. Fetch the GitHub activity for user "gaearon" in the "facebook/react" repo from Jan 1, 2023 to Dec 31, 2023
2. Process the data into a prompt for Gemini
3. Use Gemini to analyze the contributor's activity and impact
4. Output the analysis to the console
5. Save the raw activity data to a JSON file (if `--save-raw` is specified)

### Get Repository File Tree

```bash
python -m tools.get_repo_file_tree [owner] [repo] [--branch BRANCH] [--output OUTPUT_FILE]
```

Parameters:
- `owner`: GitHub repository owner (organization or username)
- `repo`: Repository name
- `--branch`: (Optional) Repository branch to analyze (defaults to the repository's default branch)
- `--output`: (Optional) Path to save the output as JSON (defaults to printing to console)

Example:
```bash
python -m tools.get_repo_file_tree facebook react --branch main --output react_file_tree.json
```

This will:
1. Fetch the file tree structure of the "facebook/react" repository from the "main" branch
2. Create a hierarchical representation of the directory structure
3. Save the result to "react_file_tree.json"

The output structure looks like:
```json
{
  "repository": "facebook/react",
  "branch": "main",
  "truncated": false,
  "tree": {
    "directories": {
      "src": {
        "directories": {
          "components": {
            "files": ["Component1.js", "Component2.js"]
          }
        },
        "files": ["index.js"]
      },
      "docs": {
        "files": ["README.md"]
      }
    },
    "files": ["LICENSE", "package.json"]
  }
}
```

### Get Repository Issues

```bash
python -m tools.get_repo_issues [owner] [repo] [start_date] [end_date] [--state STATE] [--output OUTPUT_FILE]
```

Parameters:
- `owner`: GitHub repository owner (organization or username)
- `repo`: Repository name
- `start_date`: Start date in YYYY-MM-DD format
- `end_date`: End date in YYYY-MM-DD format
- `--state`: (Optional) Filter by issue state: "all", "open", or "closed" (default: "all")
- `--output`: (Optional) Path to save the output as JSON (defaults to printing to console)

Example:
```bash
python -m tools.get_repo_issues facebook react 2023-01-01 2023-12-31 --state open --output react_issues.json
```

This will:
1. Fetch all open issues from the "facebook/react" repository created between Jan 1, 2023 and Dec 31, 2023
2. Save the results to "react_issues.json"

The output structure looks like:
```json
{
  "repository": "facebook/react",
  "time_period": "2023-01-01 to 2023-12-31",
  "state_filter": "open",
  "total_issues": 42,
  "issues": [
    {
      "id": 1234567890,
      "number": 25000,
      "title": "Issue title",
      "body": "Issue description...",
      "state": "open",
      "created_at": "2023-06-15T14:22:30Z",
      "updated_at": "2023-06-15T15:02:10Z",
      "closed_at": null,
      "html_url": "https://github.com/facebook/react/issues/25000",
      "user": {
        "login": "username",
        "id": 12345,
        "html_url": "https://github.com/username"
      },
      "labels": [
        {"name": "bug", "color": "d73a4a"}
      ]
    },
    // More issues...
  ]
}
```

## Features

The analysis includes:
- Summary of contribution activity and impact
- Key areas of focus based on files changed and commit messages
- The contributor's primary roles (developer, reviewer, etc.)
- Suggestions for broadening impact

## Data Collected

The tool collects the following data for the specified time period:
- Commits (with messages, files changed, and line changes)
- Pull requests authored
- Code reviews and review comments
- General PR comments
- Issues created
- Issues closed 