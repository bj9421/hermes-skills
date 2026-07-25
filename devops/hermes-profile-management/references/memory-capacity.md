# Memory Capacity Troubleshooting

## Problem
Memory tool fails with "Replacement would put memory at X/Y chars" errors. Batch operations also fail with "Memory consolidation failed N times this turn."

## Diagnosis

1. **Check config limit:**
   ```bash
   grep -A5 'memory:' /opt/data/.hermes/config.yaml
   ```
   Look for `memory_char_limit` and `user_char_limit`.

2. **Compare with actual usage:**
   The system prompt shows current memory usage percentage (e.g., "MEMORY [98% — 2,161/2,200 chars]"). If actual usage exceeds `memory_char_limit`, the `holographic` provider may use a different calculation.

## Solution

### Option 1: Increase the limit (preferred)
```bash
hermes config set memory.memory_char_limit 8000
hermes config set memory.user_char_limit 4000
```
Then restart the session (`/reset` or new session).

### Option 2: Consolidate aggressively
Use a single `operations` array call that BOTH removes stale entries AND adds new ones:
```python
memory(operations=[
    {"action": "remove", "old_text": "..."},  # free space first
    {"action": "add", "content": "..."}        # then add
])
```

## Prevention
- Set `memory_char_limit` to at least 8000 on RPi deployments where many facts accumulate.
- Periodically review and remove stale entries (e.g., completed task progress, old dates).
- Use skills for procedural knowledge instead of memory entries.
