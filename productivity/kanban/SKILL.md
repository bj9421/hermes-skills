---
name: kanban
description: "Kanban for Hermes Agent — two systems: (1) CLI file-based board (KANBAN.json) for project tracking, and (2) Dashboard SQLite board (kanban.db) with auto-dispatch for multi-agent work queues. Track tasks across columns with persistent storage."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kanban, project-management, workflow, tracking, productivity]
    related_skills:
      - ha-powers
      - writing-plans
      - subagent-driven-development
      - requesting-code-review
---

# 📋 Kanban — File-Based Board

> **Zero-dependency Kanban for Hermes.** Cards stored in `KANBAN.json` in your project root. Works with any project, integrates into the ha-powers pipeline.

## Quick Start

```bash
# 1. Init a board in your project
kanban init --board "My Project"

# 2. Add cards
kanban add "Implement login page" --col todo --prio P1 --desc "OAuth + email login"
kanban add "Fix navbar z-index" --col todo --prio P3

# 3. Start working
kanban move K1 --col doing

# 4. See the board
kanban list

# 5. Mark done
kanban move K1 --col review
kanban move K1 --col done

# 6. Export pretty markdown (→ Obsidian)
kanban board --output kanban/KANBAN.md
```

## Commands

| Command | What it does | Example |
|---------|-------------|---------|
| `init` | Create a new board | `kanban init --board "HA-POWERS"` |
| `add` | Add card to Backlog (or `--col`) | `kanban add "Fix bug" --prio P1 --desc "..."` |
| `move` | Move card between columns | `kanban move K1 --col doing` |
| `list` / `ls` | Show the board | `kanban list --col review` |
| `info` | Card details + activity log | `kanban info K1` |
| `log` | Add a note to card history | `kanban log K1 "Reviewed by architect"` |
| `edit` | Change title/desc/priority/assignee | `kanban edit K1 --prio P1 --assign @xun` |
| `board` | Export to Markdown (Obsidian-ready) | `kanban board --output docs/board.md` |
| `archive` | Archive Done cards older than N days | `kanban archive --days 7` (default: 7) |

## Columns

```
📋 Backlog  ─→  📝 Todo  ─→  🚧 Doing  ─→  🔍 Review  ─→  ✅ Done
  (icebox)      (planned)     (in prog)     (QC gate)      (finished)
```

The move command accepts **partial column names** (e.g. `--col todo`, `--col do`, `--col rev`).

## Priority Levels

| Level | Meaning |
|-------|---------|
| 🔴 P0 | Critical — blocker, fire |
| 🟠 P1 | High — next sprint |
| 🟡 P2 | Medium — normal priority |
| 🟢 P3 | Low — nice to have |
| ⚪ P4 | Backlog — maybe someday |

## Card Data Model

Each card stores:
- **ID** — auto-assigned: `K1`, `K2`, ...
- **Title** — what you see on the board
- **Column** — which stage it's in
- **Priority** — P0–P4
- **Assignee** — optional `@user`
- **Description** — free-text details
- **Subtasks** — optional checklist (auto-created from writing-plans)
- **Timestamps** — created, moved, logged
- **Activity Log** — every move + manual entries

## Integration with ha-powers

> The kanban skill is **embedded into ha-powers Phase 4**. Each task dispatched to a Developer subagent is automatically tracked.

### Auto-tracking Flow

```
Phase 4 starts:
  kanban add "Task 1: User model" --col doing --prio P1

Developer subagent dispatched:
  kanban log K1 "Dispatched to Developer A"

Spec review done:
  kanban log K1 "Spec review: PASS"

Quality review done:
  kanban log K1 "Quality review: APPROVED"

Task complete:
  kanban move K1 --col review

All tasks done:
  (orchestrator moves each to done)
```

### When ha-powers auto-creates cards

When you run ha-powers and it parses a plan with N tasks, it automatically:

```bash
kanban add "Task 1: User model" --col todo
kanban add "Task 3: Auth middleware" --col todo
kanban add "Task 5: Test fixtures" --col todo
```

And when dispatching:

```bash
kanban move K1 --col doing
kanban log K1 "🔄 Dispatched to Developer A"
```

### When reviewing:

```bash
kanban move K1 --col review
kanban log K1 "🔍 Spec review in progress..."
kanban log K1 "🔍 Quality review in progress..."
kanban log K1 "✅ All reviews passed!"
kanban move K1 --col done
```

## Standalone Usage (without ha-powers)

Kanban works as a standalone tool for any project:

```bash
cd my-project
kanban init --board "Sprint 1"
kanban add "Research auth libraries" --prio P2 --desc "Compare passport, auth0, supabase"
kanban add "Set up CI/CD" --prio P1

# Daily check-in
kanban list
kanban move K1 --col doing

# End of sprint
kanban archive --days 1
kanban board --output docs/sprint1-retro.md
```

## Path Options

All commands accept `--path <dir>` to operate on a board in a different directory:

