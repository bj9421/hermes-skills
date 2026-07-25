# Cron Schedule Recommendations

## Frequency Guidelines

| Activity | Recommended Schedule | Reason |
|----------|---------------------|--------|
| Memory scan | `every 180m` | Actual deployed schedule — balances freshness vs token cost |
| Stock data sync | `0 18 * * 1-5` | After market close, weekdays only |
| Session cleanup | `0 3 * * 0` | Weekly, Sunday 3 AM |
| Health check | `every 30m` | Frequent for critical services |

## Pitfalls

- **Too frequent** (< 1h): Burns tokens, creates noise in delivery
- **Too sparse** (> 12h): Facts get stale, user forgets context
- **Daily at fixed time**: Misses mid-day discoveries in active sessions

## Best Practice

Start with `every 6h`. User can adjust based on session activity level.
Active sessions (5+ turns/day) → consider `every 4h`.
Light sessions → `every 8h` is acceptable.
