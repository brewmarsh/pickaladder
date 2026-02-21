#!/usr/bin/env python3
import subprocess
import json
import re
import os
import sys

# Regex Explanation:
# SECTION_PATTERN:
# - Matches headers like '### High Cognitive Load: file.py' or '### Low Type Safety: file.py'
# - Uses (High Cognitive Load|Low Type Safety) to capture the issue type.
# - Matches everything following the header until the next '### ' or the end of the file.
# - re.DOTALL ensures that '.' matches newlines.
SECTION_PATTERN = re.compile(
    r'### (High Cognitive Load|Low Type Safety): (.*?)\n(.*?)(?=\n### |$)',
    re.DOTALL
)

# PROMPT_PATTERN:
# - Extracts the text following 'CRAFT Prompt:' within a captured section.
# - Captures everything until the end of that section's content.
PROMPT_PATTERN = re.compile(
    r'CRAFT Prompt:\n(.*?)$',
    re.DOTALL
)

def check_issue_exists(title):
    """
    Checks if a GitHub issue with the exact title already exists.
    Uses 'gh issue list' with a title-specific search.
    """
    try:
        # Search for the title in the repository's issue list.
        # We wrap the title in quotes for an exact match.
        result = subprocess.run(
            ['gh', 'issue', 'list', '--search', f'"{title}" in:title', '--json', 'number'],
            capture_output=True, text=True, check=True
        )
        issues = json.loads(result.stdout)
        return len(issues) > 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If 'gh' is not installed or fails (e.g., no auth), we assume it doesn't exist
        # but log the event if not in a CI environment.
        if not os.environ.get('GITHUB_ACTIONS'):
            print(f"Warning: Could not check for existing issue '{title}'.")
        return False
    except Exception as e:
        print(f"Error checking for issue existence: {e}")
        return False

def create_github_issue(title, body):
    """
    Creates a new GitHub issue with the 'tech-debt' and 'ai-ready' labels.
    If the issue already exists, it skips creation to avoid duplicates.
    """
    if check_issue_exists(title):
        print(f"Skipping: Issue '{title}' already exists.")
        return

    try:
        subprocess.run(
            ['gh', 'issue', 'create',
             '--title', title,
             '--body', body,
             '--label', 'tech-debt,ai-ready'],
            check=True
        )
        print(f"Successfully created issue: {title}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error creating issue '{title}': {e}")

def main():
    scorecard_path = 'scorecard.txt'
    if not os.path.exists(scorecard_path):
        print(f"Error: {scorecard_path} not found. Please run the scorecard first.")
        sys.exit(1)

    with open(scorecard_path, 'r') as f:
        content = f.read()

    typing_tasks = []

    # Iterate through each issue section found in the scorecard output
    for match in SECTION_PATTERN.finditer(content):
        issue_type = match.group(1)
        file_path = match.group(2).strip()
        section_body = match.group(3).strip()

        # Try to find a specific CRAFT Prompt block
        prompt_match = PROMPT_PATTERN.search(section_body)
        if prompt_match:
            prompt = prompt_match.group(1).strip()
        else:
            # Fallback to the whole section body if 'CRAFT Prompt:' prefix is missing
            prompt = section_body

        if issue_type == "High Cognitive Load":
            # For high cognitive load, we create a GitHub Issue
            title = f"Refactor High Cognitive Load in {file_path}"
            create_github_issue(title, prompt)
        elif issue_type == "Low Type Safety":
            # For low type safety, we queue it for automatic remediation
            typing_tasks.append({
                'file': file_path,
                'prompt': prompt
            })

    # Export typing tasks to JSON for the next workflow step
    with open('typing_tasks.json', 'w') as f:
        json.dump(typing_tasks, f, indent=2)

    print(f"Processing complete. {len(typing_tasks)} typing tasks written to typing_tasks.json.")

if __name__ == "__main__":
    main()
