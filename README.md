# OPAL Optimizer — Claude Code Plugin

An autonomous OPAL query optimization plugin for Claude Code. Give it a query, and it iteratively rewrites the OPAL, measures execution performance via the Observe CLI, keeps improvements, and discards regressions. Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) concept, applied to query optimization instead of ML training.

## What It Does

You hand it an OPAL query that runs against an Observe environment. The optimizer:

1. Runs the query and captures baseline metrics (execution time, row count, query complexity)
2. Analyzes the query using Observe platform knowledge — identifies bottlenecks like unaccelerated datasets, high-cardinality groupBys, expensive joins, or missing early filters
3. Rewrites the OPAL with a targeted optimization
4. Runs the rewritten query and measures the same metrics
5. Keeps the variant if it's faster (and semantically equivalent), discards if not
6. Repeats autonomously until interrupted

The optimizer doesn't guess blindly. It understands Observe's query execution model — acceleration, indexed columns, correlation tags, tdigest operations, join behavior — and makes informed decisions about what to change.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)
- [Observe CLI](https://github.com/observeinc/observe) — install with:
  ```bash
  go install github.com/observeinc/observe@latest
  ```
- Observe CLI configured with a valid profile at `~/.config/observe.yaml`:
  ```yaml
  profile:
    default:
      customerid: "<YOUR_CUSTOMER_ID>"
      site: "observeinc.com"
      authtoken: "<YOUR_AUTH_TOKEN>"
  ```
- (Optional) Observe MCP servers configured in Claude Code for richer dataset exploration

## Installation

Add the plugin to your Claude Code settings. Open `~/.claude/settings.json` and merge:

```json
{
  "enabledPlugins": {
    "opal-optimizer@obs-gh-chrismilton": true
  },
  "extraKnownMarketplaces": {
    "obs-gh-chrismilton": {
      "source": {
        "source": "github",
        "repo": "obs-gh-chrismilton/opal-optimizer"
      }
    }
  }
}
```

Restart Claude Code or run `/reload-plugins`.

### Verify Installation

```
/optimize-query
```

If the command is recognized, you're set.

## Usage

### Start an Optimization Run

```
/optimize-query
```

The command walks you through:
1. Paste your OPAL query (or describe what you want optimized)
2. Specify the input dataset(s)
3. Set a time range (defaults to `-r 1h` for fast iterations)
4. Optionally provide an optimization focus (e.g., "reduce groupBy cardinality" or "find an accelerated dataset")

It runs the baseline, generates an HTML dashboard, and dispatches the autonomous optimizer agent.

### Check Progress

```
/optimization-status
```

Shows the current best execution time, recent iterations, keep/discard counts, and the current best query.

### Monitor in the Browser

The HTML dashboard (generated during setup) auto-refreshes every 15 seconds and shows:
- Execution time chart over iterations
- Summary stats (best time, total iterations, keeps/discards)
- Full iteration history table
- Current best OPAL query

### Stop the Optimizer

Press `Esc` or `Ctrl+C` to interrupt the autonomous loop. The current best query is saved at `/tmp/opal-optimizer/best.opal` and the full history is in `/tmp/opal-optimizer/results.tsv`.

## How It Optimizes

The optimizer combines Observe Integration Engineer expertise with iterative measurement. Before making changes, it analyzes the query and input datasets to understand why a query is slow.

### What It Looks For

- **Unaccelerated datasets** — checks if an accelerated or optimized variant exists (e.g., `Derived Span Metrics V4 Optimized` instead of `Derived Span Metrics`)
- **Missing early filters** — filters should appear before aggregations to reduce data volume
- **High-cardinality groupBys** — unnecessary dimensions that explode the number of unique groups
- **Expensive joins** — `leftjoin` scans the entire right-side dataset; narrowing it helps
- **Inefficient patterns** — `sort + limit` instead of `topk`, complex regex where simple matches suffice, redundant stages

### Optimization Techniques (by typical impact)

| Impact | Technique |
|--------|-----------|
| Highest | Switch to an accelerated/optimized dataset |
| Highest | Add early filters on indexed/enum columns |
| High | Reduce groupBy cardinality |
| High | Use `topk` instead of `sort + limit` |
| High | Pre-filter before histogram operations |
| Medium | Combine adjacent filters |
| Medium | Remove unused `make_col` statements |
| Medium | Simplify regex patterns |
| Low | Remove dead code and unused variables |
| Low | Inline single-use stage variables |

## Tool Access

The optimizer uses two tools for interacting with Observe:

**Observe CLI** (`~/go/bin/observe`):
- Runs OPAL queries directly with timing measurement
- Lists and inspects datasets for schema information
- Samples data to understand column structure

**Observe MCP servers** (if configured):
- Explores the knowledge graph for correlation tags, metrics, and dataset relationships
- Discovers indexed/enum columns
- Finds related or alternative datasets

MCP servers are not required. The optimizer works with the CLI alone. If MCP is available for the target environment, it uses it for richer dataset discovery alongside the CLI for execution.

## Plugin Structure

```
opal-optimizer/
├── plugin.json                          # Plugin manifest
├── README.md                            # This file
├── skills/
│   └── autoresearch/
│       └── SKILL.md                     # Context skill for query optimization
├── agents/
│   └── autoresearch-loop.md             # Autonomous optimizer agent
└── commands/
    ├── autoresearch.md                  # /optimize-query setup command
    └── autoresearch-status.md           # /optimization-status quick check
```

## Companion Skill: Observe CLI

This plugin works well alongside the [Observe CLI skill](https://github.com/observeinc/observe-claude-code-skill-example), which teaches Claude Code how to use the Observe CLI for general querying, investigation, and object management. Install it at `~/.claude/skills/observe/SKILL.md` for the optimizer to reference OPAL syntax and patterns.

## Example

Starting with a monitor query that scans 2.4 million unique tag combinations:

```
/optimize-query
```

```
Query: filter (customerId = 156247313073) and (kind = "monitor")
       statsby total_credits:sum(credits), group_by(monitorId)
       topk 10, max(total_credits)

Dataset: 41032426
Time range: -r 7d
Focus: reduce data scanned
```

The optimizer might:
1. Inspect the dataset schema, find that `customerId` and `kind` are indexed
2. Verify filters are already early in the pipeline (good)
3. Check if a pre-aggregated billing dataset exists (dataset switch)
4. Try reducing the time range in a subquery
5. Measure each variant and keep what's faster

## License

MIT
