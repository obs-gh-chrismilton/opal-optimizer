#!/usr/bin/env python3
"""Safety gate hook for the OPAL optimizer plugin.

Intercepts Write, Edit, NotebookEdit, and Bash tool calls with a tiered
permission model:

TIER 1 — Always blocked (no override):
  - Overwriting protected baseline files
  - Deleting the entire optimizer workspace

TIER 2 — Auto-approved (autonomous loop can proceed):
  - Writes/edits to /tmp/opal-optimizer/ workspace files (variants, results,
    best.opal, dashboard, etc.)
  - Non-destructive Bash commands
  - Allowed Observe API calls (GET monitors, POST new monitor)

TIER 3 — Requires explicit human approval per instance:
  - Destructive Bash commands (rm, rm -rf, kill, etc.)
  - Writes outside the optimizer workspace
  - Non-allowlisted Observe API calls

Human approval works via a token file at /tmp/opal-optimizer/.approvals.
Each line is a single-use approval token. The gate consumes (removes) the
token after use.

To approve a blocked operation, the human runs:
    echo '<token>' >> /tmp/opal-optimizer/.approvals

Runs as a PreToolUse hook. Reads tool input from stdin as JSON.
Exits 0 to allow, exits 2 to block (with reason on stderr).
"""

import hashlib
import json
import os
import re
import sys

PROTECTED_FILES = [
    "/tmp/opal-optimizer/original_config.json",
    "/tmp/opal-optimizer/baseline.opal",
    "/tmp/opal-optimizer/baseline_results.json",
    "/tmp/opal-optimizer/baseline_timing.txt",
]

ALLOWED_WORKSPACE = "/tmp/opal-optimizer/"
APPROVALS_FILE = "/tmp/opal-optimizer/.approvals"

# Allowlisted API operations: (HTTP_METHOD, URL_PATTERN)
# Anything hitting observeinc.com that doesn't match one of these is blocked.
ALLOWED_API_OPS = [
    ("GET", r"/v1/monitors(/\d+)?$"),       # Read monitor(s)
    ("POST", r"/v1/monitors$"),              # Create new monitor
]

# Destructive command patterns that require human approval
DESTRUCTIVE_PATTERNS = [
    r'\brm\b',           # rm (file deletion)
    r'\brmdir\b',        # rmdir (directory deletion)
    r'\bunlink\b',       # unlink (file deletion)
    r'\bkill\b',         # kill (process termination)
    r'\bkillall\b',      # killall (process termination)
    r'\bpkill\b',        # pkill (process termination)
    r'\bmv\b.*/',        # mv (moving/renaming can be destructive)
    r'\btruncate\b',     # truncate (file truncation)
    r'\bshred\b',        # shred (secure deletion)
    r'\bdd\b',           # dd (raw disk/file writes)
    r'\b>\s*/tmp/',      # redirect overwrite to /tmp (but not >>)
]


def make_approval_token(action_description):
    """Create a short, deterministic approval token for an action."""
    return hashlib.sha256(action_description.encode()).hexdigest()[:12]


def check_approval(action_description):
    """Check if a human has approved this specific action via the token file.

    Each approval is single-use: the token is removed after consumption.
    Returns True if approved, False otherwise.
    """
    token = make_approval_token(action_description)

    if not os.path.exists(APPROVALS_FILE):
        return False

    try:
        with open(APPROVALS_FILE, "r") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return False

    # Look for the token (strip whitespace from each line)
    remaining = []
    found = False
    for line in lines:
        if line.strip() == token and not found:
            found = True  # Consume this token (don't add to remaining)
        else:
            remaining.append(line)

    if found:
        # Rewrite the file without the consumed token
        try:
            with open(APPROVALS_FILE, "w") as f:
                f.writelines(remaining)
        except (IOError, OSError):
            pass  # Token was found, allow even if cleanup fails

    return found


def block_with_approval(reason, action_description):
    """Block an action but provide instructions for human approval."""
    token = make_approval_token(action_description)
    return False, (
        f"BLOCKED: {reason}\n"
        f"This operation requires explicit human approval.\n"
        f"To approve, the human should run:\n"
        f"    echo '{token}' >> /tmp/opal-optimizer/.approvals\n"
        f"Then retry the operation.\n"
        f"(Token is for: {action_description})"
    )


def is_observe_api_call(command):
    """Check if a bash command contains an Observe API call."""
    return "observeinc.com" in command and "curl" in command.lower()


def is_destructive_command(command):
    """Check if a bash command contains destructive operations."""
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command):
            return True
    return False


