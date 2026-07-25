# Config File Safety — Overwrite Prevention

## The Danger
`write_file` tool blocks writes to `config.yaml` (security guard).
BUT terminal commands (`cp`, `mv`, `tee`) bypass this guard entirely.

**Result:** `cp profile/config.yaml config.yaml` WILL succeed and DESTROY the main config.

## Safe Restore Pattern (2026-07-13)

When config.yaml is accidentally overwritten:

```bash
# 1. Check damage
wc -l /opt/data/config.yaml
# If 45 lines instead of 700+, it was overwritten

# 2. Restore from profile backup
cp /opt/data/profiles/default/config.yaml /opt/data/config.yaml

# 3. Verify restoration
wc -l /opt/data/config.yaml
# Should be ~700+ lines

# 4. Verify critical sections exist
grep -c "llama-3.3-70b-versatile\|mixtral-8x7b-32768\|deepseek-r1-distill-llama-70b" /opt/data/config.yaml
# Should be >= 3 (groq models)

# 5. Restart gateway
# In Telegram: /restart
```

## Prevention Checklist

Before ANY file operation on config.yaml:
1. **Diff first:** `diff /opt/data/config.yaml /opt/data/profiles/default/config.yaml`
2. **Backup first:** `cp /opt/data/config.yaml /opt/data/config.yaml.bak.$(date +%s)`
3. **Use `hermes config set`** for individual settings — it's safer than bulk writes
4. **NEVER use `write_file` on config.yaml** — use `patch` or `hermes config set` instead
5. **NEVER use `cp` to overwrite config.yaml** — profile configs lack main-config-specific settings

## Why `write_file` Blocks config.yaml
The `write_file` tool has a security guard that detects paths containing `config.yaml` and blocks them to prevent accidental destruction of critical settings. This is a good safety net — but terminal commands don't have this protection.

## Session Source
Captured 2026-07-13: agent overwrote 700-line config.yaml with a 45-line file via `write_file`, then recovered by copying from profile config. Lesson: always diff before copy, always backup before overwrite.