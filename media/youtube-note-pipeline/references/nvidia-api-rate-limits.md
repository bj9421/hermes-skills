# NVIDIA NIM API Rate Limits (Free Tier)

## Limit: 40 RPM (community baseline)

- **Not an official SLA** — NVIDIA does not publish rate limits. 40 RPM is the community-acknowledged baseline.
- **Per-model, per-key** — limits vary by model and depend on real-time global traffic.
- **Worker pool model** — error `503 ResourceExhausted: Worker local total request limit reached (48/48)` means the shared worker pool for your API key is full. ALL models share this pool.

## Cooldown: Unpredictable (30s to 2+ hours)

- **No official cooldown duration** — NVIDIA does not document this.
- Light throttle: 30-60 seconds, auto-recovers.
- Heavy throttle (popular models like Kimi, GLM): can last **2+ hours** still returning 429.
- Some users report "permanent lock" behavior — 429 persists even after 2 hours.
- **Cooldown depends on global platform traffic**, not just your usage.

## No Usage API / No Rate-Limit Headers

- **No `/usage` endpoint** — cannot check remaining quota programmatically.
- **No `X-RateLimit-*` headers** — response headers don't include rate limit info.
- **No `Retry-After` header** — must guess cooldown duration.

## Avoidance Strategy (our pipeline)

| Strategy | Implementation |
|---|---|
| Min interval between calls | 2 seconds (`_rate_limit()` in all modules) |
| Concurrency | Sequential only — one pipeline at a time |
| Total per pipeline | ~5 API calls → ~10-15s total wait |
| Retry on 503 | Exponential backoff: 3s → 6s → 12s |
| Fallback models | deepseek-v4-flash → llama-3.3-70b → nemotron-70b |
| Post-throttle wait | At least 2-3 minutes before retrying after 503 |

## Key Findings from NVIDIA Forums (July 2026)

1. **Free tier is for prototyping only** — NVIDIA explicitly says it's not for production.
2. **No rate limit increase requests** — forum moderators close all RPM increase requests. The only path to higher limits is deploying your own NIM instance ($4,500/GPU/year).
3. **Popular models throttle faster** — Kimi K2.6, GLM 5.1 hit 429 below 40 RPM during peak traffic.
4. **Agentic workloads are worst case** — coding agents (Claude Code, OpenCode) fire dense parallel calls that instantly burst past 40 RPM. Our sequential approach avoids this.
5. **503 ≠ 429** — 503 is worker pool exhaustion (transient, recovers in seconds-minutes). 429 is true rate limit (longer cooldown).

## Reference

- NVIDIA Forums: https://forums.developer.nvidia.com/t/api-rate-limit-increase-is-not-granted-by-requesting-it-here/368420
- OmniRoute quota tracking issue: https://github.com/diegosouzapw/OmniRoute/issues/6846
- nvidia-api-rate-limiter proxy: https://github.com/imviren/nvidia-api-rate-limiter