```bash
kanban --path /opt/data/projects/my-app list
kanban --path ~/obsidian-vault/Projects/HAPower add "Fix bug" --col todo
```

## File Format

Data is stored in `KANBAN.json` (plain JSON, git-friendly):
```json
{
  "board": "My Project",
  "columns": ["Backlog", "Todo", "Doing", "Review", "Done"],
  "cards": [
    {
      "id": "K1",
      "title": "Rate limiter middleware",
      "column": "Doing",
      "priority": "P1",
      "assignee": "xun",
      "desc": "IP-based rate limiting with Redis",
      "subtasks": [
        {"id": "S1", "title": "Design interface", "done": true},
        {"id": "S2", "title": "Implement middleware", "done": false},
        {"id": "S3", "title": "Write tests", "done": false}
      ],
      "created_at": "2026-07-08T03:30:00Z",
      "logs": [
        {"timestamp": "2026-07-08T03:31:00Z", "message": "Moved from Todo → Doing"},
        {"timestamp": "2026-07-08T03:35:00Z", "message": "Dispatched to Developer A"}
      ]
    }
  ],
  "next_id": 2,
  "created_at": "2026-07-08T03:00:00Z",
  "updated_at": "2026-07-08T03:35:00Z"
}
```

### Subtask Tracking

When a card is created from a writing-plans output, subtasks are auto-populated:

```bash
# Auto-create subtasks from plan
kanban add "Task 1: User model" --col todo --subtasks "Design interface,Implement model,Write tests"

# Or manually
kanban subtask add K1 "Test fixtures"
kanban subtask move K1 S1 --done
kanban subtask list K1
```

Subtask status:
- `[ ]` pending
- `[x]` done
- `[>]` in progress

Example output:
```
K1: Rate limiter middleware (2/3 done)
├── [x] Design interface
├── [x] Implement middleware
└── [ ] Write tests
```

---

## 🖥️ Dashboard Kanban (SQLite Multi-Agent Board)

> **Built-in Hermes Dashboard board** — stored in `kanban.db` at the Hermes home root. Drives the multi-agent work-queue system with an internal dispatcher. Tasks with an `assignee` + `status='ready'` are picked up automatically.

### Two Kanban Systems at a Glance

| Aspect | CLI File-Based (KANBAN.json) | Dashboard SQLite (kanban.db) |
|--------|------------------------------|------------------------------|
| Backend | JSON file | SQLite database |
| Interface | `kanban` CLI commands | Hermes Dashboard web UI |
| Auto-execution | ❌ Manual move only | ✅ Dispatcher (60s interval) |
| Multi-agent | ❌ Single-user tracking | ✅ Assign profiles, auto-spawn |
| Best for | Lightweight task tracking | Automated multi-profile workflows |

### Database Location

```
/opt/data/kanban.db   (Hermes home root)
/opt/data/kanban.db.dispatch.lock
/opt/data/kanban.db.init.lock
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `tasks` | Main task storage — title, body, status, assignee, priority, model_override, etc. |
| `task_events` | Activity log — created, dispatched, completed events with JSON payload |
| `task_runs` | Execution records — which profile ran it, outcome, error details |
| `task_comments` | Free-form comments on tasks |
| `task_links` | Parent-child relationships between tasks |
| `task_attachments` | File attachments |
| `kanban_notify_subs` | Platform notification subscriptions per task |

### Task Status Lifecycle

```
ready  →  doing  →  review  →  done  →  archived
  ↑         ↓
  └── blocked (pause, unblock → ready)
```

### Required Fields for Auto-Dispatch

| Field | Value | Purpose |
|-------|-------|---------|
| `status` | `'ready'` | Must be in "Todo" state for dispatcher |
| `assignee` | Profile name (e.g. `'default'`, `'research'`, `'coder'`) | Which Hermes profile to spawn |
| `title` | Text | Task description used as the prompt |

Optional fields:

| Field | Type | Effect |
|-------|------|--------|
| `model_override` | `null` or string (`'provider/model'`) | Pin a specific model; `null` = use profile default |
| `skills` | `null` or JSON list `'["skill1","skill2"]'` | Skills to preload for the worker |
| `priority` | integer (1-5) | 1=highest, controls dispatch ordering |
| `max_retries` | integer (default 0) | Auto-retry on failure |
| `goal_mode` | 0 or 1 | If 1, task runs in goal-completion mode (multi-turn) |
| `goal_max_turns` | integer | Max turns for goal mode |

### Adding a Task (SQLite Direct)

```python
import sqlite3, time, uuid

conn = sqlite3.connect('/opt/data/kanban.db')
cur = conn.cursor()

task_id = 't_' + uuid.uuid4().hex[:8]

