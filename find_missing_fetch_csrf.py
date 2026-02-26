from __future__ import annotations

"""Utility script to find fetch calls missing CSRF protection."""


import os
from typing import Dict, List, Set


def find_fetch_without_csrf(directory: str = ".") -> Dict[str, List[int]]:
    """
    Finds JavaScript 'fetch' calls that are missing CSRF headers.

    Args:
        directory: The root directory to start scanning from.

    Returns:
        A dictionary mapping file paths to lists of line numbers with violations.
    """
    results: Dict[str, List[int]] = {}
    excluded_dirs: Set[str] = {".git", ".venv", "__pycache__", "node_modules"}

    for root, dirs, files in os.walk(directory):
        # In-place modification of dirs to skip excluded ones
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        _scan_directory_files(root, files, results)

    return results


def _scan_directory_files(
    root: str, files: List[str], results: Dict[str, List[int]]
) -> None:
    """Scan all .js files in a directory."""
    for file in files:
        if file.endswith(".js"):
            path = os.path.join(root, file)
            violations = _scan_file_for_fetch(path)
            if violations:
                results[path] = violations


def _scan_file_for_fetch(file_path: str) -> List[int]:
    """Scans a single file for fetch calls without CSRF headers."""
    violations: List[int] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if "fetch(" in line and not _has_csrf_header(lines, i):
                violations.append(i + 1)
    except (IOError, UnicodeDecodeError):
        pass
    return violations


def _has_csrf_header(lines: List[str], start_idx: int) -> bool:
    """Checks for CSRF token headers in the next 10 lines of a fetch call."""
    lookahead_limit = 10
    end_idx = min(start_idx + lookahead_limit, len(lines))

    for j in range(start_idx, end_idx):
        current_line = lines[j]
        if "X-CSRFToken" in current_line or "csrf_token" in current_line.lower():
            return True
    return False


if __name__ == "__main__":
    import sys

    search_path = sys.argv[1] if len(sys.argv) > 1 else "."
    findings = find_fetch_without_csrf(search_path)

    if not findings:
        print("No violations found.")
    else:
        for filepath, line_numbers in findings.items():
            print(f"{filepath}: Lines {line_numbers}")
