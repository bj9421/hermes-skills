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

### 3. 每日排程盤查回報 Timeout 修復 (dd239cd537ae) — 已轉 no_agent 根治

**Problem**: Job timing out at 604s (limit 600s) every run.

**Root Cause**: LLM-driven job doing status reporting doesn't need LLM. 600s idle timeout triggered while waiting for non-streaming API response (`last activity: waiting for non-streaming API response`). watchdog 每 10 分重報同一錯誤（Symptom D）。

**Fix Applied（最終方案 = no_agent 轉換）**:
1. 寫 `/opt/data/scripts/cron_daily_check.sh`（bash + python3 heredoc 讀 `/opt/data/cron/jobs.json`，分類 ✅今日成功 / ❌錯誤 / ⏳待執行，輸出繁體中文報告）— 執行 <1 秒
2. `cp` 到 `~/.hermes/scripts/cron_daily_check.sh` + chmod +x（⚠️ cronjob update 的 script 欄位只接受 `~/.hermes/scripts/` 相對檔名，絕對路徑會被拒：「Script path must be relative to ~/.hermes/scripts/」）
3. `cronjob action=update job_id=dd239cd537ae script="cron_daily_check.sh" no_agent=true`
4. `cronjob action=run` → succeeded → `last_status: ok`

**Status**: ✅ 已根治。no_agent 模式執行 <1 秒，watchdog 不再重報（第一次手動 run 後 last_status 由 error → ok）。

**教訓**: 每日盤查類的「LLM 讀狀態 + 格式化作報告」job 是 no_agent 高優先候選 — 只要報告是 jobs.json 的確定性格式化輸出，完全不需要 LLM。轉換三步驟：寫 script（Watchdog pattern）→ cp 到 ~/.hermes/scripts/ → update no_agent=true。與 bookmark-enrich / holographic-sync 同類（見 SKILL.md Symptom D variant）。

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
