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

### 4. SQLite Timezone Mismatch (Apify + SQLite pipelines)

SQLite's `datetime('now')` returns **UTC**, while Python's `datetime.now()` returns **local time**. If you INSERT records using a Python-local date but query with `datetime('now')`, you won't find them.

```python
# ❌ WRONG — different dates
snapshot_date = datetime.now().strftime("%Y-%m-%d")  # local: 2026-07-28
c.execute("INSERT INTO stats (date) VALUES (?)", (snapshot_date,))
c.execute("SELECT * FROM stats WHERE date = datetime('now')")  # UTC: 2026-07-27 → 0 rows!

# ✅ CORRECT — use Python variable consistently
snapshot_date = datetime.now().strftime("%Y-%m-%d")
c.execute("INSERT INTO stats (date) VALUES (?)", (snapshot_date,))
c.execute("SELECT * FROM stats WHERE date = ?", (snapshot_date,))  # ✅
```

## ⚠️ Cost Estimation Pitfall

**Always check the Actor's Pricing tab before estimating costs.** Different actors on the same platform can have wildly different pricing models:

| Actor | Pricing Model | Free Tier Cost (50 locations/day) |
|---|---|---|
| `louisdeconinck/instagram-location-stats-scraper` | $0.10 start + $10/1,000 results | ~$15/month ❌ |
| `apify/instagram-scraper` (official) | $2.70/1,000 results (free plan) | ~$4/month ✅ |

**Rule:** Before using any Actor, visit `https://apify.com/{actor-slug}/pricing` and check:
1. Is it Pay-Per-Event (PPE) or Pay-Per-Usage (compute units)?
2. What's the per-result cost on the **Free** plan tier?
3. Is there an Actor start fee on top of per-result?

Multiply: `locations × days × cost_per_result + (start_fee × days)` = monthly estimate.

## Example: Instagram Location Scraper (Official)

Uses `apify/instagram-scraper` with `searchType: "place"` to find locations by name.

```python
from apify_client import ApifyClient
import time

ACTOR_ID = "apify/instagram-scraper"

def search_place(client, location_name):
    """Search for a place by name, return top result."""
    run = client.actor(ACTOR_ID).call(run_input={
        "search": location_name,
        "searchType": "place",
        "searchLimit": 1,
        "resultsType": "details",  # metadata only, no posts
    })
    if run.status != "SUCCEEDED":
        return None
    dataset = client.dataset(run.default_dataset_id)
    items = list(dataset.iterate_items())
    return items[0] if items else None

# Usage: one API call per location (~56s each)
client = ApifyClient(token)
for name in location_names:
    item = search_place(client, name)
    if item:
        mc = item.get("media_count")  # total posts at this location
        ig_id = item.get("location_id")  # Instagram's numeric ID
    time.sleep(1)  # rate limit courtesy
```

### Key Details
- **Input:** `search` (string, one location name), `searchType: "place"`, `searchLimit: 1`, `resultsType: "details"`
- **Output fields:** `name`, `media_count`, `category`, `location_id` (IG numeric), `lat`, `lng`, `location_address`, `location_city`
- **Limitation:** Each search is a separate API call (~56s). Cannot batch multiple location names in one call.
- **When location IDs are NOT Instagram IDs** (e.g., Tourism Bureau `Attraction_...` format), must use search-by-name — cannot construct IG URLs.

## Deprecated: Community Instagram Location Stats Scraper

`louisdeconinck/instagram-location-stats-scraper` — 10× more expensive than official, less maintained (12 monthly users vs 37K). Used batch `locations: [id_array]` input. **No longer recommended.**

## References

- `references/apify-python-sdk-cheatsheet.md` — Quick reference for common Apify SDK operations
- `references/apify-actor-instagram-location-stats.md` — Details on the old community Instagram location scraper actor (deprecated)
