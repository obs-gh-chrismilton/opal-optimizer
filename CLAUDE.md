# CLAUDE.md

This is a **Claude Code plugin** (not a compiled project). It provides autonomous OPAL query optimization via an iterative test-measure-rewrite loop.

## Project structure

- `plugin.json` — Plugin manifest
- `skills/autoresearch/SKILL.md` — Core skill: optimizer logic and Observe platform knowledge
- `agents/autoresearch-loop.md` — Autonomous optimization loop agent
- `commands/*.md` — User-facing commands (`/optimize-query`, `/clone-monitor`, `/optimization-status`, `/verify-setup`)
- `hooks/safety_gate.py` — PreToolUse safety hook (Python 3)
- `hooks/hooks.json` — Hook configuration

## No build or test system

This plugin is entirely Markdown and one Python script. There is no build step, no test suite, and no linter configured.

## Tool access model

The agent has **unrestricted access to all read tools**: `Read`, `Grep`, `Glob`, `LS`, `WebFetch`, `WebSearch`. Write tools (`Write`, `Edit`, `NotebookEdit`, `Bash`) are gated by `hooks/safety_gate.py`.

### Three-tier permission model

| Tier | Behavior | Examples |
|------|----------|---------|
| **Tier 1 — Always blocked** | No override possible | Overwriting protected baseline files; deleting the entire workspace |
| **Tier 2 — Auto-approved** | Autonomous loop proceeds freely | Writes/edits within `/tmp/opal-optimizer/`; non-destructive Bash; allowlisted API calls |
| **Tier 3 — Human approval required** | Blocked until the human provides a single-use approval token | Destructive Bash (`rm`, `kill`, etc.); writes outside workspace; non-allowlisted API calls |

### Human approval mechanism

Destructive operations (deletes, removes, kills, etc.) can **ONLY** be used with explicit permission by the human for **each instance** requested. The gate is programmatic:

1. The safety hook blocks the operation and prints an approval token
2. The human runs: `echo '<token>' >> /tmp/opal-optimizer/.approvals`
3. The agent retries — the hook consumes the token (single-use) and allows the operation

Approval tokens are deterministic (SHA-256 of the action description) so the same action always produces the same token.

## Key conventions

- All runtime data lives in `/tmp/opal-optimizer/` — never write plugin source files there
- Baseline files are **protected** and must not be overwritten: `original_config.json`, `baseline.opal`, `baseline_results.json`, `baseline_timing.txt`
- The safety hook (`hooks/safety_gate.py`) enforces an API allowlist: only `GET /v1/monitors`, `GET /v1/monitors/{id}`, and `POST /v1/monitors` are permitted against the Observe API
- The optimization loop stops after 20 iterations or 5 consecutive discards

## External dependencies

- **Observe CLI** at `~/go/bin/observe` — runs OPAL queries
- **Observe API** — fetches/creates monitor configs
- **Observe config** at `~/.config/observe.yaml` — authentication (customer ID, auth token)
