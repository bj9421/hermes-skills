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
#    → Other tailnet nodes access via http://ttha:443 or http://100.x.x.x
```

⚠️ **Serve is NOT enabled by default** — the user must authorize it at the tailnet level via the admin console URL shown in the error message.

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

Use `scripts/tailscale-socks-proxy.py` to bridge a tailnet port to a local TCP port, so other LAN devices (phone browser, laptop) can reach it without the Android Tailscale app:

```bash
# ttha:9119 → SOCKS5 → dietpi4:9119 (Hermes dashboard)
python3 ~/scripts/tailscale-socks-proxy.py 9119 100.78.85.64 9119

# Then from any LAN device: http://192.168.1.105:9119
```

The script creates a TCP forwarder that:
1. Listens on `0.0.0.0:LISTEN_PORT`
2. Accepts inbound connections
3. Connects to destination via SOCKS5 proxy at `127.0.0.1:1080`
4. Pipes bidirectional data (works for HTTP, WebSocket, SSH, any TCP)

**Kill**: `pkill -f "tailscale-socks-proxy"` or SIGINT the process.

## Notes
- proot's ptrace interception allows Go binary's `os/exec` to work where direct exec fails
- After successful auth, `--auth-key` is not needed again (state is saved)
- Kill daemon: `tmux kill-session -t tailscale`
- The `down` file prevents termux-services/runit from interfering
- Only affects Xiaomi/MIUI (and similar strict SELinux) devices; Pixel/AOSP works without proot
- `proot` must stay running with `-b /proc -b /sys`; killing proot kills the daemon
- Port 9119 may remain in TIME_WAIT after killing a proxy — use a different port or wait 30s