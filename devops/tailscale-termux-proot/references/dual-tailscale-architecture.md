# Dual-Tailscale Architecture Decision

## Context

Single physical device (Redmi Note 10, Android 13 MIUI) with two Tailscale identities:

| Node | IP | Type | VPN Interface |
|------|----|------|---------------|
| `rmn10` | 100.108.117.92 | Android App (VPN) | `tun0` — kernel-level, routes all `100.x.x.x` |
| `ttha` | 100.112.137.111 | Termux CLI (bropines) | Virtual (userspace) — SOCKS5 on :1080 |

## The Conflict

When both run simultaneously on the same device:

```
Other tailnet node → 100.112.137.111:9229 (ttha)
    ↓
Phone WiFi interface
    ↓
Android VPN tun0 intercepts 100.x.x.x ✓
    ↓
❌ Packet goes to rmn10 (app), not ttha (Termux CLI)
❌ Termux services unreachable from tailnet
```

When only ttha runs:

```
Other tailnet node → 100.112.137.111:9229 (ttha)
    ↓
Phone WiFi interface
    ↓
No VPN tun0 — packet arrives at the OS
    ↓
ttha userspace daemon receives it ✓
    ↓
✅ Termux dashboard/CCTV reachable via tailscale serve
```

## Decision: Hybrid — Both Clients, Different Roles (2026-07-28 Verified)

**Current Architecture (Verified):** Both clients run simultaneously. The Android app handles phone browser access to other tailnet nodes, while ttha's `tailscale serve` exposes Termux services.

| Role | Component | Status |
|------|-----------|--------|
| Phone browser → dietpi4:9119 | rmn10 VPN | ✅ Verified — shows Hermes login page |
| Termux Dashboard → tailnet | ttha serve on 443 | ✅ Verified — HTTPS `302` at `ttha.taile76ad.ts.net` |
| TCP bridge fallback (app off) | ttha TCP proxy :9119 | ✅ Available (Python script) |
| Termux internal → tailnet | ttha SOCKS5 :1080 | ✅ Built-in |

### The One Limitation

When rmn10 VPN is active, **incoming** connections to ttha (`100.112.137.111`) are intercepted by the app's `tun0` interface before reaching the Termux userspace daemon. This means other tailnet nodes **cannot directly reach** ttha's services while the app VPN is on. Serve's HTTPS endpoint only works for connections initiated through the SOCKS5 proxy or from within Termux.

### User Workflow

1. **Daily**: Android app ON → phone browser reaches `http://100.78.85.64:9119` directly
2. **Tailnet to Termux**: Not needed for daily use (dashboard, CCTV are local or via serve)
3. **Fallback (app off)**: Start TCP bridge on ttha → phone browser reaches `http://192.168.1.105:9119`

**Note**: This choice accepts the routing limitation because phone-to-dietpi4 access is more frequent than external-to-Termux access.

### Setup

```bash
# 1. Authorize serve at tailnet level (one-time)
# https://login.tailscale.com/f/serve?node=<node_id>

# 2. Enable serve for a Termux service
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --bg 9229
```

### Verified Runtime Behavior

- **Default HTTPS port**: 443 (no `--https` flag needed for standard serve)
- **Domain**: `<node>.<tailnet>.ts.net` (e.g. `ttha.taile76ad.ts.net`)
- **TLS**: Let's Encrypt cert via ACME DNS-01 challenge (the `_acme-challenge` TXT record on the tailnet domain)
- **TLS is hostname-bound**: `curl https://100.112.137.111/` fails with `TLS alert internal error` — the cert is for `.ts.net`, not the Tailscale IP. Must use hostname.
- **Backend**: tailscaled terminates TLS, proxies HTTP to the local target port (e.g. `https://ttha.taile76ad.ts.net/ → http://127.0.0.1:9229`)
- **Verified**: `curl --socks5-hostname localhost:1080 -k https://ttha.taile76ad.ts.net/` returns `HTTP/2 302 → /login?next=%2F` (Hermes dashboard login) ✅

### Management

```bash
# Check config
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve status

# Disable
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --https=443 off
```

### Routing Reality

The serve daemon runs inside ttha's userspace stack. When rmn10 VPN is also active:
- **Outgoing (phone browser → dietpi4)**: ✅ Works via rmn10 VPN
- **Incoming (other tailnet node → ttha serve)**: Traffic arrives at the phone's WiFi interface, intercepted by rmn10 VPN before reaching ttha userspace daemon → ❌ ttha can't receive
- **Workaround**: Access ttha services via **rmn10's IP** (100.108.117.92) and use the Android app's own port forwarding instead

## SOCKS5 Proxy for Outbound

ttha uses `--tun=userspace-networking`, meaning there's no kernel TUN interface. To make TCP connections FROM Termux TO other tailnet nodes:

```bash
# Direct connection fails
$ curl http://100.78.85.64:9119/
→ Network is unreachable

# Via SOCKS5 proxy works
$ curl --socks5 127.0.0.1:1080 http://100.78.85.64:9119/
→ HTTP/1.1 200 OK
```

The SOCKS5 proxy is built into tailscaled (`--socks5-server=localhost:1080`).

## TCP Bridge for Inbound (from LAN)

When the Android Tailscale app is off and the phone needs to reach other tailnet nodes:

```
Phone browser → 192.168.1.105:9119 (ttha LAN IP)
    ↓
ttha Python TCP proxy (tailscale-socks-proxy.py)
    ↓
SOCKS5 127.0.0.1:1080
    ↓
dietpi4:9119 (100.78.85.64)
    ↓
HTTP/1.1 302 Found (Hermes dashboard login)
```

The Python script (`scripts/tailscale-socks-proxy.py` in this skill) creates a bidirectional TCP forwarder that works for any TCP protocol (HTTP, WebSocket, SSH, etc.).

**Important:** socat's SOCKS4A mode does NOT work with Tailscale's SOCKS5 server. The Python script is required.

## Current haup.sh Integration

`~/scripts/haup.sh` auto-starts:
1. `tailscale` tmux session → proot + tailscaled
2. `hermes-gw` tmux session → hermes gateway run
3. `cctv-map` tmux session → CCTV Taiwan Map (uvicorn)
4. Dashboard foreground → hermes dashboard --port 9229