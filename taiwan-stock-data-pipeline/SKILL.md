---
name: taiwan-stock-data-pipeline
description: >-
  台股每日收盤價資料管線 — 實際部署於 Hermes RPi4 上的
  SQLite 增量更新方案。包含 cron 排程、限流策略、
  DB 庫存管理與除錯 SOP。
version: 2.4
author: Hermes Agent
metadata:
  hermes:
    tags: [taiwan-stock, twse, tpex, daily-prices, sqlite]
    related_skills: [ai-stock-screener, taiwan-stock-sqlite-pipeline, tw-stock-radar]
---

# 台股每日資料管線 (Taiwan Stock Data Pipeline)

## Overview

| 項目 | 內容 |
|------|------|
| **排程** | 每天 16:00 (TWSE 收盤後) |
| **腳本** | `update_daily.py`（增量 + today-data filter + checkpoint 續傳） |
|| **觸發** | `run_daily_incremental_update.sh`（price → 技術指標 串聯執行） |
|| **設計模式** | `references/incremental-update-design.md`（兩層效率機制 + BATCH_SIZE 調校 + 失敗復原） |
|| **模式** | cron no_agent script-only（無 LLM，穩定可靠） |
| **語系慣例** | `references/locale-convention.md`（所有腳本輸出/註解使用正體中文） |

| **OHLC 比對** | `screening/verify_daily_prices.py`（twstock + yfinance 雙源備援，新舊路徑雙輸出）|
| **OHLC cron** | `ohlc-verification`（M-F 16:00） + `ohlc-verification-full`（Sat 02:00） |
| **OHLC 報告路徑** | `screening/output/ohlc_verification_latest.json`（每次全量比對結果） |
| **OHLC 協定** | `references/ohlc-verify-protocol.md`（架構、bug 記錄、已知限制） |
| **全量比對記錄** | `references/ohlc-full-run-2026-07-24.md`（2026-07-24 實測：1925 檔 matched=774, mismatched=1146, errors=5） |
| **全量比對記錄** | `references/ohlc-full-run-2026-07-28.md`（2026-07-28 實測：1925 檔 matched=1890, mismatched=30, errors=5, deviation=0） |
| **Missing Data 調查** | `references/ohlc-missing-data-investigation-2026-07-24.md`（1146 missing_data 根因分析：timing race condition + screen_cache.date mismatch） |
| **查詢優化** | `references/daily-prices-query-optimization.md`（固定日期 join → 229× 加速）|
| **API 測試** | `scripts/test_twse_openapi.py`、`scripts/test_tdcc_openapi.py`、`scripts/test_tpex_openapi.py`（端點可用性驗證）|
| **API 比較** | `references/api-sources-comparison.md`（六大來源完整比較）|
| **TDCC 端點** | `references/tdcc-endpoints-full.md`（135 個端點完整列表）|
| **TPEX Cloudflare** | `references/tpex-openapi-cloudflare-blocking.md`（Swagger 可下載但端點 302 封鎖）|

## DB 架構

```bash
/opt/data/taiwan_stocks.db   # 統一的 root 資料庫
```

```sql
-- 主要資料表
CREATE TABLE daily_prices (
    date TEXT NOT NULL,          -- YYYY-MM-DD
    stock_code TEXT NOT NULL,    -- e.g. 2330
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    turnover REAL,
    transaction_count INTEGER,
    amplitude REAL,
    PRIMARY KEY (date, stock_code)
);

-- 輔助表
CREATE TABLE stock_meta (
    stock_code TEXT PRIMARY KEY,
    name TEXT,       -- 公司名稱
    industry TEXT,   -- 產業別
    -- 更多欄位依腳本定義
);

CREATE TABLE IF NOT EXISTS update_checkpoint (
    batch_name TEXT PRIMARY KEY,        -- 唯一批次識別碼
    last_processed_stock TEXT NOT NULL,  -- 最後處理的股票代碼
    total_stocks INTEGER,               -- 本批總股票數
    completed INTEGER,                  -- 是否完成 (0/1)
    updated_at TEXT                     -- ISO 時間戳
);
```

**外部專案存取模式** — 以下專案讀取同一個 root DB：

| 專案 | 存取方式 |
|------|---------|
| Cashflow API | symlink: `taiwan-stock-cashflow-api/taiwan_stocks.db` → `/opt/data/taiwan_stocks.db` |
| screener 模組 | `DB_PATH` 優先順序（環境變數 → root DB → 本地備援）|
| **tw-stock-radar** | **`our_db.py` 橋接器** — SQLite `mode=ro` 唯讀連線，不搶鎖；匯出 CSV 快取給第三方掃描引擎（見 `references/external-scanner-integration.md`） |

### 市值資料 (market_cap)

`stock_meta` 於 2026-07-08 新增 `market_cap REAL` 欄位（單位：億）。

**來源：** TWSE Open API `t187ap03_L`（上市公司總市值資料，1089 筆）
**公式：** `市值 = 收盤價 × 已發行普通股數 / 1億`
**頻率：** 已發行股數變動低，每月或每季重抓即可。
**參考：** `references/market-cap-api.md`

```python
resp = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
for d in resp.json():
    shares = int(d['已發行普通股數或TDR原股發行股數'])
    # JOIN stock_meta.stock_code 後 UPDATE market_cap
```

### 熱力圖 (Heatmap — 策略選股視覺化)

基於 `daily_prices` + `stock_meta.market_cap` 的漲跌分布圖：

