# Daily Audit 2026-08-05

## Context

User asked about Bilibili duration check failing, then requested graphify weekly rebuild cron job setup.

## Tasks Completed

### 1. Bilibili 時長修復 (ad000c4)

**Problem**: Bilibili bookmarks showed `duration=null` even though yt-dlp could fetch duration correctly.

**Root Cause**: `_get_duration_yt()` in `routes_notehub.py` used `.isdigit()` to validate yt-dlp output, but yt-dlp returns decimal seconds (e.g., `239.142`). `.isdigit()` returns `False` for `239.142` → function returned `None`.

**Fix**: Changed to `int(float(raw))` to handle decimal seconds.

```python
# Before
if r.returncode == 0 and r.stdout.strip().isdigit():
    return int(r.stdout.strip())

# After
if r.returncode == 0:
    raw = r.stdout.strip()
    if raw:
        return int(float(raw))
```

**Verification**:
- 9 Bilibili bookmarks all have duration now
- Frontend renders 9 `⏱` badges correctly
- durations API returns correct values
- pytest: 27 tests pass

### 2. Graphify 每週重建 Cron (f2396dd81530)

**Setup**: Created weekly cron job to rebuild graphify automatically.

```yaml
name: graphify-weekly-build
schedule: 0 3 * * 0  # Sunday 03:00
command: cd /opt/data/projects/bookmark-manager && /opt/data/.xdg/bin/graphify update .
```

**First Run Results**:
- Nodes: 439
- Edges: 727
- Communities: 47
- Output: `graphify-out/graph.html` (379KB)

### 3. 每日排程盤查回報 Timeout 修復 (dd239cd537ae)

**Problem**: Job timing out at 604s (limit 600s) every run.

**Root Cause**: LLM-driven job doing status reporting doesn't need LLM. 600s idle timeout triggered while waiting for API response.

**Fix Applied**:
1. Simplified prompt (removed verbose formatting)
2. Added `timeout: 120` to job config

**Status**: Job still errors but with shorter timeout. Consider converting to no_agent for permanent fix.

## System Health

| Service | Status |
|---------|--------|
| Server (PID 31248) | ✅ HTTP 200 |
| Bot (PID 19248) | ✅ Running |
| Graphify server watchdog | ✅ Every 5min |
| Graphify weekly build | ✅ Sunday 03:00 |
| pytest | ✅ 27 tests pass |

## Learnings

1. **yt-dlp returns decimal seconds** — always use `int(float(raw))`, never `.isdigit()`
2. **LLM jobs can timeout** — simple status reporting jobs should be no_agent
3. **Graphify update is fast** — `graphify update .` takes ~30s vs full build
4. **Cron timeout is 600s for LLM, 2400s for no_agent** — design jobs accordingly

## Files Modified

- `/opt/data/projects/bookmark-manager/routes_notehub.py` — duration fix
- `/opt/data/cron/jobs.json` — added graphify-weekly-build, updated 盤查 job
- `/opt/data/skills/web/personal-bookmark-system/SKILL.md` — updated status
- `/opt/data/skills/devops/hermes-cron-management/SKILL.md` — added Symptom F
