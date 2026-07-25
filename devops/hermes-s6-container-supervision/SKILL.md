---
name: hermes-s6-container-supervision
description: Manage Hermes Agent s6 service lifecycle, handle dashboard/gateway crashes, and prevent infinite restart loops.
---

# Hermes s6 Container Supervision

## Overview

Hermes runs in a Docker container managed by s6-overlay. Services like dashboard and gateway are supervised by s6, which auto-restarts crashed processes.

### s6 Service Topology

On the RPi/Docker deployment, services run under these s6 supervision paths:

| Service | s6 run script | Supervised by | PID observed |
|---------|--------------|---------------|-------------|
| Main gateway (`hermes gateway run --replace`) | `/run/s6/db/servicedirs/main-hermes/run` | `s6-supervise main-hermes` (PID 28) | PID 138 |
| Gateway logger | `/run/s6/db/servicedirs/gateway-default/log` | `s6-supervise gateway-default/log` (PID 139) | PID 141 (`s6-log`) |
| Dashboard | `/run/s6/db/servicedirs/dashboard/run` | `s6-supervise dashboard` (PID 29) | PID 11675 |
| `hermes serve` (desktop backend) | ❌ **No s6 service** — must run manually | N/A | N/A |

**Key findings about the dashboard run script (`/run/s6/db/servicedirs/dashboard/run`):**
1. Checks `$HERMES_DASHBOARD` env var — if falsy, exits immediately (permanent failure)
2. Sources the Hermes venv: `. /opt/hermes/.venv/bin/activate`
3. Reads env vars `$HERMES_DASHBOARD_HOST` (default 0.0.0.0) and `$HERMES_DASHBOARD_PORT` (default 9119)
4. Uses `s6-setuidgid hermes` to drop privileges before executing
5. Passes only `--host` and `--port` flags — **auth env vars are read by the dashboard process itself**, not forwarded by the script
6. `--insecure` handling: if `HERMES_DASHBOARD_INSECURE` is truthy, prints a deprecation warning but does NOT pass `--insecure` (it's a no-op at the binary level too, June 2026+)

**Gateway logger:**
- Runs as `s6-log 1 n10 s1000000 T /opt/data/logs/gateways/default`
- Log rotation: 10 files × 1MB, auto-rotated
- Logs at `/opt/data/logs/gateways/default/current`

**Services NOT supervised by s6 (no built-in service):**
- `hermes serve` — the headless backend needed by Hermes Desktop

## Common Issues

### 1. Dashboard Infinite Restart Loop

**Symptom:** Dashboard CPU at 99%, port closed, `hermes dashboard` process repeatedly starts and dies.

**Root Cause:** Auth gate rejects non-loopback binding without registered auth provider. Process exits → s6 restarts → infinite loop.

**Fix Options:**

#### Option A: Change to loopback (no auth needed)
Set `HERMES_DASHBOARD_HOST=127.0.0.1` in container env vars. Dashboard binds to localhost only, no auth required. Access via SSH tunnel.

#### Option B: Register proper auth
Set `dashboard.basic_auth.username` and `dashboard.basic_auth.password_hash` in `config.yaml`. Then restart container so s6 picks up the config.

#### Option C: Kill s6 supervision
Kill the s6-supervise process for dashboard. Start dashboard manually. Manual process won't be auto-restarted by s6.

### 2. Gateway Crash Recovery

**Symptom:** Gateway stops responding, `hermes gateway` process gone.

**Fix:** s6 should auto-restart. Check logs:
```bash
cat /opt/data/logs/gateways/default/current
```

### 3. Service Status Check

```bash
# List all s6 services
find /opt/hermes/docker/s6-rc.d/user/contents.d/ -type f -exec cat {} \;

# Check service state
ls -la /opt/data/logs/gateways/default/
ps aux | grep hermes | grep -v grep

# Check if port is listening
python3 -c "
import socket
for port in [9119, 5000]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = s.connect_ex(('127.0.0.1', port))
    print(f'Port {port}: {\"open\" if r == 0 else \"closed\"}')
    s.close()
"
```

## Manual Process Management

### Kill stuck dashboard
```bash
kill -9 $(pgrep -f "hermes dashboard")
```

### Start dashboard manually
```bash
/opt/hermes/.venv/bin/python3 /opt/hermes/.venv/bin/hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

### Verify dashboard running
```bash
curl -s "http://127.0.0.1:9119/" | head -5
# Should redirect to /auth/login if auth is configured
```

## Prevention

- Always set auth credentials in config.yaml BEFORE enabling non-loopback dashboard
- Use loopback binding for local-only access (no auth needed)
- Monitor dashboard CPU usage — >50% sustained means restart loop
- Check s6 logs periodically: `ls -la /opt/data/logs/gateways/default/`