| 呈現方式 | 實作 | 路徑 |
|:---------|:-----|:------|
| Web 儀表板 | Flask `GET /api/heatmap` → d3-hierarchy squarified treemap（Canvas, 50 檔 top 市值） | `taiwan-stock-cashflow-api/static/index.html` |
| Telegram 截圖 | Squarified treemap via Pillow, 50 檔市值前大 | `/opt/data/render_treemap.py` |
| 排序依據 | `ORDER BY market_cap DESC LIMIT 100` | SQL |
| 顏色 | HSL 漸層（綠漲紅跌，深淺依幅度，cap @ 10%) | `app.py` + `render_treemap.py` |
| 區塊大小 | Squarified treemap — sqrt 市值比例（台積電最大塊、填滿畫面無縫隙） | `references/squarified-treemap.md` |

**SQL 查詢（0.037s）：** 固定日期 JOIN（比 window function 快 200×）

```sql
SELECT curr.stock_code, sm.stock_name, sm.industry, sm.market_cap,
       curr.close AS price,
       ROUND((curr.close - prev.close) / prev.close * 100, 2) AS change_pct
FROM daily_prices curr
JOIN daily_prices prev ON curr.stock_code = prev.stock_code AND prev.date = ?
JOIN stock_meta sm ON curr.stock_code = sm.stock_code
WHERE curr.date = ? AND curr.close IS NOT NULL AND prev.close IS NOT NULL
  AND sm.market_cap IS NOT NULL
ORDER BY sm.market_cap DESC LIMIT 100
```

## 技術指標管線 (Tech Indicators Pipeline)

> 在 `daily_prices` 原始價格資料之上，另有一套完整、已驗證的技術指標計算與選股篩選系統。

### 腳本一覽

| 腳本 | 位置 | 功能 |
|------|------|------|
| `update_all_tech_indicators.py` | `taiwan-stock-cashflow-api/screening/` | 全量計算 **1925 檔** 股票的技術指標（實測 12.5 秒 / 1925 檔） |
| `update_tech_indicators.py` | 同上 | 僅更新 `screen_cache` 中已有基本面的股票 |
| `auto_screen_and_notify.py` | 同上 | 執行 14 種選股策略 + 可選 Telegram 推播 |

### ⚠️ DB 連線最佳實踐（2026-07-14 事件；2026-07-20 確認 Fix 仍未套用）

> 所有寫入 `taiwan_stocks.db` 的 Python 腳本，**必須**設 `timeout=60` + `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=30000`。漏任何一個都會在其他寫入者活躍時噴 `database is locked`。

```python
# 標準寫法（比對 update_daily.py 與 verify_daily_prices.py）
conn = sqlite3.connect(DB_PATH, timeout=60)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

**事件：** `update_all_tech_indicators.py` 和 `update_tech_indicators.py` 用了裸 `sqlite3.connect(DB_PATH)`（timeout=0, busy_timeout=0），碰到其他寫入者（如 `update_daily.py` 正在寫入 WAL）時秒噴 `database is locked` 1925 次，且無重試機制。對照 `update_daily.py` 和 `verify_daily_prices.py` 有設這三行，從未報過 lock。

#### 🔧 Fix 套用狀態（2026-07-20 實測確認）

| 腳本 | timeout/busy_timeout | 現狀 |
|------|----------------------|------|
| `update_all_tech_indicators.py` | ❌ **尚未修復** | 遇到並發寫入者仍會 1925 全掛 |
| `update_tech_indicators.py` | ❌ **尚未修復** | 同上 |
| `update_daily.py` | ✅ 已套用 | 安全 |
| `verify_daily_prices.py` | ✅ 已套用 | 安全 |

**套用修復指令（sed 一行搞定）：**
```bash
sed -i '/conn = sqlite3\.connect/a\conn.execute("PRAGMA busy_timeout=30000")\nconn.execute("PRAGMA journal_mode=WAL")' \
  /opt/data/projects/taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py
```
若 `update_tech_indicators.py` 也漏了，同上模式處理。

**診斷還有沒有遺漏的腳本：**
```bash
grep -rn "sqlite3\.connect(" /opt/data/scripts/ /opt/data/projects/taiwan-stock-cashflow-api/ --include="*.py" \
  | grep -v "timeout="
```

### 已計算指標（`screen_cache` 表）

| 類別 | 指標 | 欄位 |
|:-----|:-----|:------|
| **RSI** | RSI-6 / RSI-12 / RSI-14 | `rsi_6`, `rsi_12`, `rsi_14` |
| **移動平均線** | MA5 / MA10 / MA20 / MA60 | `ma5`, `ma10`, `ma20`, `ma60` |
| **MACD** | DIF 值 | `macd` |
| **布林帶** | 上/中/下軌 + 寬度% | `bollinger_upper/middle/lower/width` |
| **量能** | 量比 / 量變化率 | `volume_ratio`, `volume_change` |
| **價格** | 最新價 / 成交量 | `price`, `volume` |

狀態：**1925/1925 檔已全量計算完成（100%）。**

### 選股策略（14 種，已實作）

| 策略 | 核心條件 |
|:-----|:---------|
| RSI 超賣 | `rsi_14 ≤ 30` + 基本面分數 |
| MACD 黃金交叉 | `macd > 0` + `rsi_14 ≤ 65` |
| 布林帶窄幅 | BB 寬度 < 10% + 量增 |
| 均線乖離 | ma5/ma60 比值 1.1 ~ 1.3 |
| 趨勢跟蹤 | `macd > 0` + 量增 |
| 量能爆發 | 量變化 ≥ 30% |
| 其他 8 種 | 動能、均值回歸、保守成長等 |

### ⚠️ `latest_results.json` 硬編碼路徑不一致（2026-07-20 發現）

`auto_screen_and_notify.py` 第 335~340 行硬編碼結果輸出檔案路徑：

```python
with open(
    "/opt/data/taiwan-stock-cashflow-api/screening/latest_results.json",
    "w", encoding="utf-8",
) as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

