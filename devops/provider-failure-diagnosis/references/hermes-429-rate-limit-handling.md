# Hermes 429 / Rate-Limit Handling (researched 2026-08-01, v0.18.2)

Answers the recurring question: "how do I enable/configure the rate limiter?"

## TL;DR

**Hermes has NO on/off "rate limiter" toggle.** 429 handling is built-in and automatic. The only tunable knob in v0.18.2 is `agent.api_max_retries` (default 3). Configurable per-model RPM is still an **open feature request** (#31802, P3 — not implemented as of 2026-08-01).

## Built-in 429 flow (automatic, no config needed)

```
API returns HTTP 429
   │
   ├─ 1. Read Retry-After header → wait that many seconds (capped 120s)
   │      (PR #3809, merged 2026-03 — user-friendly 429 message: "⏱️ Rate limit reached. Waiting 7s...")
   │
   ├─ 2. No header → jittered exponential backoff: 5s × 2^n (±20% jitter), cap 120s
   │
   ├─ 3. Retries exhausted (api_max_retries, default 3) →
   │      automatically switch to fallback_providers chain
   │
   └─ 4. Credential pool (multiple keys per provider) → rotate keys, skip exhausted
```

## What you can tune

| Knob | Command | Default | Notes |
|------|---------|---------|-------|
| Retry count | `hermes config set agent.api_max_retries N` | 3 | Lower → fast fallback on 429; higher → stick with primary longer |
| Fallback chain | `hermes fallback` (interactive) or `fallback_providers:` in config.yaml | — | Tried in order after retries exhausted |
| MCP server RPM | `max_rpm: N` in MCP server config | 10 | Per-server request cap, enforced in `tools/mcp_tool.py` |

## Open feature requests / PRs (may land later — re-check before claiming absent)

- **#31802** — Configurable per-minute rate limiting (RPM) for models. OPEN, P3. ← the "rate limiter switch" people look for
- **#49031** — Configurable retry backoff: `retry_backoff_base` (5.0), `retry_backoff_max` (120.0), `retry_429_cooldown` (0). OPEN
- **PR #27858** — `agent.eager_rate_limit_fallback` (default `true`): on 429 fail over to fallback immediately; `false` retries primary first. OPEN. Billing errors (402) always fail over eagerly regardless.
- **#5570 / #8486** — configurable max API retries + stream retries with smarter backoff. OPEN.

## Auxiliary tasks (vision, compression, session_search, title gen)

- 429s in the auxiliary client DO trigger the fallback chain since `f8ba265` (2026-04-21) — before that, aux tasks burned all 3 retries against the same rate-limited endpoint.
- Nous Portal has a cross-session rate guard: `$HERMES_HOME/rate_limits/nous.json` records 429 reset time so all sessions (CLI/gateway/cron/aux) check before calling Nous again — prevents retry amplification (up to 9 API calls per turn per 429).

## Diagnosis recipe

When a provider keeps 429ing:
1. Confirm it's really 429 (log: `error_type=RateLimitError provider=X`), not 402 (billing — permanent, always falls back eagerly).
2. Check `agent.api_max_retries` in config — if primary is a strict-quota provider, raising retries just adds load; better to rely on fallback chain.
3. Check whether `fallback_providers` is configured at all (`grep -A5 fallback_providers config.yaml`).
4. For Nous specifically: inspect `rate_limits/nous.json` reset_at — Hermes self-throttles until that timestamp.
5. If multiple sessions/crons hit the same key concurrently (compression + title gen + session_search), that alone can trigger 429s on strict-concurrency providers (e.g. Alibaba Coding Plan Pro pattern from #49031).
