---
name: hermes-dashboard-troubleshooting
category: devops
description: Troubleshoot Hermes dashboard connectivity and service issues.
---

# Hermes Dashboard Troubleshooting

## Trigger Conditions
- Hermes dashboard is unreachable via browser or curl.
- Port mapping errors when trying to access dashboard on expected host port.
- Dashboard service appears to be down or not starting in s6 supervision.
- Environment variable misconfiguration (HERMES_DASHBOARD, HERMES_DASHBOARD_PORT, HERMES_DASHBOARD_HOST).
- Using Tailscale or other VPN and unable to reach dashboard.

## Step‑by‑Step Procedure

### 1. Verify Dashboard Enable Flag
Check that `HERMES_DASHBOARD` is set to a truthy value (1, true, yes, etc.).  
If the flag is falsy or unset, the s6 service will exit immediately and report permanent failure.

```bash
# Inside the container or host env
echo $HERMES_DASHBOARD
```

### 2. Confirm Port and Host Settings
Ensure the following variables are set as desired:
- `HERMES_DASHBOARD_PORT` (default 9119)
- `HERMES_DASHBOARD_HOST` (default 0.0.0.0)

```bash
echo $HERMES_DASHBOARD_PORT
echo $HERMES_DASHBOARD_HOST
```

### 3. Inspect s6 Service Status
List s6 services to see if the dashboard service is down or in a permanent‑failure state.

```bash
# On the host (if you have s6 utilities) or inside container:
s6-svstat /run/service/dashboard
```

Look for `down` or `paused` status. If the service shows `permanent failure`, the enable flag is likely falsy.

### 4. Restart the Dashboard Service
After correcting environment variables, request s6 to restart the service.

```bash
# Trigger a restart (sends TERM then CONT)
s6-svc -t /run/service/dashboard
# Or force a restart if needed
s6-svc -r /run/service/dashboard
```

### 5. Verify the Process Is Running
Check that the `hermes dashboard` process is up and listening on the intended port.

```bash
ps aux | grep "hermes dashboard" | grep -v grep
```

### 6. Confirm Port Binding
Use available tools to see if the process is bound to the expected interface and port.

```bash
# If netstat or ss is available:
netstat -tlnp | grep :$HERMES_DASHBOARD_PORT
ss -tlnp | grep :$HERMES_DASHBOARD_PORT
```

If neither tool is installed, you can check `/proc/net/tcp` or attempt a curl.

### 7. Test Connectivity
From the host or another machine on the same network (including via Tailscale), try to reach the dashboard.

```bash
curl http://<host_ip>:$HERMES_DASHBOARD_PORT
# Should return HTML or a redirect to the login page.
```

If using Tailscale, ensure the Tailscale IP is reachable and firewall rules allow the port.

### 8. Check Logs for Errors
If the service repeatedly fails, inspect the dashboard log (if enabled) or the container's stdout/stderr.

```bash
# Example log location (may vary)
cat /tmp/dashboard.log 2>/dev/null || echo "Log not found"
```

### 9. Common Pitfalls

- **Basic auth env var precedence**: The dashboard basic auth plugin resolves credentials in this order (env var wins over config.yaml):
  1. `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` (env var) — checked first
  2. `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` (env var) → used directly
  3. `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` (env var, plaintext) → auto-hashed
  4. `config.yaml` → `dashboard.basic_auth.username`
  5. `config.yaml` → `dashboard.basic_auth.password_hash` → used directly
  6. `config.yaml` → `dashboard.basic_auth.password` (plaintext) → auto-hashed
  
  **Critical**: If `_USERNAME` env var is missing, auth fails even if `_PASSWORD` and `_SECRET` are set. All three (`_USERNAME`, `_PASSWORD`/`_PASSWORD_HASH`, `_SECRET`) must be present.
  
  **Also critical**: The s6 run script (`/opt/hermes/docker/s6-rc.d/dashboard/run`) only passes `--host` and `--port` to the dashboard command. Auth env vars are read by the dashboard process itself, NOT by the run script. The run script does NOT forward `_USERNAME`, `_PASSWORD`, or `_SECRET`.