但完整專案目錄是 **`/opt/data/projects/taiwan-stock-cashflow-api/screening/`**（含 `projects/`）。
沒有 `projects/` 的路徑若目錄不存在則不會報錯（因為另一個同名目錄存在於 `/opt/data/taiwan-stock-cashflow-api/`，僅含過時的 screening 子目錄），
但會造成**路徑不一致**：新結果寫到舊位置，專案路徑下的結果不更新。

**正確修復（改用動態解析）：**
```python
_script_dir = Path(__file__).resolve().parent  # screening/
_output_path = _script_dir / "latest_results.json"
with open(_output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

**手動同步（修復前暫時解法）：**
```bash
cp /opt/data/taiwan-stock-cashflow-api/screening/latest_results.json \
   /opt/data/projects/taiwan-stock-cashflow-api/screening/latest_results.json
```

**驗證兩路徑一致：**
```bash
diff <(md5sum /opt/data/taiwan-stock-cashflow-api/screening/latest_results.json) \
     <(md5sum /opt/data/projects/taiwan-stock-cashflow-api/screening/latest_results.json)
```

**已知影響（2026-07-20 實測）：** cron 執行後如果只看專案路徑的檔案，會誤以為結果未更新。腳本回傳的 `✅ Telegram 推送成功` 仍正常，僅檔案位置錯置。

### ⚠️ Telegram 報告「1924 股票」硬編碼與實際 1925 檔落差（2026-07-20 發現）

`auto_screen_and_notify.py` 的 `format_telegram_message()` 在報告末尾固定輸出：

```python
msg += f"<i>共15策略, 1924股票 | 數據來源: local SQLite DB</i>\\n"
```

但 `stock_meta` 表實際有 **1925 檔**（含已下市、暫停交易股）。這 1 檔的落差由硬編碼造成。

**影響：** 低，純展示問題。若修正可改為動態計數：
```python
conn = sqlite3.connect(DB_PATH)
total_stocks = conn.execute("SELECT COUNT(*) FROM stock_meta").fetchone()[0]
conn.close()
msg += f"<i>共{len(results)}策略, {total_stocks}股票 | 數據來源: local SQLite DB</i>\\n"
```

### ⚠️ `auto_screen_and_notify.py` 策略 Lambda 的 `None` 守衛（2026-07-16 bug）

`auto_screen_and_notify.py` 中的策略篩選邏輯是 lambda 表達式，直接比較 `screen_cache` 欄位值與閾值。
**多個 `screen_cache` 數值欄位可能為 `NULL`**（資料不足、暫停交易等），若 lambda 缺少 `is not None` 檢查，
比較運算子會拋 `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`。

**歷史案例：** `SECTOR_ROTATION` 和 `BREAKOUT_FOLLOW` 策略的 `vol_change >= X` 因 `vol_change=None` 炸掉，
其餘策略（`TREND_FOLLOWER`, `VALUE_BREAKOUT`）已內建 `s["vol_change"] is not None` 守衛所以正常。

**新增策略或修改現有策略時必須注意：**

```python
# ✅ 有守衛（安全）
"TREND_FOLLOWER": lambda s, c: (
    s["vol_change"] is not None
    and s["vol_change"] >= c.get("min_volume_change", 20)
) and s["macd"] > 0 ...,

# ❌ 無守衛（會炸，修復於 2026-07-16）
"SECTOR_ROTATION": lambda s, c: s["total_score"] >= c.get("min_total", 18)
    and s["vol_change"] >= c.get("min_volume_change", 10)  # vol_change=None → TypeError
```

**影響欄位（`screen_cache` 中可能為 NULL）：** `vol_change`, `volume_ratio`, `rsi_14`, `macd`, `bb_width` 等浮點數欄位。
所有數值比較前都應加 `is not None` 守衛，除非該策略邏輯上要求該欄位必填（此時應先 filter 再比較）。

**快速檢查命令：**
```bash
grep -n "and s\[" /opt/data/projects/taiwan-stock-cashflow-api/screening/auto_screen_and_notify.py | grep -v "is not None" | grep -E ">=|<=|>|<|=="
```

### 報告必須註記「產生模型」（用戶明確要求，2026-07-11）

**規則：** 每一則推播到 Telegram 的台股策略報告，**最後一行必須註記是由哪一個模型產生的**。
目的：當 cron 因模型失效切換到備援模型（big-pickle / agnes）時，能一眼看出本次報告跑在哪個模型上。

**實作（已落地於 `taiwan-stock-cashflow-api/screening/auto_screen_and_notify.py`）：**
- `format_telegram_message()` 末尾追加：`<i>🤖 模型: <tag></i>`
- 模型名來源優先序：
  1. `HERMES_MODEL` 環境變數（cron agent 執行腳本前 `export` 的當下模型名）
  2. `.env` 的 `CRON_MODEL_TAG`（安全網，預設 `hy3-free`）
  3. 以上皆無 → `unknown`
- `_get_model_tag()` 負責解析；手動跑忘記 export 時退回 `.env` 預設值。

**cron prompt 必須配合（`taiwan-tech-strategy-daily` 已改）：**
```
1. 先 export HERMES_MODEL="<你本次執行所用的模型，例如 hy3-free / opencode/big-pickle / custom:agnes>"
   （若因模型失效切換到備援模型，請用備援模型的名稱）
