---
name: ig-location-expansion
category: productivity
title: IG Taiwan 景點擴充與日常追蹤技能
description: 擴充 IG 追蹤地點至 100+ 個，使用 Tourism Bureau 官方資料搭配 Apify 抓取 Instagram 媒體數。
---

# IG Taiwan 景點追蹤

## 概述
從 Taiwan Tourism Bureau 官方資料庫（`taiwan_attractions` 表）選取景點，透過 Apify Instagram Scraper 每日抓取 `media_count`（該地點的 IG 貼文總數），追踪熱度變化。

## 架構
- **DB:** `/opt/data/ig-locations/data/ig_locations.db`
- **每日收集:** `/opt/data/ig-locations/scripts/daily_collect_official.py`
- **擴充腳本:** `/opt/data/ig-locations/scripts/final_expand.py`
- **Actor:** `apify/instagram-scraper`（官方版，非社群版）
- **Python:** `/opt/data/ig-locations/venv/bin/python3`

## 成本估算（2026-07 更新）

| 景點數/日 | 每日成本 | 每月成本 | 免費 $5 額度 |
|---|---|---|---|
| 5 | $0.014 | $0.41 | ✅ |
| 20 | $0.054 | $1.62 | ✅ |
| 50 | $0.135 | $4.05 | ✅（上限） |
| 100 | $0.27 | $8.10 | ❌ 需付費 |

**計價:** 官方 Instagram Scraper = $2.70 / 1,000 results（Free plan）。每次搜尋1個地點 = 1 result。

⚠️ **注意：** 社群版 `louisdeconinck/instagram-location-stats-scraper` 貴 4~10 倍（$10/1,000 + $0.10 啟動費），不建議使用。遷移到官方版前的舊估算（<$0.03/月）是錯的。

## 搜尋限制
- 地點 ID 是觀光署格式（`Attraction_...`），不是 Instagram ID
- **無法**構造 Instagram location URL，必須用 `search` 模式按名稱搜尋
- 每次搜尋 ~56 秒，50 個景點 ≈ 47 分鐘
- 無法批次搜尋多個地名（API 只接受單一搜尋字串）

## 每日脚本關鍵陷阱

### 🔴 SQLite 時區不一致
SQLite `datetime('now')` = UTC，Python `datetime.now()` = 本地時間（UTC+8）。INSERT 用本地日期、SELECT 用 `datetime('now')` 會查不到資料。**統一用 Python 變數傳入 SQL 參數。**

### 冪等性設計
每次跑之前先查 `location_stats WHERE snapshot_date = ?`（用 Python 本地日期），已存在的跳過不重抓，省 Apify 額度。

### DB Schema 注意
`locations` 表**沒有** `last_checked_at` 欄位。不要寫 UPDATE 去更新它。

## 安全注意
DROP TABLE 為 destructive 操作，執行前需使用者明確確認。建議先 rename 保留舊表再建新表。

## References
- `references/ig-location-expansion.md`：成本計算、DB schema、時區陷阱、搜尋限制
