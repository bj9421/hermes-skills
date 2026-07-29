# OHLC 交叉比對驗證協定

> 資料庫 vs API 原始資料的收盤價驗證。用於偵測 `daily_prices` 表是否有異常價格。

## 架構概覽

```
┌──────────────────────────────────────────────────┐
│  cron trigger (M-F 16:00 / Sat 02:00)            │
│  └─> verify_ohlc.py (wrapper, 舊路徑相容)        │
│       └─> exec(verify_daily_prices.py)           │
│            ├─ fetch_ohlc_via_twstock(code, date)  │
│            │   ├─ twstock  (首選)                 │
│            │   └─ yfinance (備援 — 2026-07-11)   │
│            └─ Output: JSON + TXT → 新舊雙路徑    │
└──────────────────────────────────────────────────┘
```

## 腳本位置

| 路徑 | 說明 |
|------|------|
| `screening/verify_daily_prices.py` | **真實腳本**（主力，被 cron 透過 wrapper 引用） |
| `screening/verify_ohlc.py` | **wrapper**（`exec()` 呼叫真實腳本，cron 相容層） |
| `taiwan-stock-cashflow-api/screening/` | ⚠️ symlink 指向 `projects/` 下的真實目錄 |

### 為啥要有 wrapper？（2026-07-11 bug 記錄）

兩個 cron job（`ohlc-verification` 和 `ohlc-verification-full`）的 prompt 寫死 `verify_ohlc.py`，
但該腳本不存在（真實檔名 `verify_daily_prices.py`）。

**影響：** cron 顯示 status=ok（因為 `cd + python3 -u` 只是沒有找到檔案但沒報 exit code 非零），
實際驗證從未被執行。07-10 的「0/80 一致報告」就是因為腳本根本沒跑。

**修復：** 建立 `verify_ohlc.py` wrapper，用 `exec()` 載入真實腳本並傳遞所有參數，
cron prompt 不需修改。

## 資料來源備援

`fetch_ohlc_via_twstock(code, target_date)` 現在有雙層備援：

### 層級 1: twstock（首選）
```python
stock = twstock.Stock(code)
data = stock.fetch_from(year, month)
for d in data:
    if d.date.date() == target_date:
        return {date, open, high, low, close, source: "twstock"}
```

### 層級 2: yfinance（備援 — 2026-07-11 新增）
```python
tw_id = f"{code}.TW"
ticker = yf.Ticker(tw_id)
hist = ticker.history(start=target_date, end=target_date+1d)
if not hist.empty:
    return {date, open, high, low, close, source: "yfinance"}
```

兩者都失敗 → 回傳 `None`（計入 `api_fetch_failed`）。

**為何要備援：** twstock 的上游 TWSE API 不定時失靈（07-10 連續多小時全面 404），
無備援時 OHLC 驗證完全停擺。yfinance 路線不同（Yahoo Finance → 經由 yfinance 爬蟲），
通常互補。

## 輸出路徑（新舊雙寫）

| 檔案 | 新路徑 (primary) | 舊路徑 (compat) |
|------|-------------------|-----------------|
| JSON 明細 | `projects/.../screening/output/ohlc_verification_latest.json` | `taiwan-stock-cashflow-api/.../output/ohlc_verification_latest.json` |
| TXT 摘要 | 同上 | 同上 |

舊路徑的 `taiwan-stock-cashflow-api/` 目錄實際上只有 `screening/output/` 子目錄，
不含腳本本體。雙寫確保不管哪個路徑被引用都能讀到最新結果。

## 運作方式

```python
# 1. 從 screen_cache 隨機抽樣 80 檔（或 --full 全量 ~1925 檔）
# 2. 對每檔依序嘗試 twstock → yfinance 備援
# 3. 比對 db_close 與 api_close (tolerance=1%)
# 4. 輸出 JSON 明細（含 source 欄位標示資料來源）+ 文字摘要
# 5. 新舊兩路徑各寫一份
```

## 輸出格式

### JSON (`ohlc_verification_latest.json`)
```json
{
  "date": "2026-07-10",
  "mode": "SAMPLE",
  "total_sampled": 80,
  "matched": 0,
  "mismatched": 0,
  "errors": 80,
  "details": [
    {
      "stock_code": "2330",
      "db_close": 2415.0,
      "api_close": 2415.0,
      "api_ohlc": {
        "date": "2026-07-10",
        "open": 2415.0, "high": 2415.0,
        "low": 2415.0, "close": 2415.0,
        "source": "yfinance"           // ← 標示資料來源
      },
      "matched": true,
      "reason": "match"
    }
  ]
}
```