2. 運行 update_all_tech_indicators.py
3. 運行 auto_screen_and_notify.py   ← 腳本會自動在報告末尾註記 HERMES_MODEL
4. 回報本次實際使用的模型名稱
```

**驗證方式：** 跑一次並在手機確認報告最後一行是否為預期 tag（例如測試時用 `hy3-free (test-run)` 這種獨一無二標記即可 100% 確認 footer 真的被推出去）。

> 若未來新增其他會推播報告的 cron（如 ohlc-verification、finmind-batch），請照搬同一套 `HERMES_MODEL` → footer 邏輯，確保所有報告都帶模型註記。

### OHLC 交叉比對（收盤價驗證）

> 腳本：`screening/verify_daily_prices.py` | cron: `ohlc-verification` (M-F 16:00) + `ohlc-verification-full` (Sat 02:00)
> 完整協定與已知限制：`references/ohlc-verify-protocol.md`

#### ⚠️ 操作原則（2026-07-15 全量 + 2026-07-16 抽樣實測教訓）

- **日常監控用 SAMPLE（80 檔/~3 min）** — 足夠偵測大規模異常；API 延遲可推至 ~3 分鐘，timeout 建議設 300s。FULL 模式 1,925 檔因 1.2s/檔 sleep 需 ~38 分鐘（2026-07-25 實測，已接近理論下限）
- **比對結果判讀：** `mismatched` 絕大部分是 `missing_data`（DB 中該日價格為 null），非實際價格偏差。`missing_data` 有兩種子型態需區分：
  - **(a) 無 row**：該日期無 `daily_prices` 紀錄 → 增量更新管線遺漏
  - **(b) 有 row 但 close IS NULL**：該股有資料列但收盤價為 null → 暫停交易、極低流動性或管線寫入 null
  - 差異可藉 `SELECT stock_code, date, close FROM daily_prices WHERE stock_code=? AND date=?` 分辨
- **sporadic `api_fetch_failed` 若 < 10 筆：** 通常是已下市股（1591, 3426, 4130, 4804, 4987, 6806 等）未自 screen_cache 清除，非真實異常。yfinance API 回傳 HTTP 404 + "possibly delisted" 警告但程式會容錯繼續跑。
- **2026-07-25 全量實測結果：** 1925 檔中 matched=1891, mismatched=27, errors=7。mismatched 全部為 missing_data（DB close=null），零筆實際價格偏差。7 筆 errors 為已下市股。覆蓋率從 40.2% 提升至 98.2%。
- **2026-07-28 全量實測結果（07-29 執行）：** 1925 檔中 matched=1890, mismatched=30, errors=5，Deviation>1%=0。連續 4 次 FULL 比對皆為 0 實際偏差。27 支 both_missing + 3 支 db_only_missing（5236 凌陽資料缺口值得關注）+ 5 支 api_fetch_failed（已下市股）。執行耗時約 76 分鐘。
- **異常詳細分類（2026-07-25）：**
  - **API 取得失敗 (7 支)：** `1459, 1589, 3426, 4130, 4804, 4987, 6806` — twstock + yfinance 均無法取得資料，多為已下市或停止交易股
  - **資料缺失 (20 支)：** `2035, 2937, 3064, 3067, 3085, 3158, 3226, 3531, 3664, 4183, 4305, 4406, 5520, 6171, 6210, 6228, 6236, 6242, 6856, 6865, 7743, 7782, 8342, 8477, 8905, 8923` — DB close=null，twstock 也回傳 null（可能為新上市尚未有完整交易資料）
  - **唯一值得關注的個案：** `5236（凌陽）` — yfinance 回傳 close=150.5，但 DB 為 null → 資料管線可能漏抓，建議下次更新排程時補入
- **結論：** 實際 OHLC 價格一致率 100%（所有有數值的股票均比對通過）。27 支異常全為「DB 無資料」而非「資料錯誤」，屬於資料完整性問題（pipeline 覆蓋率），非準確性問題。
- **資料缺口已從 ~30% 降至 ~1.6%（590→30 檔）：** 2026-07-14 全量還有 590 檔 `missing_data`（30%），到 2026-07-28 已降為 30 檔（1.6%），其中 27 檔為 `both_missing`（兩端皆 null，暫停交易股）。增量更新管線已有效補回絕大多數資料缺口。
- **比對結果判讀：** `mismatched` 絕大部分是 `missing_data`（DB 中該日價格為 null），非實際價格偏差。`missing_data` 有兩種子型態需區分：

#### ⚠️ 2026-07-10 事件：twstock API 全面失靈（0/80）

**症狀：** 07-10 的 OHLC 抽樣報告顯示 0/80 一致，原以為 DB 資料全錯，實際上是 **twstock 上游 API 全面失效**（80/80 回傳 `api_fetch_failed`），腳本無備援。

**發現的 3 個 bug：**
| # | 問題 | 影響 |
|---|------|------|
| 1 | cron 引用 `verify_ohlc.py`，但該檔不存在（真實檔名 `verify_daily_prices.py`） | cron 看似在跑但實際腳本未被執行 |
| 2 | `fetch_ohlc_via_twstock()` 失敗時無備援 | twstock 倒地的期間驗證完全停擺 |
| 3 | `OUTPUT_DIR` 寫死舊路徑 `/opt/data/taiwan-stock-cashflow-api/` | 新舊路徑雙輸出的相容性問題 |

**修復（2026-07-11）：**
- 建立 `screening/verify_ohlc.py` wrapper（`exec()` 指向真實腳本，cron 不需改路徑）
- 加入 yfinance 備援（twstock → yfinance 自動降級，結果標記 `source` 欄位）
- 新舊兩路徑都寫入輸出檔

#### 資料來源備援架構

```
fetch_ohlc_via_twstock(code, date)
  │
  ├─ twstock.Stock(code).fetch_from(year, month)
  │     → 成功？回傳 {date, o, h, l, c, source: "twstock"}
  │
  └─ yfinance.Ticker(code+".TW").history(start, end)  ← 備援
        → 成功？回傳 {date, o, h, l, c, source: "yfinance"}
        → 都失敗？回傳 None
