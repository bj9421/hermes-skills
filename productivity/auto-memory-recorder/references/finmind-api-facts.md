# FinMind API — Auto-Save Classification Example

Saved as fact #216 (2026-07-17). Use as a template for future API-related auto-saves.

## Raw Facts

| Fact | Category | Trust Score | Tags |
|------|----------|-------------|------|
| FinMind API error codes: 402 = quota exceeded, 403 = IP banned (auto-unban ~30 min). Free level1: 600 req/day. | general | 0.85 | api,finmind,ratelimit,error |

## Why Auto-Save?

- API error codes are **objective, verifiable** — not subjective
- Rate limits are **stable config** — they change slowly if at all
- Both are needed for future cron job troubleshooting
- Falls under `general` category (not project-specific, not user pref)

## Why NOT Report-Only

- The fact is a direct observation from API interaction, not analysis
- No human judgement needed to interpret "402 = quota exceeded"
- It's not task progress or session outcome — it's a durable API characteristic

## JSONL Format for Bulk Save

```json
{"content": "FinMind API error codes: 402 = quota exceeded, 403 = IP banned (auto-unban ~30 min). Free level1: 600 req/day.", "category": "general", "tags": "api,finmind,ratelimit,error", "trust_score": 0.85}
```
