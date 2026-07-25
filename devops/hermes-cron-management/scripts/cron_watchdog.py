#!/usr/bin/env python3
"""
Lightweight cron watchdog — runs every 10 min via no_agent cron.
- All OK → exit 0, empty stdout → silent (no notification)
- Error found → attempt auto-fix (json patch), print report → exit 1

Setup: cp to /opt/data/.hermes/scripts/cron_watchdog.py
Cron:  cronjob create name=cron-watchdog-fast schedule="every 10m" script="cron_watchdog.py" no_agent=true
"""
import json, sys, os, shutil
from datetime import datetime, timezone, timedelta

JOBS_FILE = "/opt/data/cron/jobs.json"
BACKUP_FILE = "/opt/data/cron/jobs.json.bak"
OUTPUT_DIR = "/opt/data/cron/output"
TZ = timezone(timedelta(hours=8))

def load_jobs():
    with open(JOBS_FILE, "r") as f:
        data = json.load(f)
    return data.get("jobs", data) if isinstance(data, dict) else data

def save_jobs(jobs_data):
    shutil.copy2(JOBS_FILE, BACKUP_FILE)
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)

def read_output_tail(job_id, lines=20):
    outdir = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.isdir(outdir):
        return "(no output)"
    files = sorted(os.listdir(outdir), reverse=True)
    if not files:
        return "(no output)"
    try:
        with open(os.path.join(outdir, files[0])) as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except:
        return "(read error)"

def main():
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

    try:
        raw = json.load(open(JOBS_FILE))
    except Exception as e:
        print(f"[{now}] ❌ 無法讀取 jobs.json: {e}")
        sys.exit(1)

    jobs = raw.get("jobs", raw) if isinstance(raw, dict) else raw
    fixed = []
    failed = []

    for job in jobs:
        if job.get("last_status") != "error":
            continue
        if job.get("paused_at") or not job.get("enabled"):
            continue

        name = job.get("name", "unnamed")
        jid = job.get("job_id")
        err = (job.get("last_error") or read_output_tail(jid)).lower()

        # --- Auto-fix: provider/auth errors → switch to big-pickle ---
        if any(kw in err for kw in ["401", "missing authentication", "not supported", "modelerror"]):
            job["model"] = "big-pickle"
            job["provider"] = "opencode"
            job["last_status"] = None
            job["last_error"] = None
            fixed.append(f"🔧 {name} ({jid}) — 切換到 opencode/big-pickle")
            continue

        # --- Auto-fix: drift → re-pin ---
        if "drift" in err:
            job["model"] = "big-pickle"
            job["provider"] = "opencode"
            job["last_status"] = None
            job["last_error"] = None
            fixed.append(f"🔧 {name} ({jid}) — 重新 pin 到 opencode/big-pickle")
            continue

        # --- Report only: timeout, unknown ---
        tail = read_output_tail(jid)
        failed.append(f"⚠️ {name} ({jid}) — 需人工調查\n  Error: {job.get('last_error', '?')}\n  Tail: {tail[:200]}")

    # No errors → silent exit
    if not fixed and not failed:
        sys.exit(0)

    # Save patches
    if fixed:
        save_jobs(raw)

    # Print report
    print(f"## Cron Watchdog — {now}\n")
    if fixed:
        print("### 已自動修復：")
        for msg in fixed:
            print(msg)
        print()

    if failed:
        print("### 需人工處理：")
        for msg in failed:
            print(msg)
        print()

    if fixed:
        print("💡 已修復的 job 會在下次排程自動執行。")

    sys.exit(1)

if __name__ == "__main__":
    main()