```

### 完整性驗證

```bash
# 快速檢查：NULL 完整性、跨表筆數對應、資料新鮮度
python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/verify_tech_indicators.py

# 深度交叉驗證：從 daily_prices 原始資料重算指標 → 比對 screen_cache
# └─ 預設: 80 檔隨機抽樣（~2 秒）
# └─ --full: 1,925 檔全量比對（~10 秒，修改計算邏輯後必跑）
python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/cross_verify_indicators.py
python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/cross_verify_indicators.py --full
```

### ⚠️ 歷史案例：reverse() 索引混淆（2026-07-08）

`update_all_tech_indicators.py` 從 DB 取得資料為 DESC（最新在前），技術指標需 ASC（最舊在前），
因此會 `prices.reverse()` 和 `volumes.reverse()`。

**bug：** `calculate_volume_ratio()` 和 inline `volume_change` 用 `volumes[0]`（reverse 後變成**最舊**）
而非 `volumes[-1]`（**最新**），導致全部 1,925 檔的成交量指標都是錯誤數值。

**發現：** 例行 NULL 檢查發現 5 檔 volume_ratio 為 NULL，追查確認是索引錯誤。  
**修復：** `volumes[0]` → `volumes[-1]`，`volumes[1:6]` → `volumes[-6:-1]`。  
**驗證：** `cross_verify_indicators.py --full` → 13,475 次比對全部通過。  
**教訓：** reverse 後第一時間更新所有索引註解，並對「最新筆」統一套用 `[-1]` 而非假設 `[0]`。

### 每日整合 🔴 已上線

`scripts/run_daily_incremental_update.sh` 已於 2026-07-15 修改為 today-data filter 增量模式：

```bash
# Step 0: 每日重置 checkpoint
rm -f /opt/data/update_checkpoint.json

# Step 1: 增量更新（today-data filter 跳過已有今日資料的股票）
.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py
#   ├─ Tier 1: today-data filter → 只補缺漏股 (~600-800 檔)
#   ├─ Tier 2: checkpoint → 每 50 檔存檔，timeout 可接續
#   └─ BATCH_SIZE=800 → ~21 分 < 40 分 timeout

# Step 2: 自動更新技術指標
timeout 600 .venv/bin/python3 /opt/data/taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py
```

每天 16:00 cron 觸發後，**股價 → 技術指標** 全自動完成，不需手動介入。

**設計細節 → `references/incremental-update-design.md`**

#### ⚠️ `update_daily.py` 與 `update_all_tech_indicators.py` 競態條件（2026-07-20 發現）

`run_daily_incremental_update.sh` 按順序執行（Step 1 → Step 2），但若兩個 cron 或手動執行在時間上重疊，會發生：

1. `update_daily.py` 以 WAL mode 寫入 `taiwan_stocks.db`，過程中保持 WAL 檔案開啟
2. `update_all_tech_indicators.py` 用裸 `connect(DB_PATH)`（timeout=0, busy_timeout=0）嘗試連線 → **1,925 檔全數 `database is locked`**
3. 即使 `update_daily.py` 已寫入最後一筆 checkpoint，WAL 仍在 flush 前保持鎖定狀態

**實例（2026-07-20 04:14）：** `update_daily.py` 在 `[750/800]` 時（尚有 50 檔排隊中），`update_all_tech_indicators.py` 啟動 → 1925/1925 errors。`update_daily.py` 完成約 20 秒後重試即成功。

**解決方案優先序：**
1. **根本解：** 為 `update_all_tech_indicators.py` 加入 `timeout=60` + `busy_timeout=30000`（見上方「DB 連線最佳實踐」的修復指令），讓它能在鎖定時排隊等待而非秒噴
2. **排程解：** 確保兩個 cron 之間有足夠間隔（建議 Step 1 與 Step 2 間至少 5 分鐘 buffer）
3. **臨時解：** WAL checkpoint 強制釋放鎖（僅在確定無其他寫入者時可用）：
   ```python
   conn = sqlite3.connect('/opt/data/taiwan_stocks.db', timeout=30)
   conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   conn.close()
   ```

## FinMind API 限制與封鎖防護（2026-07-11 調查）

> 完整官方文件引文 + 實測數據 + 推薦防護設計見 `references/finmind-api-limits.md`。
> 這是直接導致我們 token 頻繁被 ban 的根因，所有碰 FinMind 的程式都要遵守。

### 硬限制（Free / level 1）
- **每日 600 次**（`api_request_limit`），每小時 600 次
- 超額 → `402 {"msg":"Requests reach the upper limit"}`
- 查配額：`GET https://api.web.finmindtrade.com/v2/user_info`（Header `Authorization: Bearer <token>`）→ `user_count` / `api_request_limit`

### 封鎖（IP Ban）— 最容易踩的坑
- 短時間大量 **4xx**（含超額 402、無效 token、參數錯誤）→ **IP 自動封 30 分鐘**
- 封鎖回應：`{"msg":"ip banned","status":403}` —— **body 沒有 `retry_after` 欄位**
- 解除後若繼續打 4xx 會**再被封鎖**（死循環）

