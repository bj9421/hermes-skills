---
name: tailscale-termux-proot
title: "Tailscale on Termux (Android 13+ MIUI)"
description: "Setup Tailscale CLI on Termux with proot workaround for Android 13+ seccomp restrictions (Redmi Note 10 / MIUI)"
---

# Tailscale on Termux (Android 13+ MIUI)

## When to use
Android 13+ device where `tailscale-termux-cli` (bropines) installs but the daemon can't exec `ifconfig` due to Android seccomp blocking Go 1.26+ `clone3`/`posix_spawn` syscalls.

## Symptoms
- `tailscaled` starts but `link state: interfaces.State{ifs={} v4=false v6=false}`
- Log shows: `[Termux] ifconfig exec error: fork/exec /usr/bin/ifconfig: permission denied`
- `tailscale up` times out with `url=false`
- `ifconfig` works fine from shell but fails from within Go binary

## Root cause
Go 1.26's `os/exec` uses `clone3`/`posix_spawn` which Android 13+ seccomp blocks for `untrusted_app` domain. The bropines patch's `exec.Command("ifconfig")` always fails → returns empty interface list → daemon thinks no network.

## Solution: proot

### 1. Install bropines tailscale-termux-cli
```bash
curl -fsSL https://raw.githubusercontent.com/bropines/tailscale-termux-cli/main/remote-install.sh | bash
```

### 2. Generate auth key
Go to https://login.tailscale.com/admin/settings/keys → generate reusable auth key.

### 3. Start daemon under proot
```bash
# Stop runsv from auto-managing tailscaled
touch $PREFIX/var/service/tailscaled/down
sv down $PREFIX/var/service/tailscaled 2>/dev/null || true
pkill -9 -f "runsv.*tailscale" 2>/dev/null || true
pkill -9 tailscaled 2>/dev/null || true
sleep 1
rm -f ~/.tailscale/tailscaled.sock

# Start under proot (ptrace-based syscall interception)
proot -b /proc -b /sys tailscaled \
    --statedir="$HOME/.tailscale" \
    --socket="$HOME/.tailscale/tailscaled.sock" \
    --tun=userspace-networking \
    --socks5-server=localhost:1080
```

### 4. Authenticate
```bash
tailscale --socket="$HOME/.tailscale/tailscaled.sock" up --auth-key=tskey-auth-xxxxx
```

### 5. Verify
```bash
tailscale --socket="$HOME/.tailscale/tailscaled.sock" status
```

Expected output:
```
100.112.137.111  tailscale-termux  user@  android  ●
```

## Auto-start via tmux + haup.sh

Add to `~/scripts/haup.sh`:

```bash
if pgrep -f "proot.*tailscaled" >/dev/null 2>&1; then
    echo "⚠️  Tailscale daemon 已在執行"
else
    touch $PREFIX/var/service/tailscaled/down 2>/dev/null || true
    sv down $PREFIX/var/service/tailscaled 2>/dev/null || true
    pkill -9 -f "runsv.*tailscale" 2>/dev/null || true
    pkill -9 tailscaled 2>/dev/null || true
    sleep 1
    rm -f ~/.tailscale/tailscaled.sock

    tmux new-session -d -s tailscale \
      "proot -b /proc -b /sys tailscaled \
          --statedir=\"$HOME/.tailscale\" \
          --socket=\"$HOME/.tailscale/tailscaled.sock\" \
          --tun=userspace-networking \
          --socks5-server=localhost:1080"
fi
```

## Serving Ports via Tailscale Serve

If you need other tailnet devices to reach services on ttha (dashboard, CCTV map, etc.):

```bash
# 1. Enable Serve at tailnet level first
#    Visit the URL shown by:
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --bg 9229
#    → "Serve is not enabled on your tailnet. To enable, visit:"
#    → https://login.tailscale.com/f/serve?node=...

# 2. After enabling in browser, run again:
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --bg 9229
#    → Creates HTTPS proxy: https://<node>.<tailnet>.ts.net/ → http://127.0.0.1:9229
```

⚠️ **Serve is NOT enabled by default** — the user must authorize it at the tailnet level via the admin console URL shown in the error message.

### Serve Runtime Details

- **Default port**: `--bg` with no `--https` flag uses **443** (HTTPS)
- **Domain format**: `<node>.<tailnet>.ts.net` (e.g. `ttha.taile76ad.ts.net`)
- **Certificate**: Tailscale automatically provisions a Let's Encrypt cert via DNS-01 ACME challenge (creates `_acme-challenge.<node>.<tailnet>.ts.net` TXT record)
- **TLS bound to hostname, not IP**: curling `https://100.x.x.x/` fails with `TLS alert internal error`; must use the `.ts.net` hostname
- **Testing from Termux**: use the SOCKS5 proxy to reach the serve URL:
  ```bash
  curl -s --socks5-hostname localhost:1080 -k https://ttha.taile76ad.ts.net/
  # → HTTP/2 302 → /login?next=%2F  (Hermes dashboard login page)
  ```