def check_api_call(command):
    """Validate an Observe API call against the allowlist."""
    # Extract the HTTP method
    method = "GET"  # curl default
    if "-X " in command or "--request " in command:
        method_match = re.search(r'(?:-X|--request)\s+(\w+)', command)
        if method_match:
            method = method_match.group(1).upper()
    elif "-d " in command or "--data " in command or "-d@" in command:
        method = "POST"  # curl with data defaults to POST

    # Extract the URL path
    url_match = re.search(r'https?://[^/\s]+(/v1/[^\s"\']+)', command)
    if not url_match:
        # Has observeinc.com but no /v1/ path — might be a non-API URL, allow it
        return True, None

    url_path = url_match.group(1).rstrip("'\"")

    # Check against allowlist
    for allowed_method, allowed_pattern in ALLOWED_API_OPS:
        if method == allowed_method and re.match(allowed_pattern, url_path):
            return True, None

    # Not in allowlist — require human approval
    action_desc = f"API call: {method} {url_path}"
    return block_with_approval(
        f"{method} {url_path} is not an allowed API operation. "
        f"The optimizer can only: GET /v1/monitors, GET /v1/monitors/{{id}}, "
        f"POST /v1/monitors (create new).",
        action_desc
    )


def check_write(tool_input):
    """Check Write tool calls."""
    file_path = tool_input.get("file_path", "")

    # TIER 1: Protected files — always blocked
    for protected in PROTECTED_FILES:
        if file_path == protected:
            return False, (
                f"BLOCKED: Cannot overwrite protected file {file_path}. "
                f"This is the original baseline data and cannot be modified."
            )

    # TIER 2: Workspace files — auto-approved
    if file_path.startswith(ALLOWED_WORKSPACE):
        return True, None

    # TIER 3: Outside workspace — requires human approval
    action_desc = f"Write to: {file_path}"
    return block_with_approval(
        f"Write to {file_path} is outside the optimizer workspace "
        f"({ALLOWED_WORKSPACE}).",
        action_desc
    )


def check_edit(tool_input):
    """Check Edit tool calls."""
    file_path = tool_input.get("file_path", "")

    # TIER 1: Protected files — always blocked
    for protected in PROTECTED_FILES:
        if file_path == protected:
            return False, (
                f"BLOCKED: Cannot edit protected file {file_path}. "
                f"This is the original baseline data and cannot be modified."
            )

    # TIER 2: Workspace files — auto-approved
    if file_path.startswith(ALLOWED_WORKSPACE):
        return True, None

    # TIER 3: Outside workspace — requires human approval
    action_desc = f"Edit: {file_path}"
    return block_with_approval(
        f"Edit to {file_path} is outside the optimizer workspace "
        f"({ALLOWED_WORKSPACE}).",
        action_desc
    )


def check_notebook_edit(tool_input):
    """Check NotebookEdit tool calls."""
    notebook_path = tool_input.get("notebook_path", "")

    # TIER 2: Workspace files — auto-approved
    if notebook_path.startswith(ALLOWED_WORKSPACE):
        return True, None

    # TIER 3: Outside workspace — requires human approval
    action_desc = f"NotebookEdit: {notebook_path}"
    return block_with_approval(
        f"NotebookEdit to {notebook_path} is outside the optimizer workspace "
        f"({ALLOWED_WORKSPACE}).",
        action_desc
    )


def check_bash(tool_input):
    """Check Bash tool calls."""
    command = tool_input.get("command", "")

    # Check Observe API calls against allowlist
    if is_observe_api_call(command):
        allowed, reason = check_api_call(command)
        if not allowed:
            return False, reason

    # TIER 1: Block rm -rf of the entire workspace — always denied
    if "rm -rf /tmp/opal-optimizer" in command and "variant" not in command:
        return False, (
            "BLOCKED: Cannot delete the entire optimizer workspace. "
            "This is always denied. Use specific file paths."
        )

    # TIER 1: Block deletion of protected files — always denied
    for protected in PROTECTED_FILES:
        if (f"rm {protected}" in command
                or f"rm -f {protected}" in command
                or f"rm -rf {protected}" in command):
            return False, (
                f"BLOCKED: Cannot delete protected file {protected}. "
                f"This is the original baseline data and cannot be deleted."
            )

    # TIER 3: Destructive commands require human approval
    if is_destructive_command(command):
        # Check if human has pre-approved this specific command
        action_desc = f"Destructive bash: {command[:120]}"
        if check_approval(action_desc):
            return True, None
        return block_with_approval(
            f"Destructive command detected. Write and delete operations "
            f"can ONLY be used with explicit permission by the human for "
            f"each instance.",
            action_desc
        )

    return True, None


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name == "Write":
        allowed, reason = check_write(tool_input)
    elif tool_name == "Edit":
        allowed, reason = check_edit(tool_input)
    elif tool_name == "NotebookEdit":
        allowed, reason = check_notebook_edit(tool_input)
    elif tool_name == "Bash":
        allowed, reason = check_bash(tool_input)
    else:
        # Read, Grep, Glob, LS, WebFetch, WebSearch — always allowed
        sys.exit(0)

    if not allowed:
        print(reason, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