### 🐛 我們自己程式的 ban 死循環 bug（必修）
- `financial_analyzers.py` / `cashflow_analyzer.py` / `batch_evaluate_financial.py` 都用 `body.get("retry_after", 300)`
  → FinMind 從不回這欄位 → 永遠拿到 300 → `time.sleep(300)` 後回傳 None 繼續跑下一支
  → 每支股票又打一次 403、又睡 300s ×541 支 = 無限浪費 + 持續打 4xx 讓 IP 一直 ban
- **正確做法**：偵測到 `403 ip banned`，**整批立即停**，等一次 30 分鐘，期間不打網路；絕不在每支股票各自 sleep
- 單支股票 burst ~7 次 FinMind（income+balance+cashflow 各 1 + ROE 重抓 income+balance + 股息+股價）；541 支 backlog ≈ 3800 次 >> 600/天

### 防護守則（寫任何 FinMind 呼叫前必讀）
1. **磁碟快取**（sqlite, TTL 7 天）跨執行保留，消除重複抓取；不要用記憶體內 24h 快取
2. **全域每日配額守衛**：開跑前查 `user_info`，逼近 600 就優雅停止，不硬幹 402
3. **斷路器**：`403 ip banned` → 整批停、等 30 分鐘、期間零網路
4. **速率限制**：最小間隔 ~8s/req，避免突發
5. **去重**：ROE 直接吃 analyzer 已抓的 income/balance，勿重抓
6. **backlog 分批**：~110 支/天（含備援 ≈770 次），約 5 天填滿快取後只補增量

## Rate Limits

| 情境 | 限流 | 實測上限 |
|------|------|---------|
| 日常增量更新 | 120 rpm (0.5s/stock) | ✅ 安全 |
| 一次全補 (backfill) | 300 rpm (0.2s/stock) | ✅ 無 429 (2026-07 測試) |
| **⚠️ 必做** | 爬取前先測限流 ramp-up 60→120→180→240→300 rpm | 用戶明確要求 |

## 日常操作

### 查看今日更新狀態

```sql
SELECT date, COUNT(DISTINCT stock_code) AS stocks, COUNT(*) AS rows
FROM daily_prices
WHERE date = (SELECT MAX(date) FROM daily_prices)
GROUP BY date;
```

### 檢核資料完整性

```bash
python3 /opt/data/scripts/verify_daily_prices.py    # 檢查每檔筆數
```

### 手動補跑增量

```bash
cd /opt/data
.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py
# 預設模式：today-data filter 跳過已有今日資料的股票 + checkpoint 續傳

# 強制全量重掃（跳過 today-data filter）：
.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py --force

# 自訂批次大小：
.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py --batch 300
```

### DB 健康檢查

```bash
python3 -c "
import sqlite3, pathlib
db = sqlite3.connect('/opt/data/taiwan_stocks.db')
cur = db.execute('PRAGMA quick_check')
print('quick_check:', cur.fetchone())
cur = db.execute('SELECT COUNT(*), COUNT(DISTINCT stock_code), MIN(date), MAX(date) FROM daily_prices')
rows, stocks, dmin, dmax = cur.fetchone()
print(f'{rows:,} rows | {stocks} stocks | {dmin} ~ {dmax}')
db.close()
"
```

## 疑難排解

### database is locked

#### 即時解（-wal/-shm 髒檔）
```bash
# 背景程序被 kill 留下髒檔，阻擋新連線（僅在確認無其他寫入者時安全）
rm -f /opt/data/taiwan_stocks.db-wal /opt/data/taiwan_stocks.db-shm
```

#### WAL checkpoint 強制釋放（有其他寫入者正在工作時，比刪髒檔安全）
```python
# 若確定 DB 無其他活躍寫入者，此操作可釋放鎖
conn = sqlite3.connect('/opt/data/taiwan_stocks.db', timeout=30)
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
conn.close()
# 注意：若仍有其他 process 在用 DB（如 update_daily.py），此操作也會失敗
```

#### 根本解（漏 PRAGMA busy_timeout）— 2026-07-14 事件
`database is locked` 最常見的原因不是髒檔，而是**腳本連線時沒設 `timeout` + `busy_timeout`**，遇到其他寫入者時秒噴錯誤而非排隊等待。

**實例：** `update_all_tech_indicators.py` 和 `update_tech_indicators.py` 用裸 `sqlite3.connect(DB_PATH)`（timeout=0, busy_timeout=0）。
修正後：
```python
conn = sqlite3.connect(DB_PATH, timeout=60)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
```

即使 DB 已是 WAL mode，第二個寫入者若無 busy_timeout 也秒噴。

#### 診斷步驟
```bash
# 1. 確認 DB 目前 journal mode
python3 -c "import sqlite3; c=sqlite3.connect('/opt/data/taiwan_stocks.db'); print(c.execute('PRAGMA journal_mode').fetchone()[0]); c.close()"

# 2. 找出所有漏設 timeout 的腳本
grep -rn "sqlite3\.connect(" /opt/data/scripts/ /opt/data/projects/taiwan-stock-cashflow-api/ --include="*.py" \
  | grep -v "timeout="

# 3. 比對 cron 時段衝突（哪些 job 同分鐘）
cronjob list | grep -E "schedule.*16:0[0-9]"  # 16:00~16:09 時段
```

### 催太緊被 429

```bash
# 腳本會自動 exponential backoff，但若持續失敗：
# 1. 檢查 cron log
# 2. 降低 rpm (60 → 30)
# 3. 避開盤中尖峰 (09:00-13:30 TW)
```

### 某檔一直 TooManyRedirects

