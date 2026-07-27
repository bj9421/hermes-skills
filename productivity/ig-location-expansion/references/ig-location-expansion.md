# IG Taiwan 地點擴充技術參考

## 資料來源
Taiwan Tourism Bureau open data: data.gov.tw/dataset/7777（景點 Attractions）
- 欄位：id, name, city, category_codes, lat, lng, image_count, has_coords
- 總筆數：6095 筆，其中 6073 筆有座標（has_coords=1），且 image_count > 0

## 擴充策略
1. 保留現有 28 個重點景點（中正、九份、日月潭等熱門打卡點）
2. 從 Tourism Bureau 資料中選取 image_count > 0 的景點，依 image_count 降序排列
3. 先確保每個縣市至少有 1-2 個代表（避免單一城市過度集中）
4. 剩餘數量以 image_count 最高的補充，直到總數達 100

## Apify 成本計算（2026-07 更新：官方版）
- **Actor:** `apify/instagram-scraper`（官方，非社群版）
- **定價：** $2.70 / 1,000 results（Free plan）。每次搜尋 1 個地點 = 1 result。
- 50 locations/day: $0.135/天 = **$4.05/月**（免費 $5 額度內 ✅）
- ⚠️ **社群版** `louisdeconinck/instagram-location-stats-scraper` 貴 4 倍：$10/1,000 + $0.10/start，**不要用**

## DB Schema
```
locations (primary key: location_id TEXT — 觀光署 Attraction_* 格式)
  location_id, name, category, lat, lng

location_stats (daily snapshots)
  id INTEGER PK, location_id TEXT FK, snapshot_date TEXT, media_count INTEGER,
  name TEXT, category TEXT, city TEXT
```

⚠️ `locations` 表**沒有** `last_checked_at` 欄位。不要寫 UPDATE 語句去更新它。

## 🔴 SQLite 時區陷阱（重要）
SQLite 的 `datetime('now')` 返回 **UTC**，而 Python `datetime.now()` 返回**本地時間（UTC+8）**。

```python
# ❌ 錯誤：兩者不同步
snapshot_date = datetime.now().strftime("%Y-%m-%d")  # 本地時間
c.execute("INSERT ... VALUES (?, ...)", (snapshot_date,))  # 本地日期
c.execute("SELECT ... WHERE snapshot_date = datetime('now')")  # UTC 日期 → 查不到！
```

**正確做法：** 統一用 Python 的本地時間，SQL 查詢也用 Python 變數：
```python
snapshot_date = datetime.now().strftime("%Y-%m-%d")
c.execute("SELECT ... WHERE snapshot_date = ?", (snapshot_date,))  # ✅ 一致
```

## 冪等性設計（重跑安全）
每日脚本應檢查「今天是否已抓過」，避免重複花 Apify 額度：
```python
c.execute("SELECT location_id FROM location_stats WHERE snapshot_date = ?", (snapshot_date,))
already_done = {row[0] for row in c.fetchall()}
for lid, name in locations:
    if lid in already_done:
        skipped += 1
        continue
    # ... fetch and save
```

## 搜尋限制
- 地點 ID 是觀光署格式（`Attraction_...`），不是 Instagram ID
- **無法**構造 Instagram location URL，必須用 `search` 模式按名稱搜尋
- 每次搜尋 ~56 秒，50 個景點 ≈ 47 分鐘
- 無法批次搜尋多個地名（API 只接受單一搜尋字串）
- 部分小景點 IG 上無地標頁面（如社區博物館、季節性花季），會搜不到

## SQLite 操作注意
DROP TABLE 為 destructive 操作。建議 rename 舊表再建新表：
```sql
ALTER TABLE locations RENAME TO locations_backup;
CREATE TABLE locations_new (...);
INSERT INTO locations_new SELECT ...;
DROP TABLE locations_backup;
ALTER TABLE locations_new RENAME TO locations;
```

## 常見問題
### Q: 為什麼有些景點搜不到？
A: IG 上沒有對應地標頁面。常見於：小型藝文空間、社區博物館、季節性活動、離島小景點。處理方式：替換成同縣市其他景點，或簡化搜尋關鍵字。

### Q: category_codes 是什麼格式？
A: JSON array，例如 `["文化","古蹟"]`。解析時需用 `json.loads(cls)[0]` 取第一個類別。