cur.execute('''
    INSERT INTO tasks (id, title, body, assignee, status, priority, created_by, created_at, workspace_kind)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    task_id,
    '📊 Q2 財報資料補齊',
    'Task description / prompt body here',
    'default',        # assignee → picks up default profile
    'ready',          # status → dispatcher will see it
    1,                # priority (1-5, 1=highest)
    'xun',            # created_by
    int(time.time()),
    'scratch'
))

# Add creation event so Dashboard shows it
cur.execute('''
    INSERT INTO task_events (task_id, kind, payload, created_at)
    VALUES (?, ?, ?, ?)
''', (
    task_id,
    'created',
    '{"status": "ready", "assignee": "default"}',
    int(time.time())
))

conn.commit()
conn.close()
```

### Dispatcher Configuration

Set in `config.yaml` under `kanban:`:

```yaml
kanban:
  auto_decompose: true               # Auto-split tasks with subtasks
  auto_decompose_per_tick: 3
  default_assignee: ''               # Set a fallback profile name
  dispatch_in_gateway: true          # Runs in gateway process
  dispatch_interval_seconds: 60      # Polling interval
  dispatch_stale_timeout_seconds: 14400  # 4h before reclaiming a stale claim
  failure_limit: 2                   # Auto-block after N failures
  orchestrator_profile: ''           # Profile for decomposer
```

> 💡 **Dispatcher flow:** Every 60s, the gateway scans for `status='ready'` tasks with a non-null `assignee`. It atomically claims one, sets status to `doing`, spawns the assigned Hermes profile with the task title as the prompt, then records the outcome in `task_runs`. After completion, status moves to `done` (success) or stays `doing` with a `result` field (failure). After `failure_limit` consecutive failures, the task is auto-blocked.

### Checking Board State

```bash
# Via Python
python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('/opt/data/kanban.db')
rows = conn.execute('SELECT id, title, status, assignee, priority, created_at FROM tasks WHERE status != ? ORDER BY priority, created_at', ('archived',)).fetchall()
for r in rows:
    ts = datetime.fromtimestamp(r[5]).strftime('%m/%d %H:%M')
    print(f'[{r[2]}] {r[1]}  (P{r[4]}, {r[3] or \"unassigned\"})  {ts}')
conn.close()
"
```

### CLI Alternative: `hermes kanban <verb>`

Hermes also exposes CLI verbs for the SQLite board:

```bash
hermes kanban init             # Initialize the SQLite board
hermes kanban create           # Create a task
hermes kanban list / ls        # Show board
hermes kanban show TASK_ID     # Task details
hermes kanban assign TASK_ID   # Assign to a profile
hermes kanban comment TASK_ID  # Add comment
hermes kanban complete TASK_ID # Mark done
hermes kanban archive TASK_ID  # Archive
```

See `hermes kanban --help` for the full verb list.

### Pitfalls

- **No assignee = no dispatch.** The most common reason a task sits forever in Todo is a missing or null `assignee`. Always set it explicitly.
- **Only `status='ready'` tasks are dispatched.** Archived or done tasks are ignored.
- **Dispatcher is tied to the gateway process.** If the gateway is stopped/restarting, tasks queue up until it comes back.
- **Lock file.** `kanban.db.dispatch.lock` prevents duplicate dispatches across processes — don't remove it manually unless you know the previous dispatcher is dead.
- **Profile must exist.** The assignee name must match an existing Hermes profile name. Unknown profiles silently block dispatch.

## Best Practices

- **Init kanban at project start** — before any work begins
- **Move cards as you work** — `kanban move K1 --col doing` when you start a task
- **Log important events** — reviews, decisions, blockers
- **Archive weekly** — keep the board clean, data stays in `archived_cards`
- **Export before demos** — `kanban board --output kanban/board.md` for Obsidian/screenshots
- **Use priority honestly** — not everything can be P1
- **Subtask granularity** — create subtasks only when a card has 3+ clearly independent steps; don't over-split

> 💡 **Kanban vs Progress Tracker:**
> - **Progress Tracker** (inside ha-powers) = tracks one feature's development steps in real-time. Disappears after the feature is done.
> - **Kanban** = tracks multiple features across sessions. Persists in `KANBAN.json`.
> - Use Kanban to decide WHAT to build next; use Progress Tracker to track HOW you build it.

## Manual kanban list Example Output

```
======================================================================
  📋 HA-POWERS Dev
======================================================================

  📋 Backlog (1)
  ──────────────────────────────────────────────────────────────────
    ID    Priority       Title
    ────  ──────────     ─────────────────────────────────────
    K5    ⚪ P4          Nice to have: dark mode toggle

  🚧 Doing (2)
  ──────────────────────────────────────────────────────────────────
    ID    Priority       Title
    ────  ──────────     ─────────────────────────────────────
    K1    🟠 P1          Rate limiter middleware   @xun
    K3    🟡 P2          Redis integration

  ✅ Done (1)
  ──────────────────────────────────────────────────────────────────
    ID    Priority       Title
    ────  ──────────     ─────────────────────────────────────
    K2    🟠 P1          Login page redesign

  Total: 4 cards (4 shown)
```