### TXT (`ohlc_verify_report.txt`)
```
📊 OHLC 交叉比對 (隨機抽樣) - 2026-07-10
✅ 一致: 74/80
❌ 不一致: 3 支
  xxx: DB=xx vs API=yy (source: twstock)
⚠️ API 失敗: 3 支
```

## 執行方式

```bash
# 抽樣 80 檔（每日 cron）
cd /opt/data/taiwan-stock-cashflow-api && /opt/data/.venv/bin/python3 -u screening/verify_ohlc.py

# 全量檢查（Sat cron，約 40-50 分鐘）
cd /opt/data/taiwan-stock-cashflow-api && /opt/data/.venv/bin/python3 -u screening/verify_ohlc.py --full

# 直接執行真實腳本也可
/opt/data/projects/taiwan-stock-cashflow-api/.venv/bin/python3 -u \
  /opt/data/projects/taiwan-stock-cashflow-api/screening/verify_daily_prices.py

# 快速診斷（50 支抽樣，1-2 分鐘，避免 --full 超時）
/opt/data/.venv/bin/python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/quick-ohlc-diagnostic.py
```

## 執行效能實測

| 模式 | 取樣數 | sleep | 預估 | 實際實測 | 瓶頸 |
|------|--------|-------|------|---------|------|
| SAMPLE | 80 | 1.2s/檔 | ~3 min | ~3 min (2026-07-16) | sleep + API 延遲 |
| FULL | 1,925 | 1.2s/檔 | 38-77 min | **~76 min** (2026-07-28)；**~38 min** (2026-07-25)；歷史高點 101 min (2026-07-17) | sleep + API 延遲 |

**執行時間大幅改善（2026-07-25 實測）：** 歷史 Full 執行 101-117 分鐘，2026-07-25 僅 38 分鐘。
推測原因：twstock API 回應速度改善、或多數股票 twstock 直接命中（不需降級到較慢的 yfinance 備援）。
**實際執行時間已接近理論下限（1925 × 1.2s = 38.5 min），代表 twstock 層幾乎零延遲。**

**SAMPLE 模式實測（2026-07-16）：** 80 支的 `--full` 命令在 120s timeout 被迫中斷（未輸出結果），但 SAMPLE 不加 `--full` 的 80 支行指令在 300s 完成。實際耗時約 160s（從 output timestamp 推算：Start at 16:41:18 → Progress 80/80 + summary）。建議 cron 或前景呼叫時 timeout 設 300s 為安全值。

**建議：** 長期趨勢監控用 SAMPLE 模式（80 檔/~3 min）已足夠。FULL 僅在重大事故後才需執行，且建議排程在週六凌晨不限時背景執行。

## 比對結果典型型態

### 2026-07-14 全量檢查（`--full`，目標日期 2026-07-14）

```
Sampled:    1925
Matched:    1312 (68.2%)  ✅
Mismatched: 608  (31.6%)  ❌  →  全部為 missing_data (DB 無資料)
Errors:      5   (0.3%)   ⚠️  →  已下市股
Deviation>1%: 0            (無實際價格偏差)
```

### 2026-07-16 抽樣檢查（目標日期 2026-07-15）

```
Sampled:    80
Matched:    77   (96.25%) ✅
Mismatched: 3    (3.75%)  ❌  →  全部為 missing_data (DB close=null)
Errors:     0    (0%)     ⚠️
Deviation>1%: 0           (無實際價格偏差)
```

**覆蓋率對比：** 7/14 全量檢查時 68.2% coverage → 7/15 抽樣推估 ~96% coverage，顯示增量更新管線在 7/14 → 7/15 之間有效補回大量缺漏資料。

### 2026-07-21 抽樣檢查（目標日期 2026-07-20，修復 get_yesterday 後首次執行）

```
Sampled:    80
Matched:    28   (35%)   ✅  — DB 有資料者全數吻合
Mismatched: 52   (65%)   ❌  → 全部為 db_only_missing (DB 缺 07-20 的收盤價)
Errors:     0    (0%)    ⚠️
Deviation>1%: 0          (無實際價格偏差)
```

