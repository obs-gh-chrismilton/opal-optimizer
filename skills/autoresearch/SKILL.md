---
name: autoresearch
description: "Autonomous OPAL query optimization loop. Use when the user wants to optimize an Observe OPAL query, improve query performance, reduce execution time, minimize data scanned, or iteratively tune a query. Also trigger when the user mentions 'optimize this query', 'make this faster', 'reduce credits', or 'query performance'."
user-invocable: false
---

# Autoresearch — OPAL Query Optimizer

An autonomous optimization loop that iteratively rewrites OPAL queries, measures performance via the Observe CLI, and keeps improvements. Inspired by Karpathy's autoresearch concept applied to query optimization instead of ML training.

## How It Works

1. You provide an OPAL query, its input dataset(s), and a time range
2. The optimizer runs the query via `~/go/bin/observe query` and captures baseline metrics
3. It rewrites the OPAL with an optimization (tighter filters, fewer groupBys, pre-aggregation, etc.)
4. Runs the rewritten query, compares metrics
5. Keeps the variant if it's better, discards if not
6. Repeats

## Metrics Tracked

- **Execution time** (wall clock seconds) — measured via `time` wrapper
- **Result row count** — from the query output
- **Query complexity** — number of OPAL stages, joins, aggregations

## Usage

- `/optimize-query` — interactive setup, then dispatches the autonomous optimizer agent
- `/optimization-status` — quick terminal check on optimization progress

## Dependencies

- Observe CLI installed at `~/go/bin/observe`
- Observe config at `~/.config/observe.yaml` with a valid profile
- The `/observe` skill for OPAL syntax reference