- **Auth env var vs config.yaml username mismatch → auto_sso loop (HTTP 500 on `/`)**: When `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` (env var) differs from `dashboard.basic_auth.username` (config.yaml), the basic auth provider may accept the initial login but fail on subsequent `auto_sso` refresh — the conflicting username in config.yaml corrupts session validation.
  - **Symptom pattern**: Login page loads (HTTP 200), but POSTing credentials returns 401, root path `/` returns **HTTP 500** (not the normal 302 redirect). The auth log shows endless `login_start (reason: "auto_sso")` events with **no** corresponding `login_success`.
  - **Diagnosis**: Compare env var vs config:
    ```bash
    cat /proc/$(pgrep -f 'hermes dashboard' | head -1)/environ | tr '\0' '\n' | grep DASHBOARD_BASIC_AUTH_USERNAME
    grep -A5 'basic_auth:' /opt/data/config.yaml | grep username
    ```
    Check auth log for the auto_sso loop:
    ```bash
    grep -c 'login_start.*auto_sso' /opt/data/logs/dashboard-auth.log
    grep -c 'login_success' /opt/data/logs/dashboard-auth.log
    ```
  - **Fix**: Align config.yaml with env vars:
    ```bash
    hermes config set dashboard.basic_auth.username <env-var-value>
    hermes config set dashboard.basic_auth.password <env-var-password>
    hermes config set dashboard.basic_auth.secret <env-var-secret>
    s6-svc -r /run/service/dashboard
    ```
    Config changes take effect after a dashboard restart (`s6-svc -r`). Env var changes require container redeploy (Portainer → Recreate).
  - **Correct login endpoint**: The login form POSTs to `/auth/password-login` (NOT `/api/auth/login`) with JSON body `{"provider":"basic","username":"...","password":"..."}`. Test with:
    ```bash
    curl -c /tmp/dash_cookies.txt -X POST http://dietpi4:9119/auth/password-login \
      -H 'Content-Type: application/json' \
      -d '{"provider":"basic","username":"admin","password":"..."}'
    ```
    On success, returns `{"ok":true,"next":"/"}` with session cookies. Thereafter, access `/` with cookies for HTTP 200.

- **Forgotten enable flag**: Setting only the port without `HERMES_DASHBOARD=1` leaves the service disabled.
- **Assuming hot‑reload**: Changing environment variables does not affect a already‑running dashboard; you must restart the s6 service.
- **Permission denied on `/run/s6/container_environment`**: This directory is owned by root; the hermes user cannot write to it directly. Use s6‑provided mechanisms or restart the container with correct env.
- **Conflicting port mappings**: Ensure the host‑to‑container port mapping matches `HERMES_DASHBOARD_PORT` (e.g., `-p 8501:8501` if you set the internal port to 8501).
- **Tailscale subnet routes**: Verify that the Tailscale interface is up and that the advertised subnet includes the host's port.

- **Non-loopback bind requires auth provider**: Binding to `0.0.0.0` (non-loopback) REQUIRES a registered auth provider. The dashboard will refuse to start with: `Refusing to bind dashboard to 0.0.0.0 — the auth gate engages on non-loopback binds, but no auth providers are registered.`
  - **Fix**: Set `dashboard.basic_auth.username` + `password_hash` in `config.yaml`, or use `hermes config set dashboard.basic_auth.username <name>` and `hermes config set dashboard.basic_auth.password_hash <hash>`.
  - **Hash generation**: `python3 -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('your-password'))"`
  - **Local-only alternative**: Bind to `127.0.0.1` instead (no auth required), then tunnel via SSH/Tailscale.
  - ⚠️ `HERMES_DASHBOARD_INSECURE` no longer works (hardened June 2026). Setting it prints a warning but is ignored.
- **Dashboard stuck/unreachable due to dual-gateway Telegram token conflict**: If the dashboard responds with HTTP 200/302 but appears stuck (stale data, unresponsive UI, models seemingly broken), the root cause may NOT be the dashboard — it may be gateway state corruption from two profiles fighting over the Telegram token.
  - **Symptom pattern**: dashboard opens but shows stale/no data; Telegram bot doesn't respond; model switching seems broken; user asks "正常了嗎" repeatedly.
  - **Root cause**: Profile A's gateway (e.g., research) starts while Profile B's gateway (e.g., default) already holds the Telegram token. The competing gateway can't authenticate Telegram, retries, and its retries corrupt the original gateway's internal state → entire routing stack degrades → dashboard reads from a corrupted gateway and appears stuck.
  - **Diagnosis**: (1) Check for multiple gateway processes: `ps aux | grep "hermes.*gateway" | grep -v grep`. (2) Look for "Telegram bot token already in use (PID X)" in gateway logs. (3) Check gateway log directory: `ls /opt/data/logs/gateways/` — if multiple profiles have gateway logs, that's the likely cause.
  - **Fix**: Kill the competing gateway process (`kill <competing-pid>`). The original gateway regains Telegram control within ~30s. No dashboard restart needed — the dashboard was always fine; it was reading from a corrupted gateway.
  - **Prevention**: A profile that does not need Telegram should not run its own gateway. If a profile needs a gateway but with a different Telegram token, configure one per profile. See `hermes-profile-management` → "Telegram token conflict between profiles" pitfall.
  - **⚠️ Don't confuse with s6 crash loop.** Dual-gateway case: normal CPU, port reachable (HTTP 200), dashboard UI loads — just stale data. s6 crash loop: 99% CPU, port closed, connection refused.

- **s6 stuck-process loop**: s6-supervise auto-restarts crashed dashboard processes. If the dashboard crashes repeatedly, s6 spawns new instances that also crash → CPU spikes to 99%. The port stays closed because no process successfully binds.
  - **Symptom**: `ps aux | grep dashboard` shows process with 99% CPU, but `curl` to port fails with connection refused.
  - **Fix**: Kill ALL dashboard processes (including s6-supervise managed ones), then fix the root cause (auth config, port conflict, etc.), then restart.
  - **Nuclear option**: `kill -9 $(pgrep -f "hermes dashboard")` then start fresh.

