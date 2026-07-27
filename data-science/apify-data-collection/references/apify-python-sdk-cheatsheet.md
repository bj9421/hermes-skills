# Apify Python SDK Quick Reference

## Client Initialization
```python
import os
from decimal import Decimal

from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_TOKEN"])
approved_budget = Decimal(os.environ["APIFY_MAX_TOTAL_CHARGE_USD"])
if not approved_budget.is_finite() or approved_budget <= 0:
    raise ValueError("APIFY_MAX_TOTAL_CHARGE_USD must be positive")
if os.environ.get("APIFY_APPROVE_PAID_RUN") != "yes":
    raise RuntimeError("Set APIFY_APPROVE_PAID_RUN=yes after approval")
```

## Run an Actor
```python
run = client.actor("username/actor-id").call(
    run_input={"key": "value"},
    max_items=10,
    max_total_charge_usd=approved_budget,
)
```

## Get Result
```python
# Small datasets — load all into memory
items = list(client.dataset(run.default_dataset_id).iterate_items())

# Large datasets: request bounded pages.
offset = 0
limit = 100
while True:
    page = client.dataset(run.default_dataset_id).list_items(
        offset=offset,
        limit=limit,
    )
    if not page.items:
        break
    for item in page.items:
        process(item)
    offset += len(page.items)

# Export bounded JSON bytes for a caller-controlled destination.
payload = client.dataset(run.default_dataset_id).get_items_as_bytes(
    item_format="json",
    limit=1000,
)
```

## Get Input/Output Variables
```python
# Actor's input schema
input_schema = client.actor("username/actor-id").get_input_schema()

# Actor's output schema
output_schema = client.actor("username/actor-id").get_output_schema()
```

## Common Actor IDs
| Purpose | Actor ID |
|---------|----------|
| Instagram Location Stats | `louisdeconinck/instagram-location-stats-scraper` |
| X Posts and Engagement | `xquik/x-tweet-scraper` |
| X Audiences and Overlap | `xquik/x-follower-scraper` |

## Pitfalls
- `list(iterate_items())` loads all results into memory. Use pagination for large datasets.
- Set `max_items` and `max_total_charge_usd` before every Actor run.
- Actor status must be `SUCCEEDED` before retrieving results
- `run.default_dataset_id` is only valid after a successful run

Actor listings:

- [X Tweet Scraper](https://apify.com/xquik/x-tweet-scraper)
- [X Follower Scraper](https://apify.com/xquik/x-follower-scraper)
