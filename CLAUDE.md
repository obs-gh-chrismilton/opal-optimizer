# CLAUDE.md

This is a **Claude Code plugin** (not a compiled project). It provides autonomous OPAL query optimization via an iterative test-measure-rewrite loop.

## Project structure

- `plugin.json` — Plugin manifest
- `skills/autoresearch/SKILL.md` — Core skill: optimizer logic and Observe platform knowledge
- `agents/autoresearch-loop.md` — Autonomous optimization loop agent
- `commands/*.md` — User-facing commands (`/optimize-query`, `/clone-monitor`, `/optimization-status`)
- `hooks/safety_gate.py` — PreToolUse safety hook (Python 3)
- `hooks/hooks.json` — Hook configuration

## No build or test system

This plugin is entirely Markdown and one Python script. There is no build step, no test suite, and no linter configured.

## Key conventions

- All runtime data lives in `/tmp/opal-optimizer/` — never write plugin source files there
- Baseline files are **protected** and must not be overwritten: `original_config.json`, `baseline.opal`, `baseline_results.json`, `baseline_timing.txt`
- The safety hook (`hooks/safety_gate.py`) enforces an API allowlist: only `GET /v1/monitors`, `GET /v1/monitors/{id}`, and `POST /v1/monitors` are permitted against the Observe API
- The optimization loop stops after 20 iterations or 5 consecutive discards

## External dependencies

- **Observe CLI** at `~/go/bin/observe` — runs OPAL queries
- **Observe API** — fetches/creates monitor configs
- **Observe config** at `~/.config/observe.yaml` — authentication (customer ID, auth token)
