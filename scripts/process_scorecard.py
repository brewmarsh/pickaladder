import re
import json
import subprocess
import os
import sys

# Regex to find CRAFT blocks and their associated metadata.
# The expected format is:
# Issue: <Type>
# File: <Path>
# [CRAFT]
# <Prompt Content>
# [/CRAFT]
#
# Logic:
# - Look for "Issue:" followed by "High Cognitive Load" or "Low Type Safety".
# - Look for "File:" followed by the file path.
# - Capture everything between [CRAFT] and [/CRAFT] as the prompt.
CRAFT_BLOCK_RE = re.compile(
    r"Issue:\s*(?P<type>High Cognitive Load|Low Type Safety)\n"
    r"File:\s*(?P<file>[^\n]+)\n"
    r"\[CRAFT\]\n(?P<prompt>.*?)\[/CRAFT\]",
    re.DOTALL
)

def check_issue_exists(file_path: str, issue_type: str) -> bool:
    """
    Checks if a GitHub issue for the given file and issue type already exists.
    Uses 'gh issue list' with a search query.
    """
    search_query = f'"{issue_type}" "{file_path}"'
    try:
        # We search for open issues matching the query.
        result = subprocess.run(
            ["gh", "issue", "list", "--search", search_query, "--json", "number"],
            capture_output=True,
            text=True,
            check=True
        )
        issues = json.loads(result.stdout)
        return len(issues) > 0
    except Exception as e:
        print(f"Warning: Failed to check for existing issues: {e}")
        return False

def create_issue(file_path: str, issue_type: str, prompt: str) -> None:
    """
    Creates a new GitHub issue using the CRAFT prompt as the body.
    """
    title = f"Remediation: {issue_type} in {file_path}"
    body = prompt.strip()
    labels = "tech-debt,ai-ready"

    try:
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body, "--label", labels],
            check=True
        )
        print(f"Successfully created issue for {file_path}")
    except Exception as e:
        print(f"Error: Failed to create issue for {file_path}: {e}")

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python process_scorecard.py <scorecard_file>")
        return

    scorecard_path = sys.argv[1]
    if not os.path.exists(scorecard_path):
        print(f"Error: {scorecard_path} not found.")
        return

    with open(scorecard_path, "r") as f:
        content = f.read()

    typing_tasks = []

    # Iterate through all CRAFT blocks found in the scorecard report.
    for match in CRAFT_BLOCK_RE.finditer(content):
        issue_type = match.group("type").strip()
        file_path = match.group("file").strip()
        prompt = match.group("prompt").strip()

        if issue_type == "High Cognitive Load":
            if not check_issue_exists(file_path, issue_type):
                create_issue(file_path, issue_type, prompt)
            else:
                print(f"Issue already exists for {file_path} ({issue_type})")

        elif issue_type == "Low Type Safety":
            typing_tasks.append({
                "file": file_path,
                "prompt": prompt
            })

    # Save type safety tasks for subsequent CI steps.
    if typing_tasks:
        with open("typing_tasks.json", "w") as f:
            json.dump(typing_tasks, f, indent=2)
        print(f"Wrote {len(typing_tasks)} tasks to typing_tasks.json")
    else:
        # Create an empty file if no tasks, to avoid errors in subsequent steps if they expect the file.
        # Or we can just not create it and the workflow can check for existence.
        pass

if __name__ == "__main__":
    main()
