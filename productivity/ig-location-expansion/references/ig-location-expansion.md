# IG Taiwan 地點擴充技術參考

## 資料來源
Taiwan Tourism Bureau open data: data.gov.tw/dataset/7777（景點 Attractions）
- 欄位：id, name, city, category_codes, lat, lng, image_count, has_coords
- 總筆數：6095 筆，其中 6073 筆有座標（has_coords=1），且 image_count > 0

## 擴充策略
1. 保留現有 28 個重點景點（中正、九份、日月潭等熱門打卡點）
2. 從 Tourism Bureau 資料中選取 image_count > 0 的景點，依 image_count 降序排列
3. 先確保每個縣市至少有 1-2 個代表（避免單一城市過度集中）
4. 剩余數量以最 image_count 的補充，直到總數達 100

## Apify 成本計算
- Actor: louisdeconinck/instagram-location-stats-scraper
- 定價模式：Pay per event（非按 CU 計費）
  - Actor start: $0.10 / 1000 runs = $0.0001/run
  - Result (每筆 location): $0.01 / 1000 = $0.00001/location
- 假設一次跑 100 個 locations + 平台使用（約 1GB x 1min ≈ 0.017 CU @ $0.2/CU ≈ $0.0034）
- 單次運行總成本 ≈ $0.0001*1 + $0.00001*100 + $0.0034 ≈ $0.0045
- 每月 30 次 × $0.0045 ≈ $0.135（遠低於免費額度 $5）

## SQLite 操作注意
- DROP TABLE 會永久删除表內容，執行前建議先備份或 rename
- 正確做法：
  ```sql
  ALTER TABLE locations_old RENAME TO locations_backup;
  CREATE TABLE locations_new (...);
  INSERT INTO locations_new SELECT ...;
  DROP TABLE locations_old;
  ALTER TABLE locations_new RENAME TO locations;
  ```
- 或直接使用 INSERT OR REPLACE 在臨時表上操作後再替換

## 常見問題
### Q: 為什麼有些景點的 city 字段是空的？
A: 部分 Tourism Bureau 資料中的 city 字段可能為空或格式不一致（如「臺北市」vs "台北市"），建議使用 COALESCE(city, 'Unknown') 處理。

### Q: category_codes 是什麼格式？
A: JSON array，例如 `["文化","古蹟"]`。解析時需用 json.loads(cls)[0] 取第一個類別。

### Q: Instagram location ID 和 taiwan_attractions 的 id 格式不同怎麼辦？
A: IG location ID 是數字（如 236326709），而 taiwan_attractions id 是字串格式（如 Attraction_A25000000E_000013）。在 locations 表中用 taiwan_attractions 的 id 作為 primary key 即可。