### 11. Remote Desktop Connection via `hermes serve`

Hermes Desktop (native Electron app) connects to a **remote `hermes serve`** process, NOT to `hermes dashboard`. They are different commands on the same binary.

| Command | Purpose | Auth required? | Serves UI? | Default port |
|---------|---------|---------------|-----------|-------------|
| `hermes dashboard` | Web admin panel | ✅ on non-loopback | ✅ Yes (HTML) | 9119 |
| `hermes serve` | Headless backend for Desktop App | ✅ on non-loopback | ❌ No (JSON-RPC/WS) | 9119 (use different) |

Both read the same auth env vars — dashboard basic-auth setup also enables `serve`.

#### Setup Steps

**Step 1: Auth credentials** (`/opt/data/.hermes/.env`)
```bash
cat >> /opt/data/.hermes/.env << 'EOF'
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=your-strong-password
HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)
EOF
chmod 600 /opt/data/.hermes/.env
```

**Step 2: Start `hermes serve`** (separate port — 9119 is usually dashboard)
```bash
hermes serve --host 0.0.0.0 --port 9120
```

**Step 3: Connect from Desktop App**
- Settings → Remote connection → toggle ON
- **Remote URL**: `http://dietpi4:9120` (or Tailscale IP)
- **Sign in** with the username/password from Step 1

#### Key Differences from Dashboard

| Aspect | `hermes dashboard` | `hermes serve` |
|--------|-------------------|----------------|
| Start command | `--host 0.0.0.0 --port 9119` | `--host 0.0.0.0 --port 9120` |
| Browser accessible | ✅ Yes (HTML UI) | ❌ No (REST+WS API only) |
| Desktop app compatible | ❌ No | ✅ Yes |
| s6 service | ✅ Built-in (`dashboard`) | ❌ Must run manually |
| `--tui` flag | ✅ Has it | ❌ Not needed |

#### Pitfalls

- **❌ `--insecure` is DEPRECATED (June 2026+).** Accepted but ignored — non-loopback always requires auth. Use basic auth env vars.
- **❌ No `--tui` flag on `hermes serve`.** Old blog-post advice about `--tui` is for `hermes dashboard` only. `serve` always exposes WebSocket.
- **⚠️ Port conflict.** If dashboard is on 9119, `serve --port 9119` fails EADDRINUSE. Use 9120.
- **⚠️ No s6 service** for `hermes serve` — container supervision only covers `dashboard` and `main-hermes` (gateway). Must run manually; won't survive restart without custom s6 service.
- **⚠️ Auth env vars read by process itself**, not forwarded by any wrapper. `.env` is canonical source.

#### Verification

```bash
ss -tlnp | grep 9120                           # listening?
curl -s -o /dev/null -w "%{http_code}" http://localhost:9120  # → 302 (auth req)
curl -c /tmp/sc.txt -X POST http://dietpi4:9120/auth/password-login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"basic","username":"admin","password":"your-password"}'
# → {"ok":true,"next":"/"}
curl -b /tmp/sc.txt -s -o /dev/null -w "%{http_code}" http://dietpi4:9120/  # → 200
```

#### Quick env-var method (desktop side)

```bash
export HERMES_DESKTOP_REMOTE_URL="http://dietpi4:9120"
export HERMES_DESKTOP_REMOTE_USERNAME="admin"
export HERMES_DESKTOP_REMOTE_PASSWORD="your-password"
# then launch Hermes.app / Hermes.exe
```

### 12. Verification Checklist (dashboard)
- [ ] `HERMES_DASHBOARD` is set to a truthy value.
- [ ] `HERMES_DASHBOARD_PORT` matches the host‑side port in `-p HOST:CONTAINER`.
- [ ] `s6-svstat /run/service/dashboard` shows `up` (pID and timeout).
- [ ] `ps` shows `hermes dashboard --host ... --port ...` running.
- [ ] Port is listening on `0.0.0.0` (or the specified host) and the correct port number.
- [ ] `curl http://<host>:$HERMES_DASHBOARD_PORT` returns a successful HTTP response (200).
- [ ] If using Tailscale, `tailscale ip -4` shows an address reachable from the client, and the same curl works via that IP.

## References
- Hermes Dashboard documentation: https://hermes-agent.nousresearch.com/docs/dashboard/
- s6-overlay service management: https://skarnet.org/software/s6-overlay/
- Environment variable precedence in Hermes containers: values in `/run/s6/container_environment` override Docker `-e` at service start time.
- **Dashboard status indicators & service topology**: `references/service-topology.md` — explains what each green light means, which services are expected in different configurations, and when a missing "API" light is normal.
- **Profile listing & visibility**: `references/profile-listing.md` — how the dashboard discovers profiles, Docker vs native paths, and why "ghost" profiles appear.

## Templates
- `templates/dashboard-env.example`: Example snippet for docker‑run or compose file.

## Scripts
- `scripts/check_dashboard.sh`: One‑liner to verify dashboard status (optional).