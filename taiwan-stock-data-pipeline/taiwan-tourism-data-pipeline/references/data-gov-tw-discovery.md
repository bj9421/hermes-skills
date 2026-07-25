# data.gov.tw CDN URL Discovery

All Taiwan Tourism Bureau datasets live on `data.gov.tw` under dataset IDs **7777–7780**.

## The Problem

The `data.gov.tw` site is a React SPA — but the **raw HTML** returned by `curl` contains the CDN download links embedded in the page source. No headless browser needed.

## Discovery Command

```bash
curl -sL "https://data.gov.tw/dataset/{DATASET_ID}" | grep -oP 'href="[^"]*json[^"]*"'
```

## Verified CDN URLs (2026-07-17)

| Dataset | data.gov.tw | CDN URL |
|---------|-------------|---------|
| 景點 | `/dataset/7777` | `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip` |
| 活動 | `/dataset/7778` | `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Event-json.zip` |
| 餐飲 | `/dataset/7779` | `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Restaurant-json.zip` |
| 旅宿 | `/dataset/7780` | `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Hotel-json.zip` |

## Pitfall: CDN Base URL

The CDN base is `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/`. There's only one `v2.0` — no `v2.1` or different locale variants observed.

## Pitfall: Filename ≠ Dataset Name

The English filename does not always match the dataset category:
- **餐飲** → `Restaurant-json.zip` (not `Food`)
- **活動** → `Event-json.zip` (not `Activity`)

Always grep the HTML before hardcoding.

## Zip Contents

Each zip contains a single JSON file named `{Category}List.json` (e.g. `AttractionList.json`, `EventList.json`). The JSON wrapper key is the plural category name (e.g. `Attractions`, `Events`, `Restaurants`, `Hotels`).
