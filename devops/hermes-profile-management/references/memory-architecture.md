# Hermes Memory Architecture

## Overview

Hermes has two persistent data stores, with critically different scoping:

| Store | Scope | File | Content |
|-------|-------|------|---------|
| **Memory** | Per-profile | `~/.hermes/memory_store.db` (or profile-specific path) | Extracted facts (memory + user_profile entries) |
| **Session history** | **Global** | `~/.hermes/state.db` | All conversation transcripts from every profile |

The **session store is shared** — any profile can `session_search` across all profiles' conversations.
The **memory store is isolated** — each profile has its own SQLite DB unless explicitly configured otherwise.

## Memory Provider: `holographic`

The default (and recommended) memory provider is `holographic`. It auto-extracts facts from conversation and stores them with trust scoring.

### Key Config Settings (in `config.yaml`)

```yaml
memory:
  memory_enabled: true          # master switch
  user_profile_enabled: true    # separate user-profile store
  write_approval: false         # if true, agent asks before saving
  memory_char_limit: 4000       # max chars for agent memory
  user_char_limit: 2500         # max chars for user profile
  provider: holographic
  nudge_interval: 10            # reminder every N messages
  flush_min_turns: 6            # min turns before memory extraction

plugins:
  hermes-memory-store:
    db_path: ~/.hermes/memory_store.db   # the SQLite file
    auto_extract: true                    # auto-extract from conversation
    default_trust: 0.5
    min_trust_threshold: 0.3              # below this: discard
    temporal_decay_half_life: 0           # 0 = no decay
```

## Per-Profile Resolution: The `$HOME/.hermes/` Trap

When a profile has a `config.yaml` with the `memory:` block but **no explicit `plugins.hermes-memory-store.db_path`**, the memory system does NOT fall back to the root config's `db_path`. Instead, it resolves to **`$HOME/.hermes/memory_store.db`** under that profile's own runtime environment.

For example, on RPi with `HERMES_HOME=/opt/data` and `HOME=/opt/data/home`:

| Profile | config has `db_path`? | Actual DB used |
|---------|----------------------|----------------|
| Root (`/.hermes/config.yaml`) | `~/.hermes/memory_store.db` | `/opt/data/.hermes/memory_store.db` |
| Default | ❌ (no plugins block) | Falls back to `$HOME/.hermes/memory_store.db` |
| Research | ❌ (no plugins block) | Falls back to `/opt/data/profiles/research/home/.hermes/memory_store.db` |

This means **two profiles can both have `memory: enabled: true` yet write to entirely different SQLite files**. A symlink on one path doesn't help if the actual reads/writes go to a different path altogether.

### The Fix: Explicit Absolute Path

Always set `db_path` explicitly in **every profile's config** using an **absolute path**:

```yaml
plugins:
  hermes-memory-store:
    db_path: /opt/data/.hermes/memory_store.db   # absolute path, no ~
    auto_extract: true
    default_trust: 0.5
    min_trust_threshold: 0.3
    temporal_decay_half_life: 0
```

Do NOT rely on symlinks — they are fragile and easy to defeat by a profile writing to a different location.

### How to Detect Separate Memory DBs

```bash
# Find ALL memory_store.db files on the system
find /opt/data -name "memory_store.db" -type f

# Check each one for content
for db in $(find /opt/data -name "memory_store.db" -type f); do
    echo "$db: $(sqlite3 "$db" 'SELECT COUNT(*) FROM facts' 2>/dev/null || echo 0) facts"
done
```

### How to Merge Two Memory DBs

Use Python to merge unique facts from one DB into another:

```python
import sqlite3

TARGET = '/opt/data/.hermes/memory_store.db'   # receiving DB
SOURCE = '/opt/data/profiles/research/home/.hermes/memory_store.db'  # source

# Read source facts
conn_src = sqlite3.connect(SOURCE)
src_facts = conn_src.execute(
    'SELECT content, category, tags, trust_score, retrieval_count, helpful_count FROM facts'
).fetchall()
conn_src.close()

# Merge into target (skip duplicates by content)
conn_tgt = sqlite3.connect(TARGET)
existing = set(r[0] for r in conn_tgt.execute('SELECT content FROM facts').fetchall())

inserted = 0
for f in src_facts:
    if f[0] not in existing:
        conn_tgt.execute(
            'INSERT INTO facts (content, category, tags, trust_score, retrieval_count, helpful_count) VALUES (?,?,?,?,?,?)',
            f
        )
        inserted += 1

conn_tgt.commit()
conn_tgt.execute("INSERT INTO facts_fts(facts_fts) VALUES('rebuild')")
conn_tgt.close()
print(f'Inserted {inserted}, skipped {len(src_facts)-inserted} duplicates')
```

### Trust Scoring

Each extracted memory has a trust score (0–1). Only entries above `min_trust_threshold` survive. Scores can:
- Increase on repeated confirmation
- Decrease on contradiction or user correction
- Decay over time if `temporal_decay_half_life > 0`

## Per-Profile Memory: What Happens By Default

1. **When you create a profile** via `hermes profile create <name>`, the new profile inherits the source profile's `config.yaml`, which includes `plugins.hermes-memory-store.db_path` pointing to `~/.hermes/memory_store.db`.

2. **Both profiles point to the SAME SQLite file** → they share memory automatically.

3. **If a profile has NO `config.yaml` at all** (e.g. a bare profile directory with only `skills/`), the memory system is effectively **inactive** for that profile — no memory is read or written.

## How to Check a Profile's Memory Status

```bash
# Check if memory is configured
hermes --profile <name> config show | grep -A 20 "Memory\|memory"
# or check directly:
grep -A 15 "memory:" ~/.hermes/profiles/<name>/config.yaml
```

```bash
# Check if the DB exists
ls -la ~/.hermes/memory_store.db
# For profile-specific:
ls -la ~/.hermes/profiles/<name>/memory_store.db
```

## Sharing Memory Between Profiles

### Option A: Explicit Shared Path (Recommended)

Set the same absolute `db_path` in every profile's config:

```bash
# In each profile's config.yaml:
# plugins.hermes-memory-store.db_path: /opt/data/.hermes/memory_store.db

# Via CLI:
hermes --profile default config set plugins.hermes-memory-store.db_path "/opt/data/.hermes/memory_store.db"
hermes --profile research config set plugins.hermes-memory-store.db_path "/opt/data/.hermes/memory_store.db"
```

### Option B: Separate DBs (true isolation)

Each profile gets its own SQLite file:

```bash
hermes --profile default config set plugins.hermes-memory-store.db_path "~/.hermes/default_memory.db"
hermes --profile research config set plugins.hermes-memory-store.db_path "~/.hermes/research_memory.db"
```

### Option C: Read-only view of another profile's memory

Point one profile's `db_path` to the other's DB. That profile reads/writes the same file (effectively bidirectional sharing).

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Profile has no memory | No `config.yaml` with `memory:` block | Create profile via `hermes profile create` or add config manually |
| "memory_store.db not found" | Profile uses custom path that doesn't exist | Create the file or fix the path |
| Memories from Profile A don't appear in Profile B | Different `db_path` — and one profile may be writing to `$HOME/.hermes/` instead of the configured path | Use absolute paths in all profiles; run `find /opt/data -name "memory_store.db" -type f` to find all copies |
| Auto-extraction stopped | `auto_extract: false` or `memory_enabled: false` | Check config |
| Trust threshold too aggressive | `min_trust_threshold` too high | Lower to 0.3 or 0.2 |
| Memory works in CLI but not dashboard | Different profile context | Check which profile the dashboard is running under |
