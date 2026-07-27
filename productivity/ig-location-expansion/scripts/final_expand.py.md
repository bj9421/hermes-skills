# final_expand.py 擴充腳本說明

## 功能
從 Taiwan Tourism Bureau 景點資料中選取指定數量（預設 100）的地點擴充至 locations 表，並保留當前追蹤的重點景點。

## 使用方式
```bash
cd /opt/data/ig-locations
python3 scripts/final_expand.py
```

## 流程
1. 讀取 taiwan_attractions 表（has_coords=1 且 image_count > 0）
2. 根據 CURRENT_NAMES 集合保留原有景點
3. 剩餘位置依 image_count 降序填入直到達到 TARGET
4. 建立 locations_new 表，插入所有選取的景點（含 name, category, lat, lng）
5. DROP 舊的 locations 表，將 locations_new rename 為 locations

## 注意事項
⚠️ 此操作會替換整個 locations 表！執行前請：
- 確認已有使用者明確授權
- 檢查 CURRENT_NAMES 列表是否完整包含需要保留的重要景點
- 建議先備份現有資料：cp data/ig_locations.db data/ig_locations.db.bak

## 相關檔案
- daily_collect.py：每日收集腳本，透過 Apify API 抓取 Instagram media count