---
name: taiwan-tourism-data-pipeline
description: >-
  Download, parse, and import Taiwan Tourism Bureau open data (景點/餐飲/旅宿/活動) into SQLite.
  Covers data.gov.tw dataset discovery, CDN URL extraction, zip parsing, and normalized schema design.
---

# 🇹🇼 Taiwan Tourism Data Pipeline

Download the 4 Tourism Bureau open datasets, extract from JSON zip, and import into `ig_locations.db` (or any SQLite target).

## Data Sources

All datasets live on `data.gov.tw` under datasets **7777–7780**:

| Dataset | data.gov.tw | CDN filename | Record key | Rows (2026-07) |
|---------|-------------|--------------|------------|----------------|
| 景點 (Attractions) | `/dataset/7777` | `Attraction-json.zip` | `Attractions` | ~6,095 |
| 活動 (Events) | `/dataset/7778` | `Event-json.zip` | `Events` | ~824 |
| 餐飲 (Restaurants) | `/dataset/7779` | `Restaurant-json.zip` | `Restaurants` | ~3,689 |
| 旅宿 (Hotels) | `/dataset/7780` | `Hotel-json.zip` | `Hotels` | ~15,656 |

### ⚠️ CDN Naming Pitfall

The CDN filenames **do not** match what you'd guess from the dataset name:
```
❌ Food-json.zip  →  ✅ Restaurant-json.zip
❌ Activity-json.zip → ✅ Event-json.zip
✅ Attraction-json.zip
✅ Hotel-json.zip
```
**Always verify** by grepping the dataset page HTML before hardcoding.

## Step-by-Step

### 1. Discover download URLs

```bash
# Fetch data.gov.tw page (no browser needed — grep raw HTML)
curl -sL "https://data.gov.tw/dataset/7777" | grep -oP 'href="[^"]*json[^"]*"'

# Returns:
# href="https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip"
```

The CDN base is always: `https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/`

### 2. Download & extract

```bash
curl -sL --max-time 30 "$CDN_URL" -o /tmp/attractions.zip

python3 -c "
import zipfile, json
with zipfile.ZipFile('/tmp/attractions.zip', 'r') as z:
    with z.open('AttractionList.json') as f:
        data = json.load(f)
        records = data['Attractions']  # ← note the record key
        print(f'{len(records)} records')
"
```

**Note:** Server has no `unzip` binary — always use Python `zipfile`.

### 3. Schema design pattern

Each table gets:
- `id TEXT PRIMARY KEY` — from the source `*ID` field
- `name TEXT NOT NULL`
- `description TEXT`
- Type-specific codes (category/cuisine/hotel classes) as JSON text
- `city`, `address` — extracted from `PostalAddress` dict
- `lat REAL`, `lng REAL` — from `PositionLat`/`PositionLon`
- `phone TEXT` — first entry from `Telephones` list
- `image_urls TEXT` — JSON array
- `image_count INTEGER`
- `has_coords INTEGER DEFAULT 0` — for fast filtering
- `data_json TEXT` — full original record for later reference
- `created_at` / `updated_at` timestamps

**Indexes to create:**
```sql
CREATE INDEX IF NOT EXISTS idx_{table}_city ON {table}(city);
CREATE INDEX IF NOT EXISTS idx_{table}_coords ON {table}(lat, lng);
```

### 4. Extractor implementation pattern

Write one extractor per table that normalises the raw JSON into flat columns:

```python
def extract_attractions(record):
    addr = record.get('PostalAddress') or {}
    images = record.get('Images') or []
    return {
        'id': record['AttractionID'],
        'name': record.get('AttractionName', ''),
        'description': (record.get('Description') or '')[:5000],
        'category_codes': json.dumps(record.get('AttractionClasses') or []),
        'city': addr.get('City'),
        'address': addr.get('StreetAddress'),
        'lat': record.get('PositionLat'),
        'lng': record.get('PositionLon'),
        'phone': (record.get('Telephones') or [{}])[0].get('Tel') if record.get('Telephones') else None,
        'image_urls': json.dumps([i['URL'] for i in images if i.get('URL')]),
        'image_count': len([i for i in images if i.get('URL')]),
        'has_coords': 1 if record.get('PositionLat') and record.get('PositionLon') else 0,
    }
```

### 5. Bulk insert

```python
columns = ['name', 'description', 'category_codes', ...]  # no 'id'
placeholders = ', '.join(['?'] * (len(columns) + 1))
sql = f"INSERT OR REPLACE INTO {table} (id, {', '.join(columns)}) VALUES ({placeholders})"

for record in records:
    row = extractor(record)
    values = [row['id']] + [row.get(c) for c in columns]
    cur.execute(sql, values)
```

**Common bug:** the `columns` list must include ALL non-id columns including `data_json`. If bind-count mismatches, first check the columns list vs the CREATE TABLE statement.

## Verification

After import, run:

```sql
SELECT COUNT(*), SUM(has_coords), SUM(CASE WHEN description IS NOT NULL AND length(description)>20 THEN 1 ELSE 0 END)
FROM taiwan_attractions;
```

Expected: coords ≈ 100%, descriptions > 80% for attractions/events.

## Post-Import: Query Tool

After data is imported into `ig_locations.db`, use `blogger_ref.py` for interactive queries:

```bash
# Quick reference
bash /opt/data/scripts/blogref cities                        # 縣市資料量一覽
bash /opt/data/scripts/blogref attractions --city 臺南市      # 縣市景點
bash /opt/data/scripts/blogref search 老街                    # 跨表關鍵字搜尋
bash /opt/data/scripts/blogref categories                     # 分類代碼對照
bash /opt/data/scripts/blogref all --city 花蓮縣              # 縣市四表總覽
```

Main script: `ig-locations/scripts/blogger_ref.py`  
Shortcut: `/opt/data/scripts/blogref`

Supports filtering by city, category (by name or code), keyword, and limit. Outputs Emoji-formatted cards ready for use in travel articles.

## Pitfalls

- **CDN names are unintuitive.** Always grep the data.gov.tw HTML — don't guess `Food` vs `Restaurant`.
- **No `unzip` on server.** Use Python `zipfile`.
- **`POST` not supported by CDN.** Plain HTTPS GET only.
- **Record key is plural** (e.g. `Attractions`, `Events`, `Restaurants`), not singular.
- **PostalAddress is a dict**, not a flat string — extract city/street separately.
- **Empty zip (0 bytes)** means wrong URL — try a different filename.
- **Bind-count mismatch** = columns list doesn't match the INSERT statement. Every column in CREATE TABLE must have a corresponding entry in the columns list.

## Reference Files

- `references/data-gov-tw-discovery.md` — Exact `curl + grep` commands for CDN URL discovery, with verified URLs and filename pitfalls.

## Script

The canonical import script lives at `scripts/import_taiwan_data.py`. Run:
```bash
python3 /opt/data/ig-locations/scripts/import_taiwan_data.py
```

It handles all 4 datasets, creates tables if missing, and prints a summary.
