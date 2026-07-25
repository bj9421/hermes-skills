# Apify Python SDK Quick Reference

## Client Initialization
```python
from apify_client import ApifyClient
client = ApifyClient("YOUR_API_TOKEN")
```

## Run an Actor
```python
run = client.actor("username/actor-id").call(run_input={"key": "value"})
```

## Get Result
```python
# Small datasets — load all into memory
items = list(client.dataset(run.default_dataset_id).iterate_items())

# Large datasets — paginated
page = client.dataset(run.default_dataset_id).get_items_page(page_number=0)
for item in page.items:
    process(item)

# Download as JSON file
client.dataset(run.default_dataset_id).download_items_as_json(filename="output.json")
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

## Pitfalls
- `iterate_items()` loads ALL results into memory — use pagination for large datasets
- Actor status must be `SUCCEEDED` before retrieving results
- `run.default_dataset_id` is only valid after a successful run
