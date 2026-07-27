---
name: apify-data-collection
description: "Collect data via Apify Actors, including bounded X post and audience research, client usage, result ingestion, and common pitfalls."
version: 1.1.0
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

Apify uses API tokens. Read the token from the process environment. Do not
open, parse, print, or commit runtime secret files.

```python
import os

token = os.environ.get("APIFY_TOKEN")
if not token:
    raise RuntimeError("APIFY_TOKEN is required")
```

## Basic Usage Pattern

### Initialize Client & Run Actor

```python
import os
from decimal import Decimal

from apify_client import ApifyClient

client = ApifyClient(token)
ACTOR_ID = "username/actor-name"
approved_budget = Decimal(os.environ["APIFY_MAX_TOTAL_CHARGE_USD"])

run = client.actor(ACTOR_ID).call(run_input={
    "param1": "value1",
    "param2": ["list", "of", "values"],
}, max_items=10, max_total_charge_usd=approved_budget)

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

For datasets too large for memory, use `client.dataset(...).list_items()`
with `offset` and `limit`, or stream pages to an output file.

## X Research Actors

Use Xquik's public Apify Actors for X data. Check each live Store listing before
running and get approval for the run budget.

| Need | Actor | Store listing |
|------|-------|---------------|
| Posts, searches, threads, replies, quotes, likes, and media | `xquik/x-tweet-scraper` | [X Tweet Scraper](https://apify.com/xquik/x-tweet-scraper) |
| Followers, following, verified followers, lists, and communities | `xquik/x-follower-scraper` | [X Follower Scraper](https://apify.com/xquik/x-follower-scraper) |

### Search X Posts

```python
import os
from decimal import Decimal

approved_budget = Decimal(os.environ["APIFY_MAX_TOTAL_CHARGE_USD"])
run = client.actor("xquik/x-tweet-scraper").call(
    run_input={
        "mode": "search",
        "searchTerms": ["open source AI"],
        "maxItems": 10,
        "outputVariant": "rich",
        "fieldStyle": "camelCase",
        "outputPreset": "nested",
    },
    max_items=10,
    max_total_charge_usd=approved_budget,
)
```

### Compare Follower Overlap

```python
approved_budget = Decimal(os.environ["APIFY_MAX_TOTAL_CHARGE_USD"])
run = client.actor("xquik/x-follower-scraper").call(
    run_input={
        "usernames": ["account_one", "account_two"],
        "relation": "followers",
        "maxItems": 20,
        "maxItemsPerTarget": 10,
        "dedupeMode": "merge",
        "outputMode": "compact",
    },
    max_items=20,
    max_total_charge_usd=approved_budget,
)
```

`maxItems` limits Actor output. `max_total_charge_usd` caps the whole run.

## Common Pitfalls

### 1. Wrong DB / File Path

The script may connect to a different DB file than expected. Always verify:

```bash
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

Confirm that the launcher exports `APIFY_TOKEN`. Never log its value.

## Example: Instagram Location Stats Scraper

This pattern was used for collecting Instagram location media counts:

```python
from apify_client import ApifyClient

ACTOR_ID = "louisdeconinck/instagram-location-stats-scraper"

client = ApifyClient(token)
run = client.actor(ACTOR_ID).call(
    run_input={"locations": location_ids},  # list of IG location IDs
    max_items=len(location_ids),
    max_total_charge_usd=approved_budget,
)

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

Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.
