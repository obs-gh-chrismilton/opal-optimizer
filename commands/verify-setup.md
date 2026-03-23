---
name: verify-setup
description: "Check all prerequisites for the OPAL optimizer plugin and guide through fixing anything missing"
model: opus
---

You are running a setup verification for the OPAL optimizer plugin. Check every prerequisite and report results clearly.

## Step 1: Check the Observe CLI binary

```bash
if [ -x ~/go/bin/observe ]; then
  echo "CLI: OK ($(~/go/bin/observe --help 2>&1 | head -2 | tail -1))"
else
  echo "CLI: NOT INSTALLED"
fi
```

If the CLI is missing, check whether Go is installed:
```bash
go version 2>&1 || echo "Go: NOT INSTALLED"
```

**Remediation if missing:**
- If Go is not installed: suggest `brew install go` (macOS) or the [official Go install](https://go.dev/doc/install), then `go install github.com/observeinc/observe@latest`
- If Go is installed but CLI is missing: suggest `go install github.com/observeinc/observe@latest`

## Step 2: Check the Observe CLI config

```bash
if [ -f ~/.config/observe.yaml ]; then
  echo "Config: FOUND"
else
  echo "Config: NOT FOUND"
fi
```

If found, validate its structure:
```bash
python3 -c "
import yaml
c = yaml.safe_load(open('$HOME/.config/observe.yaml'))
p = c['profile']['default']
print(f'Config: OK (customer={p[\"customerid\"]} site={p.get(\"site\", \"observeinc.com\")})')
" 2>&1
```

**Remediation if missing or malformed:**

Tell the user to create `~/.config/observe.yaml` with this content:
```yaml
profile:
  default:
    customerid: "<YOUR_CUSTOMER_ID>"
    site: "observeinc.com"
    authtoken: "<YOUR_AUTH_TOKEN>"
```

Or authenticate via SSO:
```bash
~/go/bin/observe --customerid <ID> --site observeinc.com login <EMAIL> --sso
```

## Step 3: Check Python 3 and PyYAML

```bash
python3 -c "import yaml; print('PyYAML: OK')" 2>&1 || echo "PyYAML: MISSING"
```

**Remediation if missing:**
- PyYAML is required by `/clone-monitor` for reading `observe.yaml`
- Install with: `pip3 install pyyaml`

## Step 4: Validate CLI connectivity

Only run this if Steps 1 and 2 both passed. If either failed, skip this step and note it was skipped.

```bash
~/go/bin/observe list dataset 2>&1 | head -5
```

If this fails with an auth error, the token is expired or wrong. Tell the user to re-authenticate:
```bash
~/go/bin/observe --customerid <ID> --site observeinc.com login <EMAIL> --sso
```

If it succeeds, report how many datasets were listed as confirmation.

## Step 5: Check the Observe CLI skill (optional)

```bash
if [ -f ~/.claude/skills/observe/SKILL.md ]; then
  echo "CLI Skill: OK"
else
  echo "CLI Skill: NOT INSTALLED (optional)"
fi
```

If missing, mention it is optional but recommended for richer OPAL syntax knowledge. Install with:
```bash
mkdir -p ~/.claude/skills/observe && curl -o ~/.claude/skills/observe/SKILL.md https://raw.githubusercontent.com/observeinc/observe-claude-code-skill-example/main/SKILL.md
```

## Step 6: Print summary

Format a clear summary table with the results of all checks:

```
=== OPAL Optimizer Setup ===
Observe CLI:      OK (v1.x.x)         | NOT INSTALLED
CLI Config:       OK (customer=12345)  | NOT FOUND / MALFORMED
PyYAML:           OK                   | MISSING
CLI Connectivity: OK (N datasets)      | FAILED / SKIPPED
CLI Skill:        OK                   | Not installed (optional)

Ready to optimize!  /  N issue(s) to fix before optimizing.
```

If everything required passes, suggest the user try `/optimize-query` or `/clone-monitor <id>` next.

If there are failures, list the remediation steps in priority order.
