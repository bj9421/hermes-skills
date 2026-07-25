# Hermes Service Topology & Dashboard Status Indicators

## Services Overview

Hermes runs several independent processes under s6 supervision:

| Service | Command | Purpose | Dashboard Indicator |
|---------|---------|---------|-------------------|
| **Dashboard** | `hermes dashboard` | Web UI (port 9119) | "Dashboard" — always on when running |
| **Gateway (per profile)** | `hermes gateway run` | Message relay for Telegram / Slack / etc. | "Telegram" (or platform label) |
| **API Server** | `hermes serve` | JSON-RPC/WebSocket for desktop app & remote clients | "API" |
| **Proxy** | `hermes proxy start` | OpenAI-compatible local proxy for OAuth providers | Not shown on dashboard |

## What the Green Lights Mean

The dashboard shows status indicators for:

1. **Telegram / Gateway** — one per connected gateway profile. Multiple green = multiple profiles with active gateways.
2. **API** — lit when `hermes serve` is running. This is an **optional** service for desktop app / programmatic clients.
3. **Dashboard** — the web UI itself (always green when you're viewing it).

## Normal Configurations

### Telegram-only (most common)
```
✅ Telegram (default)    — gateway for Telegram
✅ Telegram (research)   — gateway for research profile (if configured)
✅ Dashboard              — web UI
❌ API                    — NOT running (normal)
```

### Full setup (with desktop app or remote clients)
```
✅ Telegram
✅ API                    — hermes serve running
✅ Dashboard
```

### Multi-profile with coder gateway (this session's setup)
```
✅ Telegram (default)    PID 146  — `hermes gateway run --replace`
✅ Telegram (research)   PID 472  — `hermes -p research gateway run --replace`
✅ Telegram (coder)      ready    — `hermes -p coder gateway run --replace`
✅ Dashboard             PID 126  — port 9119
❌ API                            — NOT running (normal for Telegram-only workflows)
```

## How to Start the API Server

Only needed if you use the Hermes desktop app or programmatic clients:

```bash
# Start the serve (API) service
hermes serve --host 0.0.0.0 --port <port>

# Or check its status
hermes serve --status
```

**Caveat**: If the dashboard already binds to port 9119, use a different port for `serve` (e.g., 8642).

## Diagnostic Commands

```bash
# See what Hermes processes are running
ps aux | grep "hermes" | grep -v grep

# List all active s6 services
ls /run/service/

# Check dashboard port binding
cat /proc/net/tcp | awk '{print $2}' | cut -d: -f2 | sort -un | while read p; do [ "$p" != "0" ] && printf "port %d\n" 0x$p; done
```

## Key Principle

**Gateways ARE the API for Telegram** — they receive messages, process them via the agent, and respond. `hermes serve` is an *additional* API for external clients, not required for normal chat operation. An "API" light off on the dashboard is expected and fine when you only use Telegram messaging.