**關鍵發現：**
- **零筆真正異常。** 所有 52 筆標記為 mismatched 的原因皆是 `db_close = null`（`daily_prices` 還未寫入該日資料），但 twstock API 查得到報價。這不是資料錯誤，而是管線延遲。
- **覆蓋率驟降解讀：** 從 7/16 的 98.65% 降至 35% 是因為當天早上 `daily_prices` 增量更新僅完成 ~41%（795/1925 檔），與價格準確度無關。
- `get_yesterday()` 在本次執行前已修復，目標日期正確為 2026-07-20（週一）。

**每日價格入庫狀況（截至 2026-07-21 16:40）：**
| 日期 | 筆數 | 有收盤價 | 完成度 |
|------|------|----------|--------|
| 07-17 (五) | 1,918 | 1,903 | 100% ✅ |
| 07-20 (一) | 795 | 782 | ~41% ⚠️ |
| 07-21 (二) | 795 | 781 | ~41% ⚠️ |

### 2026-07-16（週四）收盤價 — 全量檢查（2026-07-17 週五執行）

```
Sampled:    1925
Matched:    1899  (98.65%) ✅
Mismatched: 21    (1.09%)  ❌  → 全部為 both_missing（兩端皆 null，非價格偏差）
Errors:      5    (0.26%)  ⚠️  → 已下市股（1591, 3426, 4804, 4987, 6806）
Deviation>1%: 0             (無實際價格偏差)
執行耗時：~1h45m (101 min)
```

**覆蓋率里程碑：** 從 7/14 的 68.2% → 7/16 的 98.65%，確認增量更新管線已有效填補幾乎所有資料缺口。僅剩 21 檔 both_missing（兩端同步無資料 — 暫停交易或已下市），**資料管線健康，價格品質優良。**

### 2026-07-28（週二）收盤價 — 全量檢查（2026-07-29 執行）

```
Sampled:    1925
Matched:    1890  (98.2%)  ✅
Mismatched: 30    (1.6%)   ❌  → 全部為 missing_data
Errors:      5    (0.3%)   ⚠️  → 已下市股（3426, 4130, 4804, 4987, 6806）
Deviation>1%: 0             (無實際價格偏差)
執行耗時：~76 min
```

**跨次 FULL 比較（4 次）:**

| 執行日期 | 目標日期 | Matched | Mismatched | Errors | Dev>1% | 耗時 |
|----------|----------|---------|------------|--------|--------|------|
| 07-17 | 07-16 | 1,899 (98.65%) | 21 | 5 | **0** | 101 min |
| 07-24 | 07-23 | 1,891 (98.2%) | 29 | 5 | **0** | ~38 min |
| 07-25 | 07-24 | 1,891 (98.2%) | 29 | 5 | **0** | ~38 min |
| **07-29** | **07-28** | **1,890 (98.2%)** | **30** | **5** | **0** | ~76 min |

**關鍵穩定模式：** 連續 4 次 FULL 比對皆為 0 實際偏差。Mismatch 數量在 21-30 間微幅波動，全數來自 `both_missing`（DB+API 皆 null）或已知已下市股，非真實異常。5236（凌陽）持續出現 db_only_missing，可能是唯一值得關注的個案。

### 關鍵發現

1. **價格準確度 100%** — DB 中有資料的 1,312 檔，收盤價與 API 完全吻合（0 偏差 >1%）。`daily_prices` 表的價格本身是可靠的。

2. **~30% 股票 DB 缺昨日資料（2026-07-14 全量）** — `screen_cache` 涵蓋 1,925 檔，但 `daily_prices` 表缺了 590 檔的 7/14 收盤價。這**不是**比對異常，而是**資料覆蓋缺口**。但需注意：`missing_data` 有兩種子型態：
   - **(a) 無 row**：該日期在 `daily_prices` 中完全不存在該股 → 增量更新管線遺漏
   - **(b) 有 row 但 close IS NULL**：該股有資料列（date, stock_code 存在）但 close 為 null → 暫停交易、極低流動性或管線寫入 null
   - **案例（2026-07-16 抽樣）：** 3064（泰偉）在 daily_prices 中有 839 筆歷史紀錄，但 7/13~7/16 的 close 皆為 null；3067（全域）7/15 為 null 但 7/14 有價格 18.0；8923（時報）7/15 為 null 但 7/14 有價格 18.75。`verify_daily_prices.py` 的 `SELECT close FROM daily_prices WHERE stock_code=? AND date=?` 對兩型態都回傳 `db_close = None`，無法區分。
   - **鑑別法：** `SELECT date, close FROM daily_prices WHERE stock_code=? AND date=?` — 確認 row 存在性後再檢查 close 值。
   - **2026-07-16 趨勢改善：** 相較 7/14 全量 68.2% 匹配率，7/15 抽樣達到 96.25%，顯示增量更新管線有效補回了大量缺漏。