```python
# twstock.Stock(code) 瞬態網路錯誤，非股票無效
# 解法：在 update_daily.py 中 wrap try/except，排入 retry 清單
# 下次跑會被 checkpoint 略過，需手動重跑該檔
```

### twstock 回傳「查詢日期小於99年1月4日」

**現象：** `twstock.TWSEFetcher.fetch()` 或 `twstock.Stock.fetch_from()` 回傳
`{"stat": "查詢日期小於99年1月4日，請重新查詢!", "data": []}`，即使傳入正確的公元年份（如 2026）。

**原因：** `twstock` ≤1.5.1 的 `TWSEFetcher.fetch()` 在組建 TWSE API URL 時遺漏 `response=json` 參數。
沒有此參數時 TWSE API 誤將傳入的公元年解讀為民國年（例如 2026 → 民國 2026 年），遠小於 99 年的下限，故回傳此錯誤。

**受影響版本：** twstock 1.5.1 及更早版本。

**修復方法：**

```python
# 檔案：<venv>/lib/python3.13/site-packages/twstock/stock.py
# 修改 TWSEFetcher.fetch() 的 params 字典
params = {
    "date": "%d%02d01" % (year, month),
    "stockNo": sid,
    "response": "json",      # ← 加入此行
}
```

修復後清除 `.pyc` 快取：

```bash
rm -f <venv>/lib/python3.13/site-packages/twstock/__pycache__/stock.cpython-313.pyc
```

**驗證方式：** 重新執行測試，應回傳 `stat: OK` 及合法資料。

**注意：** 此 bug 影響所有透過 twstock 拉取 TWSE 歷史股價的行為（包含 `update_daily.py` 的增量更新、`verify_daily_prices.py` 的交叉比對）。TPEX API 端點（`tpex.org.tw`）不受影響，僅 TWSE 端點有此問題。

## Dashboard API Troubleshooting

### `error_monitor` 欄位顯示 `undefined`

**症狀：** 系統狀態頁顯示「總錯誤數: undefined」「警示觸發: undefined」

**原因：** `/health` 端點原本只回傳 `{status, timestamp}`，沒有 `error_monitor` 物件。前端用 `healthRes.error_monitor` 取值，undefined 上再取值還是 undefined。

**修復：** 在 `app.py` 的 `/health` 端點加入 `error_monitor` 結構（含 `total_errors`, `alerts_triggered`, `latest_data_date` 等欄位）。

**⚠️ 前端使用時要加 fallback：**
```javascript
const em = healthRes.error_monitor || {};
const totalErrors = em.total_errors ?? 0;  // 不要直接用 em.total_errors
```

### 資訊訊息誤計入 `alerts_triggered`

**症狀：** 系統正常但「警示觸發」顯示 1

**原因：** 把正常資料日期訊息也 append 到 `alerts_triggered` 陣列，而前端用 `len(alerts_triggered)` 顯示。

**修復：** 拆成 `info_messages[]` 和 `alerts_triggered[]` 兩個陣列。只有真正異常才放進 `alerts_triggered`。

**See also:** `ai-stock-screener` skill 的 `/health` Endpoint 文件

## 多資料來源策略（2026-07-10 更新）

本系統設計上以 **Yahoo Finance** 為主要資料來源、FinMind 為備援，但：

> ⚠️ **2026-07-11 重大修正（推翻前版結論）**：先前以為「Yahoo 在本機完全回空、FinMind 承擔 100%」是**錯的**——根因是 `yf_fetcher.py` 的 bug（缺轉置 / MAP 反向 / empty 判斷錯），不是 Yahoo 不可用。
> 修復後實測：Yahoo 實際覆蓋率 **53.8%**（1880 支 active universe 中 1011 支三表全成功）。
> 剩 **869 支 (46.2%) Yahoo 缺資料，需 FinMind 備援**（抽測 30 支確認備援路徑活著、走新建的 `finmind_client`）。
> 「Yahoo 優先、FinMind 備援」策略**有效**，但 Yahoo 非 100% 覆蓋，FinMind 配額守衛仍是必須。
> 修復細節 + 覆蓋率測法 + finmind_client 設計 → `references/yahoo-fetcher-fix.md`。

| 來源 | 用途 | 狀態 | 參考 |
|------|------|------|------|
| **Yahoo Finance** | 主力（免費無 quota，覆蓋率 ~54%） | ✅ 修復後可用（yf_fetcher bug 已修） | `references/yahoo-fetcher-fix.md` |
| **FinMind** | **實際唯一來源**（quota 有限，需嚴格限流） | ⚠️ 402/403 封鎖風險 | `references/finmind-api-limits.md` |
| **TWSE OpenAPI** | 上市股票備援 | ✅ 已驗證 | `references/api-sources-comparison.md` §2 |
| **TDCC OpenAPI** | 股權分散、ETF 分析（獨家） | ✅ 已驗證 | `references/tdcc-api-investigation.md` |
| **TPEX OpenAPI** | 上櫃股票備援 | ❌ Cloudflare 封鎖 | `references/api-sources-comparison.md` §3 |
| **xfinance** | 曾評估為 yfinance drop-in 替代 | ❌ Yahoo 429 + Stooq CF + 無 .TW | `references/xfinance-evaluation.md` |

### 財報資料來源比較（2026-07-10 新增）

| 來源 | 損益表 | 負債表 | 現金流量表 | 認證 | Quota | 備註 |
|------|--------|--------|------------|------|-------|------|
| Yahoo Finance | ✅ | ✅ | ✅ | 免 | 無 | **主力來源** |
| FinMind | ✅ | ✅ | ✅ | 需要 | 有限 | 備援 |
| TWSE OpenAPI | ✅ | ✅ | ❌ 302 | 免 | 無 | 僅損益+負債 |
| TDCC OpenAPI | ❌ | ❌ | ❌ | 免 | 無 | **不提供財報** |
| TPEX OpenAPI | ❌ | ❌ | ❌ | 免 | — | Cloudflare 封鎖 |