- **Backend**: tailscaled terminates TLS, proxies HTTP to the local target port

### Managing Serve Config

```bash
# Check current config
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve status
# → https://ttha.taile76ad.ts.net/ → proxy http://127.0.0.1:9229

# Disable serve
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --https=443 off
```

## Dual-Tailscale Architecture (Android App + Termux CLI + Serve)

### Verified Setup (2026-07-28)

The current production architecture keeps **both** clients running for different roles:

| Component | Role | Method |
|-----------|------|--------|
| **rmn10 (Android App, 100.108.117.92)** | Phone browser → other tailnet nodes | ✅ VPN `tun0` routes `100.x.x.x` directly |
| **ttha (Termux CLI, 100.112.137.111)** | Expose Termux services to tailnet | ✅ `tailscale serve --bg 9229` via HTTPS |
| **SOCKS5 proxy (:1080)** | Termux outbound to tailnet | ✅ Built into tailscaled userspace |

**Phone browser → dietpi4:9119** — ✅ Verified working via Android app VPN, showing Hermes login page.

**ttha serve → Dashboard** — ✅ Verified working. Accessible at `https://ttha.taile76ad.ts.net/` from SOCKS5-proxied clients. Returns `HTTP/2 302 → /login`.

### The One Conflict

| Scenario | Result |
|----------|--------|
| rmn10 active → browser reaches `dietpi4:9119` | ✅ Direct via VPN |
| rmn10 active + other tailnet node → ttha serve | ❌ VPN intercepts `100.x.x.x` traffic before ttha userspace daemon can receive it |
| rmn10 off → phone browser reaches tailnet | ❌ No route → use TCP bridge below |
| rmn10 off → ttha SOCKS5 + TCP bridge | ✅ Works (Python TCP proxy on LAN IP) |

**Rule**: Only one client can **receive** incoming connections at a time. The Android app's kernel-level VPN catches all `100.x.x.x` before the userspace ttha daemon sees them. Serve only works for outbound-initiated connections (via SOCKS5).

### TCP Bridge Fallback (app off)

When rmn10 is off, use the Python TCP proxy to bridge tailnet services to the LAN:

```bash
python3 ~/scripts/tailscale-socks-proxy.py 9119 100.78.85.64 9119
# → Phone browser → 192.168.1.105:9119 → SOCKS5 → dietpi4:9119
```

See `references/dual-tailscale-architecture.md` for the full architecture decision document.

## Accessing Other Tailnet Services from ttha (Outbound)

In `--tun=userspace-networking` mode, ttha has **no kernel-level Tailscale interface**. TCP connections to other tailnet IPs (`100.x.x.x`) will fail with "Network is unreachable" because the OS doesn't know how to route those addresses. Use the daemon's built-in **SOCKS5 proxy** at `localhost:1080`:

```bash
# curl via SOCKS5
curl -s --socks5 127.0.0.1:1080 http://100.78.85.64:9119/

# Python requests via SOCKS5
# pip install pysocks
import requests
resp = requests.get("http://100.78.85.64:9119/", proxies={
    "http": "socks5://127.0.0.1:1080",
    "https": "socks5://127.0.0.1:1080",
})
```

### TCP bridge: expose tailnet service on LAN

When the Android Tailscale app is off, the phone's browser has no route to `100.x.x.x` IPs. Use a TCP forwarder on ttha to bridge a tailnet service to the LAN interface:

```bash
# Option A: Python proxy script (see scripts/tailscale-socks-proxy.py)
python3 ~/scripts/tailscale-socks-proxy.py 9119 100.78.85.64 9119
# → ttha:9119 (LAN) → SOCKS5 → dietpi4:9119 (tailnet)

# Then from any LAN device: http://192.168.1.105:9119
```

The script creates a bidirectional TCP forwarder via the daemon's SOCKS5 proxy. Works for HTTP, WebSocket, SSH, any TCP protocol.

**Kill**: `pkill -f "tailscale-socks-proxy"` or Ctrl-C.

⚠️ **socat's SOCKS4A does NOT work** with Tailscale's SOCKS5 server — the Tailscale daemon only speaks SOCKS5, not SOCKS4/4A. Use the Python script above instead.

⚠️ **Port TIME_WAIT**: after killing a proxy on port `N`, restarting on the same port within ~30s may fail with "Address already in use". Use a different port or wait for TIME_WAIT to expire.

## Notes
- proot's ptrace interception allows Go binary's `os/exec` to work where direct exec fails
- After successful auth, `--auth-key` is not needed again (state is saved)
- Kill daemon: `tmux kill-session -t tailscale`
- The `down` file prevents termux-services/runit from interfering
- Only affects Xiaomi/MIUI (and similar strict SELinux) devices; Pixel/AOSP works without proot
- `proot` must stay running with `-b /proc -b /sys`; killing proot kills the daemon
- Port 9119 may remain in TIME_WAIT after killing a proxy — use a different port or wait 30s