3. **資料缺口診斷法：**
   ```sql
   -- 檢查 daily_prices 最新的完整日期
   SELECT date, COUNT(*) AS stocks
   FROM daily_prices
   WHERE date >= date('now', '-10 days')
   GROUP BY date
   ORDER BY date DESC;
   
   -- 找出 screen_cache 中有但 daily_prices 缺某一日的股票
   SELECT sc.stock_code, sc.price AS sc_price, dp.close AS dp_close
   FROM screen_cache sc
   LEFT JOIN daily_prices dp ON sc.stock_code = dp.stock_code AND dp.date = 'YYYY-MM-DD'
   WHERE dp.close IS NULL AND sc.price IS NOT NULL AND sc.price > 0
   ORDER BY sc.stock_code;
   ```

4. **已下市股清理：** FULL 比對中反覆出現 `api_fetch_failed`（1591, 3426, 4804, 4987, 6806 等），應從 `screen_cache` 刪除以減少雜訊。

5. **🐛 `compare_prices()` 分類缺口（2026-07-17 FULL 全量發現）** — `compare_prices()` 將 `db_close is None or api_close is None` 全歸為同一 `"missing_data"`，但實際上包含三種根本不同的子情境：

   | 子情境 | db_close | api_close | 意義 | 本次 FULL 發生次數 |
   |--------|----------|-----------|------|-------------------|
   | **both_missing** | None | None | 暫停交易 / 低流動性，**非異常** | 19 |
   | **db_only_missing** | None | ✓ 有值 | 資料缺口，需補跑更新 | 2（1589, 5236） |
   | **api_only_missing** | ✓ 有值 | None | API 延遲或已下市 | 0 |

   這導致 mismatched 計數（21）幾乎全是無害的 `both_missing`，稀釋了真正須關注的 `db_only_missing` 異常信號。

   **改善建議（`verify_daily_prices.py` L136-152）：** 將 `compare_prices()` 的單一 `"missing_data"` 拆分為三個獨立 reason：

   ```python
   def compare_prices(db_close, api_close, tolerance=0.01):
       if db_close is None and api_close is None:
           return False, "both_missing"      # 非異常，可濾除
       if db_close is None:
           return False, "db_only_missing"   # 資料缺口，需關注
       if api_close is None:
           return False, "api_only_missing"  # API 問題
       if api_close == 0:
           return False, "api_zero"
       deviation = abs(db_close - api_close) / api_close
       if deviation <= tolerance:
           return True, "match"
       else:
           return False, f"deviation_{deviation:.2%}"
   ```

   修復後，cron 回報可專注於 `db_only_missing` 和 `deviation_*` 計數，`both_missing` 直接濾除即得到真正需處理的異常筆數。

## ⚠️ 已知限制

### 1. 目標日期資料可能尚未發布
TWSE 歷史股價 API 通常在次一交易日才更新。例如：
- 週五的交易資料 → 最快週六才上架
- API `fetch_from()` 回傳的月資料只到週四，找不到週五的 record

目前腳本將回傳 `None` 一律歸類為 `api_fetch_failed`，
無法區分「API 連線異常」與「目標日期資料尚未發布」。

### 2. DB 資料缺口
腳本比對目標是「昨天」，但如果 `twse_daily_update` cron 未正常執行，DB 的 `daily_prices` 表
可能缺少前幾天資料，導致 `db_close = null`，比對結果為 `missing_data`。

執行前建議先確認：
```sql
SELECT MAX(date) FROM daily_prices;
```

### 3. twstock 1.5.1 response=json bug（已修復）
詳見 SKILL.md「疑難排解 → twstock 回傳查詢日期小於99年1月4日」。

### 4. cron path desync（已修復 — 2026-07-11）
原 cron prompt 中的路徑 `/opt/data/taiwan-stock-cashflow-api/screening/verify_ohlc.py` 有兩個問題：
1. 檔名不存在（應為 `verify_daily_prices.py`）
2. 該目錄下 `screening/` 不含腳本本體（僅有 `output/` 子目錄）