**關鍵決策：**
- Yahoo Finance 是主力（完整三表 + 免認證 + 無 quota 限制）
- FinMind 退居備援（quota 耗盡時自動切換）
- TDCC 經調查確認不提供財報，僅用於股權分散等統計資料

### ⚠️ TDCC OpenAPI 調查結果（2026-07-10）
- 網址：`https://openapi-t.tdcc.com.tw/swagger-ui/index.html`
- Swagger spec：`/tdcc-opendata-api-docs`
- 所有端點分類：股務資訊(1-x)、權益證券統計(2-x)、境外基金(3-x)、境外結構型商品(4-x)、期信基金(5-x)、股東e票通(6-x)
- **結論：TDCC 不提供台股財報資料，無法取代 FinMind**

## 專案目錄結構

```
/opt/data/
├── taiwan_stocks.db                           ← 主 DB（1.5M rows, 1925 檔）
├── update_daily.py                            ← 每日增量更新（16:06 cron）
├── run_daily_incremental_update.sh            ← cron wrapper（price → 技術指標）
├── taiwan-stock-cashflow-api/screening/       ← 【主力】選股腳本（cron 引用）
│   ├── screener.py                            ← 14 種選股策略
│   ├── screener_db.py                         ← DB 查詢（DB_PATH 動態解析）
│   ├── auto_screen_and_notify.py              ← 策略分析 + Telegram 推播
│   └── update_all_tech_indicators.py          ← 全量技術指標計算（12.5s/1925檔）
├── archive_ai_stock_tw/                       ← 📦 已備份（原 ai_stock_tw，最舊版）
├── archive_dashboard/                         ← 📦 已備份（原 ai_stock_tw_dashboard，中間版）
└── skills/taiwan-stock-data-pipeline/         ← 本技能文件
```

### 目錄合併記錄（2026-07-10）

三個 screening 目錄曾長期並存，造成維護負擔。合併過程：
1. **驗證**：檢查三個目錄核心檔案（screener.py, screener_db.py）的 MD5 和行數
2. **確認主力**：`taiwan-stock-cashflow-api/screening/` 是唯一被 cron 引用的版本（832 行 screener.py）
3. **Rename 備份**：`ai_stock_tw/` → `archive_ai_stock_tw/`，`ai_stock_tw_dashboard/` → `archive_dashboard/`
4. **觀察期**：一週後確認主力運作正常再刪除 archive

### 清理 API 比對遺留檔（2026-07-10）

`scripts/` 目錄積累了大量 API 比對測試檔（2026-07-09 同一晚產出），共 51 個檔案可刪除：

```
# 批量刪除 API 比對遺留檔
rm scripts/test_twse_{alt,brotli,csrf,gzip,openapi,opendata,raw,real}.py
rm scripts/test_tpex_{curl,headers,openapi,params,redirect,url}.py
rm scripts/test_finmind_{all,datasets,final,full,screener}.py
rm scripts/test_tdcc{,_categories,_correct,_full,_key,_openapi,_paths}.py
rm scripts/test_open_data.py test_openapi_call.py test_sources.py
rm scripts/compare_api_sources.py final_comparison.py rate_limit_test.py

# 批量刪除舊版迭代腳本（只剩 v3 在用）
rm scripts/fix_incomplete_{dates,fast,parallel,targeted,v4}.py
rm scripts/incremental_update.py incremental_update_loop.py manual_update_jun10_11.py
```

**清理原則：**
- 被 cron 引用 → 保留
- 有明確用途（如 fix_incomplete_v3.py）→ 保留
- 同名系列（test_xxx_a.py, test_xxx_b.py）→ 通常可全刪
- 舊版迭代腳本（v1, v2, v3-old）→ 保留最新版

### ⚠️ 重要：合併前必做
1. 確認 cron job 引用的腳本路徑（目前是 `taiwan-stock-cashflow-api/screening/`）
2. 測試主力版本能正常執行（DB 連線、技術指標計算、推播）
3. 另外兩個目錄是舊版，沒有被任何 cron 引用
4. 合併前先 rename 舊版為 archive/，觀察一週無誤再處理

## 相關技能
### Related skills
- **`ai-stock-screener`** — 台股現金流分析 API（使用本 DB）
- **`taiwan-stock-sqlite-pipeline`** — 泛用建置指南（如何從零開始建立）

> **📋 腳本盤點與清理 SOP → `references/script-inventory-cleanup-sop.md`**
> （含三段檢查法、分類表、2026-07-15 清理 7 檔實例）
>
> ⚠️ **舊版檔案清理記錄（供參考）：**
> 本管線歷經多次迭代，舊腳本（`run_twse_batch.py`, `download_taiwan_stocks.py`,
> `batch_evaluate_financial_v2.py`, `daily_push.py` 等）、舊 DB（`*_part*.db`,
> `bak.corrupt*`）、及舊技能參考檔已於 2026-07-08 全數清除。`update_daily.py`
> 為唯一現行方案。詳細舊名對應請查 session history 或 `naming_cleanup_audit.md`。

### 自動化清理工具

> 2026-07-10 新增 `legacy-script-cleaner.py` 自動化掃描腳本，可檢查 cron 引用並分類檔案。
> 用法：`python3 skills/maintenance/legacy-script-cleanup/scripts/legacy_script_cleaner.py`
