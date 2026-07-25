# API Key Recovery Workflow

When API keys appear "missing" or "truncated" in Hermes, follow this diagnostic tree:

## Step 1: Check .env file (via terminal, not read_file)
```bash
python3 -c "
with open('/opt/data/.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            v = v.strip().strip('\"').strip(\"'\")
            if 'KEY' in k or 'TOKEN' in k:
                print(f'{k}: [{len(v)} chars]')
"
```

## Step 2: Check Docker env (gateway process)
```bash
# Find gateway PID
ps aux | grep 'hermes.*gateway' | grep -v grep
# Check its environ
python3 -c "
with open('/proc/<PID>/environ', 'rb') as f:
    env = f.read().decode('utf-8', errors='replace').split('\0')
for ev in env:
    if 'KEY' in ev or 'TOKEN' in ev:
        print(ev[:200])
"
```

## Step 3: Check config.yaml providers block
```bash
python3 -c "
import yaml
with open('/opt/data/config.yaml') as f:
    cfg = yaml.safe_load(f)
print('providers:', list(cfg.get('providers', {}).keys()))
print('custom_providers:', [cp.get('name') for cp in cfg.get('custom_providers', [])])
print('auxiliary.vision:', cfg.get('auxiliary', {}).get('vision', {}))
"
```

## Step 4: Understand the separation
| Source | What it controls |
|--------|-----------------|
| `.env` | Runtime API keys (Hermes gateway reads at startup) |
| `providers:` in config.yaml | Which providers appear in the model selector |
| `custom_providers:` in config.yaml | Custom endpoint providers (agnes, etc.) |
| `auxiliary.vision` in config.yaml | Vision model fallback config |
| Docker env vars | Process-level env (may supplement or override .env) |

## Key insight
Having a key in `.env` does NOT make it appear in the model selector. You need BOTH:
1. Key in `.env` (for runtime authentication)
2. `providers.<name>:` block in `config.yaml` (for selector visibility)

## Common key lengths (for verification)
| Key | Expected length | Notes |
|-----|----------------|-------|
| NVIDIA_API_KEY | ~70 chars | Starts with `nvapi-` |
| OPENROUTER_API_KEY | Variable | Starts with `sk-or-` |
| OPENCODE_ZEN_API_KEY | Variable | Starts with `sk-` |
| AGNES_API_KEY | Variable | Starts with `sk-` |
| FINMIND_API_KEY | Variable | JWT format |
| GROQ_API_KEY | ~56 chars | Starts with `gsk_` |

## Pitfalls
- **Secret redaction:** Hermes displays `.env` keys as `sk-xxx...yyy` in tool output. This is NOT truncation — the actual value is complete. Verify with Python `len()`.
- **Commented out keys:** `.env` may have `# KEY=value` (commented). Docker env may still have the real value.
- **Container vs host:** Docker env vars inside the container may differ from host env vars. Always check from inside the container.
