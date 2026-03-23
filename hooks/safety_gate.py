#!/usr/bin/env python3
"""Safety gate hook for the OPAL optimizer plugin.

Intercepts Write, Edit, and Bash tool calls to prevent:
- Overwriting the original monitor config or baseline files
- Deleting optimization results or working files
- Running destructive Observe API calls (DELETE, PATCH on monitors)
- Modifying files outside the /tmp/opal-optimizer/ workspace

Runs as a PreToolUse hook. Reads tool input from stdin as JSON.
Exits 0 to allow, exits 2 to block (with reason on stderr).
"""

import json
import sys
import os

PROTECTED_FILES = [
    "/tmp/opal-optimizer/original_config.json",
    "/tmp/opal-optimizer/baseline.opal",
    "/tmp/opal-optimizer/baseline_results.json",
    "/tmp/opal-optimizer/baseline_timing.txt",
]

ALLOWED_WORKSPACE = "/tmp/opal-optimizer/"


def check_write(tool_input):
    """Check Write tool calls."""
    file_path = tool_input.get("file_path", "")

    # Block overwriting protected files
    for protected in PROTECTED_FILES:
        if file_path == protected:
            return False, f"BLOCKED: Cannot overwrite protected file {file_path}. This is the original baseline data."

    # Warn if writing outside the workspace (but allow it)
    if not file_path.startswith(ALLOWED_WORKSPACE) and not file_path.startswith("/Users/"):
        return False, f"BLOCKED: Write to {file_path} is outside the optimizer workspace ({ALLOWED_WORKSPACE})."

    return True, None


def check_edit(tool_input):
    """Check Edit tool calls."""
    file_path = tool_input.get("file_path", "")

    for protected in PROTECTED_FILES:
        if file_path == protected:
            return False, f"BLOCKED: Cannot edit protected file {file_path}. This is the original baseline data."

    return True, None


def check_bash(tool_input):
    """Check Bash tool calls for destructive operations."""
    command = tool_input.get("command", "")

    # Block DELETE calls to the Observe monitors API
    if "DELETE" in command.upper() and "/v1/monitors/" in command:
        return False, "BLOCKED: Cannot delete monitors via the API. The optimizer should only create new monitors, never delete existing ones."

    # Block PATCH calls to the Observe monitors API (modifying existing monitors)
    if "PATCH" in command.upper() and "/v1/monitors/" in command:
        return False, "BLOCKED: Cannot modify existing monitors via the API. The optimizer should create a new V2 monitor, not modify the original."

    # Block rm of protected files
    for protected in PROTECTED_FILES:
        if f"rm {protected}" in command or f"rm -f {protected}" in command or f"rm -rf {protected}" in command:
            return False, f"BLOCKED: Cannot delete protected file {protected}."

    # Block rm -rf of the entire workspace
    if "rm -rf /tmp/opal-optimizer" in command and "variant" not in command:
        return False, "BLOCKED: Cannot delete the entire optimizer workspace. Use specific file paths."

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
    elif tool_name == "Bash":
        allowed, reason = check_bash(tool_input)
    else:
        sys.exit(0)

    if not allowed:
        print(reason, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
