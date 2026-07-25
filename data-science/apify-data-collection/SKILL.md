---
name: apify-data-collection
description: "Collect data via Apify actors — venv setup, client usage, actor invocation, result ingestion, and common pitfalls."
version: 1.0.0
author: Hermes Agent
---

# Apify Data Collection

Collect data via Apify actors using the `apify-client` Python SDK. Covers venv setup, client initialization, actor invocation, result retrieval, and common pitfalls.

## Prerequisites

### 1. Create Project Venv (if missing)

Scripts that import third-party packages (e.g., `apify_client`) often fail with `ModuleNotFoundError` because the system Python has no extras installed.

```bash
cd /path/to/project
python3 -m venv venv
./venv/bin/python -m pip install apify-client
```

**Rule of thumb:** If the script imports `twstock` / `yfinance` / `pandas` → use `/opt/data/.venv/bin/python3`. If it imports a project-specific package like `apify_client` → create a project-local venv.

### 2. Token Authentication

Apify uses API tokens. Load from `.env` or environment variable:

```python
import os
TOKEN_KEY = "APIFY_TOKEN"
token = None
env_file = Path("/path/to/project/.env")
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith(TOKEN_KEY + "="):
                token = line.split("=", 1)[1]
                break
if not token:
    token = os.environ.get(TOKEN_KEY)
if not token:
    print("APIFY_TOKEN not set!")
    sys.exit(1)
```

## Basic Usage Pattern

### Initialize Client & Run Actor

```python
from apify_client import ApifyClient

client = ApifyClient(token)
ACTOR_ID = "username/actor-name"

run = client.actor(ACTOR_ID).call(run_input={
    "param1": "value1",
    "param2": ["list", "of", "values"],
})

if run.status != "SUCCEEDED":
    print(f"Actor failed: {run.status}")
    sys.exit(1)
```

### Retrieve Results

```python
dataset = client.dataset(run.default_dataset_id)
items = list(dataset.iterate_items())
# items is a list of dicts, one per result
```

### Alternative: Output Files (for large datasets)

For datasets too large for memory, use `client.dataset(...).get_items_page()` with pagination, or download output files via `client.dataset(...).download_items_as_json()`.

## Common Pitfalls

### 1. Wrong DB / File Path

The script may connect to a different DB file than expected. Always verify:

```python
# Check what DB the script actually uses
grep "DB_PATH\|connect(" /path/to/script.py
```

If the script creates an empty DB alongside an existing one, the data went to the correct DB — not the new empty one.

### 2. Actor Returns Fewer Items Than Expected

An Apify actor may return fewer results than the number of input items. Check:
- Input validation (invalid IDs get skipped)
- Actor logs (look for `requestsFailed` in the output)
- The actor's documentation for rate limits or input constraints

### 3. Token Not Found

The `.env` file may be in a different location than expected. Always check both `.env` file and `os.environ`.

## Example: Instagram Location Stats Scraper

This pattern was used for collecting Instagram location media counts:

```python
from apify_client import ApifyClient

ACTOR_ID = "louisdeconinck/instagram-location-stats-scraper"

client = ApifyClient(token)
run = client.actor(ACTOR_ID).call(run_input={
    "locations": location_ids,  # list of IG location IDs
})

dataset = client.dataset(run.default_dataset_id)
items = list(dataset.iterate_items())

for item in items:
    lid = str(item.get("location_id", ""))
    mc = item.get("media_count")
    # Save to SQLite...
```

## References

- `references/apify-python-sdk-cheatsheet.md` — Quick reference for common Apify SDK operations
- `references/apify-actor-instagram-location-stats.md` — Details on the Instagram location scraper actor used in this project
