# Instagram Location Stats Scraper — Actor Details

## Actor
- **ID:** `louisdeconinck/instagram-location-stats-scraper`
- **Purpose:** Fetches media counts for a list of Instagram location IDs
- **Input:** `{"locations": ["location_id_1", "location_id_2", ...]}`
- **Output:** List of objects with `location_id`, `media_count`, `name`, `category`, `lat`, `lng`, `location_city`

## Usage in Project
Located at: `/opt/data/ig-locations/scripts/daily_collect.py`

The script:
1. Reads location IDs from SQLite `locations` table
2. Sends them to the Apify actor
3. Saves results to SQLite `location_stats` table
4. Generates top/bottom rankings

## Known Issues
- 1 of 28 locations may return no `media_count` (deactivated Instagram location)
- Actor completes in ~4 seconds for 28 locations (399 req/min throughput)
