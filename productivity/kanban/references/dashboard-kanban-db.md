# Dashboard Kanban — Database Schema Reference

> Full schema for `/opt/data/kanban.db` (Hermes Dashboard built-in kanban).

## Table: `tasks`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | TEXT | PK | | Format: `t_` + 8 hex chars (e.g. `t_8d856b36`) |
| `title` | TEXT | NOT NULL | | Task prompt / description shown on board |
| `body` | TEXT | YES | | Detailed description, execution notes |
| `assignee` | TEXT | YES | | Hermes profile name (`default`, `research`, `coder`, etc.) |
| `status` | TEXT | NOT NULL | | `ready`, `doing`, `review`, `done`, `archived`, `blocked` |
| `priority` | INTEGER | YES | 0 | 1=highest, 5=lowest |
| `created_by` | TEXT | YES | | User or profile name |
| `created_at` | INTEGER | NOT NULL | | Unix timestamp |
| `started_at` | INTEGER | YES | | When dispatcher claimed it |
| `completed_at` | INTEGER | YES | | When finished |
| `workspace_kind` | TEXT | NOT NULL | `'scratch'` | Workspace isolation mode |
| `workspace_path` | TEXT | YES | | Path to isolated workspace |
| `branch_name` | TEXT | YES | | Git branch if worktree mode |
| `claim_lock` | TEXT | YES | | Dispatcher claim UUID |
| `claim_expires` | INTEGER | YES | | Claim expiry timestamp |
| `tenant` | TEXT | YES | | Namespace for multi-tenant boards |
| `result` | TEXT | YES | | Execution result summary |
| `idempotency_key` | TEXT | YES | | Prevent duplicate dispatch |
| `consecutive_failures` | INTEGER | NOT NULL | 0 | Auto-block counter |
| `worker_pid` | INTEGER | YES | | Spawned worker PID |
| `last_failure_error` | TEXT | YES | | Last error message |
| `max_runtime_seconds` | INTEGER | YES | | Per-run timeout |
| `last_heartbeat_at` | INTEGER | YES | | Worker heartbeat |
| `current_run_id` | INTEGER | YES | | FK to task_runs.id |
| `workflow_template_id` | TEXT | YES | | Workflow template reference |
| `current_step_key` | TEXT | YES | | Current workflow step |
| `skills` | TEXT | YES | | JSON list: `'["skill1","skill2"]'` |
| `model_override` | TEXT | YES | | `'provider/model'` format |
| `max_retries` | INTEGER | YES | 0 | Retry count before block |
| `goal_mode` | INTEGER | NOT NULL | 0 | 1 = goal-completion mode |
| `goal_max_turns` | INTEGER | YES | | Max turns for goal mode |
| `session_id` | TEXT | YES | | Hermes session ID |
| `project_id` | TEXT | YES | | Project grouping |
| `block_kind` | TEXT | YES | | Block reason category |
| `block_recurrences` | INTEGER | NOT NULL | 0 | Block recurrence count |

## Table: `task_events`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER (PK) | Auto-increment |
| `task_id` | TEXT (FK) | References tasks.id |
| `run_id` | INTEGER (FK) | References task_runs.id (nullable) |
| `kind` | TEXT | `created`, `dispatched`, `completed`, `failed`, `blocked`, `unblocked`, etc. |
| `payload` | TEXT | JSON with event-specific data |
| `created_at` | INTEGER | Unix timestamp |

## Table: `task_runs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER (PK) | Auto-increment |
| `task_id` | TEXT (FK) | References tasks.id |
| `profile` | TEXT | Which profile executed |
| `step_key` | TEXT | Workflow step (nullable) |
| `status` | TEXT | `running`, `done`, `failed`, `timeout` |
| `claim_lock` | TEXT | Dispatch UUID |
| `claim_expires` | INTEGER | Claim timeout |
| `worker_pid` | INTEGER | Worker process ID |
| `max_runtime_seconds` | INTEGER | Timeout |
| `last_heartbeat_at` | INTEGER | Ping timestamp |
| `started_at` | INTEGER | Unix timestamp |
| `ended_at` | INTEGER | Unix timestamp |
| `outcome` | TEXT | `completed`, `failed`, `timeout` |
| `summary` | TEXT | Execution summary |
| `metadata` | TEXT | JSON blob |
| `error` | TEXT | Error details |

## Table: `task_comments`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER (PK) | Auto-increment |
| `task_id` | TEXT (FK) | References tasks.id |
| `author` | TEXT | Comment author |
| `body` | TEXT | Comment content |
| `created_at` | INTEGER | Unix timestamp |

## Table: `task_links`

| Column | Type | Notes |
|--------|------|-------|
| `parent_id` | TEXT (PK) | Parent task id |
| `child_id` | TEXT (PK) | Child task id |

## Table: `task_attachments`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER (PK) | Auto-increment |
| `task_id` | TEXT (FK) | References tasks.id |
| `filename` | TEXT | Original filename |
| `stored_path` | TEXT | Path on disk |
| `content_type` | TEXT | MIME type |
| `size` | INTEGER | Bytes |
| `uploaded_by` | TEXT | Uploader |
| `created_at` | INTEGER | Unix timestamp |

## Table: `kanban_notify_subs`

| Column | Type | Notes |
|--------|------|-------|
| `task_id` | TEXT (PK, FK) | References tasks.id |
| `platform` | TEXT (PK) | `telegram`, `discord`, etc. |
| `chat_id` | TEXT (PK) | Platform chat identifier |
| `thread_id` | TEXT (PK) | Thread identifier |
| `user_id` | TEXT | Platform user ID |
| `notifier_profile` | TEXT | Profile used for notifications |
| `created_at` | INTEGER | Unix timestamp |
| `last_event_id` | INTEGER | Last notified event id |

## Useful Queries

### All active tasks (not archived)
```sql
SELECT id, title, status, assignee, priority, created_at
FROM tasks
WHERE status != 'archived'
ORDER BY priority, created_at;
```

### Tasks ready for dispatch
```sql
SELECT id, title, assignee, priority, model_override
FROM tasks
WHERE status = 'ready' AND assignee IS NOT NULL AND assignee != ''
ORDER BY priority;
```

### Task execution history
```sql
SELECT t.id, t.title, r.profile, r.status, r.outcome, r.started_at, r.ended_at, r.error
FROM tasks t
JOIN task_runs r ON r.task_id = t.id
WHERE t.id = ?
ORDER BY r.started_at DESC;
```

### Recent events for a task
```sql
SELECT kind, payload, created_at
FROM task_events
WHERE task_id = ?
ORDER BY created_at DESC;
```

### Task + latest run (one query)
```sql
SELECT t.id, t.title, t.status, t.assignee, t.model_override,
       r.status AS run_status, r.outcome, r.error
FROM tasks t
LEFT JOIN task_runs r ON r.id = t.current_run_id
WHERE t.status != 'archived'
ORDER BY t.priority, t.created_at;
```
