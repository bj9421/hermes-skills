# Profile Discovery — Finding All Hermes Profiles on Disk

## Problem

`hermes profile list` only shows profiles registered under `~/.hermes/profiles/`. Legacy, manually-created, or migrated profiles can exist in other parent directories — invisible to the CLI but fully functional if referenced by path.

This causes confusion when users ask "where is profile X?" or "profile X disappeared."

## Discovery Workflow

### 1. Check the official Hermes location

```bash
ls ~/.hermes/profiles/
```

### 2. Scan the entire data directory for `profile.yaml`

```bash
find /opt/data -name "profile.yaml" -not -path "*/skills/*" -not -path "*/.hermes/skills/*"
```

Each result is a valid standalone profile directory with:

- `config.yaml` — model, provider, toolsets
- `SOUL.md` — persona/instructions
- `.env` — API keys (may be a symlink to a shared `.env`)
- `skills/` — installed skills
- `memories/` — MEMORY.md, USER.md
- `state.db` — session history
- `cron/` — scheduled jobs
- `auth.json` — gateway auth tokens

### 3. Identify which profiles are active

```bash
# Currently running gateways
ps aux | grep "hermes" | grep -v grep

# Recent activity
ls -ltu ~/.hermes/profiles/*/state.db 2>/dev/null
ls -ltu /opt/data/profiles/*/state.db 2>/dev/null
ls -ltu /opt/data/profiles/*/logs/agent.log 2>/dev/null
```

### 4. Check for stale references

```bash
# Does any SOUL.md or config.yaml still reference the old profile?
grep -rn "coder\|architect\|planner" /opt/data/.hermes/SOUL.md 2>/dev/null
```

If found, update those references to reflect current architecture (HA·Power uses subagents, not standalone profiles).

## Cleanup

After confirming a profile is unused:

```bash
# Verify it's not running
ps aux | grep <profile-name>

# Remove the entire profile directory
rm -rf /opt/data/profiles/<profile-name>
```

> ⚠️ Profiles can contain their own `memory_store.db`, `state.db`, and cron job output. Deletion is permanent.