修復：建立 wrapper + 雙輸出 + yfinance 備援（詳見上方記錄）。

### 5. 🐛 `get_yesterday()` 週一日期 bug（2026-07-14 發現，**2026-07-21 已修復**） ✅

**症狀：** 當今天為週二、昨天為週一時，腳本錯誤地再減 2 天變成「週六」，導致查無交易日資料、或查到的月份資料不含該日。

**錯誤的演算法（L123-133）：**
```python
yesterday = datetime.now().date() - timedelta(days=1)
if yesterday.weekday() == 0:    # Monday → 錯！星期一本來就是交易日
    yesterday -= timedelta(days=2)   # → Saturday
elif yesterday.weekday() == 5:  # Saturday
    yesterday -= timedelta(days=1)
elif yesterday.weekday() == 6:  # Sunday
    yesterday -= timedelta(days=2)
```

**根因：** 函式判斷的是 `yesterday.weekday()` 而非 `today.weekday()`。當今天為週二時，昨天是週一(0)，但程式誤認 0=週末並減了 2 天。正確做法是檢查「今天」的星期幾，再決定「昨天」是否需要再往前推。

**影響實例：** 2026-07-21（週二）執行時，原始程式選了 2026-07-18（週六）而非 2026-07-20（週一）。

**已套用的修復（2026-07-21）：**
```python
def get_yesterday():
    """取得最近一個交易日（跳過週末）"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    # 檢查「今天」的星期幾來決定回推天數
    if today.weekday() == 0:   # 週一 → 上週五（往前 3 天）
        yesterday = today - timedelta(days=3)
    elif today.weekday() == 6: # 週日 → 上週五（往前 2 天）
        yesterday = today - timedelta(days=2)
    # 週二~週六: yesterday = today - 1 即為正確交易日
    return yesterday
```

**驗證（完整 10 情境測試，含跨月邊界）：**
| 今天 | 星期 | 回推 | 結果 | 正確 |
|------|------|------|------|------|
| 2026-07-20 | Mon | 3 | 07-17 Fri | ✅ |
| 2026-07-21 | Tue | 1 | 07-20 Mon | ✅ |
| 2026-07-22 | Wed | 1 | 07-21 Tue | ✅ |
| 2026-07-23 | Thu | 1 | 07-22 Wed | ✅ |
| 2026-07-24 | Fri | 1 | 07-23 Thu | ✅ |
| 2026-07-25 | Sat | 1 | 07-24 Fri | ✅ |
| 2026-07-26 | Sun | 2 | 07-24 Fri | ✅ |
| 2026-08-03 | Mon | 3 | 07-31 Fri（跨月） | ✅ |
| 2026-08-02 | Sun | 2 | 07-31 Fri（跨月） | ✅ |
| 2026-08-01 | Sat | 1 | 07-31 Fri（跨月） | ✅ |

**檔案：** `screening/verify_daily_prices.py`，單一函式修改。

### 6. `--full` 模式超時限制（2026-07-14）

**現象：** `--full` 全量檢查（1,925 支股票）每支 sleep 1.2 秒 + API 回應時間 ~3-5 秒，總耗時約 **38-50 分鐘**。在 cron 或前景執行常因 timeout 被中斷。

**影響：**
- cron runtime 若設 600s (10 min) → 一定超時
- 前景 terminal timeout=300s → 一定超時
- Hermes 背景程序雖可用 notify_on_complete，但中斷後無 checkpoint 續傳機制

**解決方案：**
- 快速診斷（50 支，~2 分鐘）→ `scripts/quick-ohlc-diagnostic.py`
- 全量檢查建議分 4 批執行（~500 支/批 × ~8 min），或延長 sleep 改為 burst + 長休息
- 若只檢查最新日收盤，快速模式（50 支隨機抽樣）已足夠偵測異常

### 7. ⚠️ `--all-dates` 參數不存在（2026-07-25 陷阱）

**現象：** 嘗試使用 `--full --all-dates` 會報 `error: unrecognized arguments: --all-dates`。

**事實：** 腳本只支援 `--full`（全量 1925 支）或不加參數（隨機抽樣 80 支）。
沒有「指定日期範圍」或「所有日期」的參數 — 目標日期由 `get_yesterday()` 自動決定。

**如需比對特定日期：** 必須修改 `get_yesterday()` 函式的回傳值，或直接改寫 `target_date` 變數後執行。
