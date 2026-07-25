# 外部掃描器整合 (External Scanner Integration)

## 概述

本管線的 `daily_prices` 資料除了供自有策略分析使用，也透過 **`our_db.py` 橋接器** 餵給第三方開源專案 **tw-stock-radar**（台股數據獵手），讓它直接用本地資料庫而非 yfinance 網路抓取。

## 專案位置

```
/opt/data/tw-stock-radar/   ← 第三方專案（非 projects/ 下，注意！）
```

## 橋接器：our_db.py

> 位置：`/opt/data/tw-stock-radar/our_db.py`（267 行）

### 設計目標
讓 tw-stock-radar 的掃描引擎（`scan.py`）可以完全不連網，直接吃本地 `taiwan_stocks.db` 的資料。

### 技術實作

**資料讀取（唯讀模式，安全不搶 DB）：**
```python
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
```
- `mode=ro` → 唯讀，絕不會跟其他寫入者（如 `update_daily.py`）衝突
- 不受 WAL busy_timeout 問題影響

**支援的查詢介面：**
| Method | 用途 | 回傳格式 |
|--------|------|---------|
| `get_stock_data(code, months_back=9)` | 單股日線 OHLCV | pd.DataFrame (index=Date, cols=Open/High/Low/Close/Volume) |
| `get_stock_data_range(code, start, end)` | 指定日期範圍 | 同上 |
| `get_universe()` | 全市場股票清單 | [(code, name, industry), ...] |
| `get_fundamentals(code)` | 基本面（PE/PB/殖利率/EPS） | dict 與 load_fundamentals 相容 |
| `has_data(code)` | 檢查是否有價量資料 | bool |
| `latest_date()` | DB 最新日期 | str "YYYY-MM-DD" |

### 每日 Pipeline

```
16:00 ─ update_daily.py          → daily_prices 寫入 taiwan_stocks.db
                                    ↓
16:25 ─ our_db.py --export       → 唯讀讀取 daily_prices → 匯出 CSV 快取
         ↓
         └─ cache/*_TW.csv       ← 1920 檔 CSV（在 tw-stock-radar/cache/ 下）
                                    ↓
         └─ scan.py --cache --full → 吃本地 CSV 做強弱分/技術面/籌碼分析
                                    ↓
              state.json (333KB) + history.json (訊號記錄)
```

### 匯出行為

- `export_to_cache()` 方法：讀取全市場 → 每檔匯出成 `{代碼}_TW.csv`
- 資料不足 10 筆的股票會跳過（新股/剛恢復交易）
- 每 200 檔顯示一次進度
- 預設匯出過去 12 個月的資料
- 快取目錄：`/opt/data/tw-stock-radar/cache/`（約 22MB，1920 檔）

## 啟動狀態

| 元件 | cron | 狀態 |
|------|------|------|
| `our_db.py --export` + `scan.py --cache --full` | `twstock-daily-scan` (16:25 M-F) | ✅ 有跑 |
| `state.json` 產出 | 同上 | ✅ 333KB，最後 2026-07-17 |
| `history.json` 訊號 | 同上 | ✅ 17 檔 (5 long + 12 short) |
| `server.py` Dashboard (port 8899) | 無 | ❌ 未啟動 |

### 掃描產出範例

```json
{
  "code": "1439",
  "name": "雋揚",
  "side": "long",
  "score": 88.3,
  "reason": "SuperTrend 翻多，RSI 62 健康區，量能放大4.6x",
  "stop": 23.69,
  "tp1": 30.59,
  "tp2": 38.87
}
```

## Dashboard 啟動方式

若需要看深色 HUD 看板：

```bash
cd /opt/data/tw-stock-radar
/opt/data/.venv/bin/python3 server.py
# → http://0.0.0.0:8899
```

目前未納入 cron 自動啟動，因 dashboard 是視覺化工具非必要後端。

## 注意事項

1. **DB 不要放 projects/ 下**：tw-stock-radar 在 `/opt/data/tw-stock-radar/` 根目錄，非 projects/ 下
2. **掃描排程順序依賴**：`twstock-daily-scan` 在 16:25 跑，需等 16:00 的 `update_daily.py` 完成後才有最新資料
3. **`scan.py` 不吃 yfinance**：`--cache` 參數讓它只讀本地 CSV，永不連網
4. **server.py 非必要**：掃描本體（scan.py）持續產生 state.json/history.json，不開 dashboard 不影響數據產出
