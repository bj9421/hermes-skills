---
name: ai-stock-screener
description: Use when launching the Taiwan Stock Cashflow Analysis API server (taiwan-stock-cashflow-api). Provides startup, health check, and basic usage guidance.
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [taiwan-stock, cashflow, api, screener, stocks]
    related_skills: [taiwan-stock-data-pipeline]
---

# AI 選股 - 台股現金流分析 API

## Overview

本技能用於啟動與操作 `/opt/data/projects/taiwan-stock-cashflow-api` 專案，這是一個提供台灣上市公司現金流及財務分析的本地 API 伺服器。

## When to Use

- 需要啟動台股現金流分析 API 伺服器時
- 需要檢查伺服器運行狀態時
- 需要查詢特定股票財務分析資料時

## Project Structure

> **⚠️ 重要：** 專案實際位置為 `/opt/data/projects/taiwan-stock-cashflow-api/`，**非** `/opt/data/taiwan-stock-cashflow-api/`。後者僅有一個過時的 `screening/` 子目錄，不包含完整專案。看門狗腳本 `/opt/data/scripts/taiwan-stock-cashflow-watchdog.py` 過去因此路徑錯誤而失效（2026-07-13 已修復）。

```
/opt/data/projects/taiwan-stock-cashflow-api/
├── app.py                  # 主應用程式 (Flask)
├── financial_analyzers.py  # 財務分析模組
├── batch_update_cache.py   # 批次掃描填充 screen_cache
├── daily_notify.py         # 每日推播功能（原名 daily_push.py）
├── start_server.py         # 啟動腳本
├── restart_server.py       # 重啟腳本
├── requirements.txt
├── taiwan_stocks.db        # 台股資料庫（symlink → /opt/data/taiwan_stocks.db；原有本地副本已刪除，統一指向 root DB）
└── screening/              # 選股邏輯資料夾
    ├── screener_api.py     # 篩選 API 路由 (需 register_screener_routes(app) 註冊)
    ├── screener.py         # 篩選邏輯核心
    ├── update_all_tech_indicators.py  # 技術指標批量計算
    └── auto_screen_and_notify.py      # 篩選+通知
```

## Quick Start

### 1. 啟動伺服器

> **兩種啟動方式：**

#### a) 前景執行（除錯／手動）

```bash
cd /opt/data/projects/taiwan-stock-cashflow-api
source .venv/bin/activate
python app.py
```

#### b) 背景執行（cron / 無介面 — ⬅️ 常用）

```bash
cd /opt/data/projects/taiwan-stock-cashflow-api && .venv/bin/python app.py
```

> **⚠️ `source .venv/bin/activate` 在非互動式 shell 中可能無法正確設定環境。** 背景執行（`terminal(background=true)`）或 cron 腳本中，請使用 **完整 venv Python 路徑** 直接執行：`/opt/data/projects/taiwan-stock-cashflow-api/.venv/bin/python app.py`。

伺服器預設運行於 `http://localhost:5000`

### 2. 確認伺服器狀態

```bash
curl http://localhost:5000/
```

預期回應：
```json
{
  "message": "現金流分析 API (支持年度累計資料)",
  "usage": "/analyze/<stock_code>",
  "version": "1.2"
}
```

### 3. 分析股票

```bash
# 分析台積電 (2330)
curl http://localhost:5000/analyze/2330

# 分析鴻海 (2317)
curl http://localhost:5000/analyze/2317
```

## API Endpoints

| 端點 | 說明 | 範例 |
|------|------|------|
| `GET /` | 伺服器狀態 | `curl localhost:5000/` |
| `GET /dashboard` | 策略選股儀表板（HTML） | Browser → `localhost:5000/dashboard` |
| `GET /api/heatmap` | 熱力圖資料（市值前100漲跌幅） | `curl localhost:5000/api/heatmap` |
| `GET /analyze/<code>` | 分析指定股票現金流 | `curl localhost:5000/analyze/2330` |
| `GET /health` | 健康檢查 | `curl localhost:5000/health` |
| `GET /screen/strategies` | 列出所有篩選策略 | `curl localhost:5000/screen/strategies` |
| `GET /screen/strategy/<name>` | 執行指定篩選策略 | `curl localhost:5000/screen/strategy/BB_TOUCH_LOWER` |

### 熱力圖回應格式

```json
{
  "success": true,
  "date": "2026-07-08",
  "prev_date": "2026-07-07",
  "stocks": [
    {
      "code": "2330",
      "name": "台積電",
      "industry": "半導體業",
      "market_cap": 639233.92,
      "price": 2465.0,
      "change_pct": 1.02,
      "change_dir": "up"
    }
  ],
  "total": 100
}
```

## 台灣股市顏色慣例 ⚠️

**🇹🇼 台股配色（與歐美相反）：**
- **🔴 紅 = 漲**（上漲）
- **🟢 綠 = 跌**（下跌）
- **⚪ 平 = 灰**

Dashboard 熱力圖的 Canvas 繪圖（`static/index.html`）需注意：
1. 區塊背景色：`chg > 0 → 紅`, `chg < 0 → 綠`
2. 區塊內文字一律白色（漲跌靠背景色區分，不需再上色文字）
3. 文字佈局：股號（白粗體）→ 股名（灰）→ 漲跌幅（白粗體），垂直三行
4. 漲跌幅文字**不**另外用紅綠色，統一白色

## 修改後重啟伺服器

修改 `static/index.html` 或 `app.py` 後必須重啟 Flask 伺服器才會生效：

```bash
# 1. 查詢背景程序
# 2. kill 舊的
# 3. 重啟（background=true）
cd /opt/data/projects/taiwan-stock-cashflow-api && .venv/bin/python app.py
```

注意：`static/index.html` 每次 request 從 disk 讀取（Flask 預設不 cache），但 `app.py` 的 Python 模組不會熱更新。

## `/health` Endpoint — `error_monitor` Schema

`GET /health` 回傳結構：

```json
{
  "status": "healthy|warning|error",
  "timestamp": "ISO-8601",
  "error_monitor": {
    "total_errors": 0,
    "alerts_triggered": 0,
    "info": ["✅ 最新資料: 2026-07-08"],
    "alerts": [],
    "latest_data_date": "YYYY-MM-DD",
    "latest_data_rows": 1913
  }
}
```

**邏輯規則：**
- `days_since <= 1`（資料 ≤ 1 天前）→ `status: healthy`, `total_errors: 0`, 訊息放入 `info[]`
- `days_since == 2`（資料 2 天前）→ `status: warning`, `total_errors: 1`, 警告放入 `alerts[]`
- `days_since >= 3`（資料 3 天前以上）→ `status: error`, `total_errors: 1`

**⚠️ 重要：`info_messages` 和 `alerts_triggered` 是分開的陣列。** 前端顯示 `alerts_triggered` 時只會計 `alerts[]` 的長度，不會計 `info[]`。不要把正常訊息塞進 `alerts_triggered`。

**前端使用方式：**
```javascript
const em = healthRes.error_monitor || {};
const totalErrors = em.total_errors ?? 0;
const alertsTriggered = em.alerts_triggered ?? 0;
// 不要直接用 em.total_errors，API 可能未回傳
```

## Key Anti-Pattern: `fetchWithTimeout` Returns Parsed JSON, Not Response

`static/index.html` 中的 `fetchWithTimeout()` helper **已經在內部呼叫 `r.json()`**，所以回傳的是**解析好的 JS 物件**，**不是 `Response` 物件**。

```javascript
// ❌ 常見錯誤：當 Response 物件處理
const res = await fetchWithTimeout('/api/something');
if (res.ok) { ... }                    // undefined，永遠 false
const data = await res.json();         // TypeError: res.json is not a function

// ✅ 正確：直接存取 JSON 屬性
const res = await fetchWithTimeout('/api/something');
if (res && res.success) { ... }        // 用 .success 而非 .ok
const data = res.data;                 // 已解析完成，不需 await .json()
```

這個問題導致了 Session 中的「2330 沒資料」bug：`screenRes.ok` 和 `analyzeRes.ok` 皆為 `undefined`，整段分析 UI 被跳過。

**項目中所有使用 `fetchWithTimeout` 的地方都要注意：**
- `loadDashboard()` → `healthRes`, `stratRes`
- `runStrategy()` → `res`
- `analyzeStock()` → `analyzeRes`, `screenRes`

檢查 `static/index.html` 時搜尋 `.ok` 和 `.json()` 呼叫模式。

## 資料來源與 Token 注入

本專案的財務資料來自多個來源，主力為 **Yahoo Finance**，FinMind 作為備援：

### FinMind Token 注入（2026-07-09 修復）

**問題：** 過去所有腳本使用免費 IP-based 存取，批量處理 876+ 檔會在 ~17 分鐘內觸發 `BannedWait`。

**修復：** 所有模組已更新為從 `/opt/data/.env` 讀取 `FINMIND_API_KEY` 並自動注入 token：
- `financial_analyzers.py` → `_make_params()` helper
- `cashflow_analyzer.py` → `_make_params()` helper
- `screening/screener.py` → `_make_screener_params()` helper
- `screening/batch_evaluate_financial.py` → imports `_make_screener_params`
- `app.py` → token loading + params helper
- `heatmap/app.py` → 同上

**路徑注意：** `.env` 相對於專案根目錄的路徑為 `../.env`（從 `/opt/data/projects/taiwan-stock-cashflow-api/` 目錄執行時）。

### 多資料來源策略（2026-07-10 更新；2026-07-11 修正 Yahoo 實際故障）

| 來源 | 用途 | 狀態 | 參考 |
|------|------|------|------|
| **Yahoo Finance** | **主力**（全財報覆蓋） | ✅ 已修復並驗證 | `references/yahoo-finance-integration.md` |
| **FinMind** | 備援（quota 有限） | ⚠️ 402 超限 / 403 IP ban | 同上 §FinMind 封鎖行為 |
| **TWSE OpenAPI** | 上市股票備援 | ✅ 已驗證 | `references/api-sources-comparison.md` §3 |
| **TDCC OpenAPI** | 股權分散、ETF 分析（獨家） | ✅ 已驗證 | `references/api-sources-comparison.md` §5 |
| **TPEX OpenAPI** | 上櫃股票備援 | ❌ Cloudflare 封鎖 | `references/api-sources-comparison.md` §4 |

> ⚠️ **Yahoo 曾長期「靜默失效」**：`yf_fetcher.py` 多個 bug 讓 Yahoo 回空、全 fall back FinMind，
> 把 FinMind 600/天刷爆 → IP ban。除非跑過 `references/yahoo-finance-integration.md` 的攔截驗證，
> 否則**不要假設 Yahoo 正常**——它失敗時是 `except: return None`，不會報錯。
> 程式碼層面：cron 模型（LLM）與 FinMind token 是**兩回事**，cron job 各自 pin 模型不代表 FinMind 配額隔離；
> 所有腳本讀同一把 `FINMIND_API_KEY`，需集中配額守衛。

### yf_fetcher.py 致命 bug（2026-07-11 修復，詳見 references/yahoo-finance-integration.md）

1. **資料方向反了**：yfinance 1.5.x 回傳 `index=科目, columns=日期`，舊程式對科目名做 `to_datetime` → 崩潰被吞。修法：先 `.T` 轉置再處理。
2. **欄位 MAP 方向反了**：原本 `{我們名: yahoo名}` 卻用 yahoo 名去查 → 全 miss；analyzer 讀 `Revenue` 查不到 `Operating Revenue`。修法：反轉為 `{yahoo名: 我們名}`。
3. **`not df.empty` 對新版 yfinance 拋 ValueError**（empty 回傳 Series 非 bool）→ 用 `len(df) > 0`。
4. **`cashflow_analyzer.py` 完全沒接 Yahoo**，直接打 FinMind → 需在 `_fetch_cashflow_data` 加 Yahoo 優先路徑。

### FinMind 封鎖死循環陷阱（必看）

- 403 回應 `{"msg":"ip banned","status":403}` **沒有 `retry_after` 欄位**，舊程式 `body.get("retry_after", 300)` 永遠 300 → per-stock `sleep(300)` 後繼續打 → 無限浪費 + 持續 ban。
- 修法：偵測 403 **整批停**，ban 期間不打網路；配額逼近 600/天就優雅停止，不硬幹 402。

## Common Pitfalls

1. **虛擬環境與背景啟動陷阱**：`source .venv/bin/activate` 在互動式 shell 中運作正常，但在**背景程序**（`terminal(background=true)`、cron）或某些非互動式 shell 中可能失效。這時 Flask 會報 `ModuleNotFoundError: No module named 'flask'`。**解法：** 使用完整 venv Python 路徑直接執行：`/opt/data/projects/taiwan-stock-cashflow-api/.venv/bin/python app.py`

2. **埠號衝突**：預設使用 5000 port，若被佔用需修改 `app.py`

3. **資料庫路徑解析**：`screening/` 的腳本透過 `DB_PATH` 優先順序決定使用哪份資料庫：\n   - **① `$STOCK_DB_PATH` 環境變數** → 最高優先\n   - **② `/opt/data/taiwan_stocks.db`** → 若此檔存在（通常是新的）\n   - **③ 專案本地的 `/opt/data/projects/taiwan-stock-cashflow-api/taiwan_stocks.db`** → 最後備援\n   `/opt/data/taiwan_stocks.db` 存在時，專案本地的 DB *不會被讀取*。如要強制使用專案本地 DB，設定 `STOCK_DB_PATH=/opt/data/projects/taiwan-stock-cashflow-api/taiwan_stocks.db`。
   詳細的 DB 庫存管理請參考 `taiwan-stock-data-pipeline` 的 `references/db_inventory_management.md`。

4. **背景執行**：若要在背景執行，使用 `background=true` 參數。詳見上方 Quick Start §1.b 的背景執行方式 — 務必使用完整 venv Python 路徑，而非 `source .venv/bin/activate`。

5. **註冊篩選 API 路由**：`screening/screener_api.py` 的 `register_screener_routes(app)` **不會自動執行**。必須在 `app.py` 中手動 import 並呼叫：
   ```python
   from screening.screener_api import register_screener_routes
   register_screener_routes(app)
   ```
   若忘記加，`/screen/strategies` 等端點回傳 404，導致 Dashboard 首頁 JS 崩潰（`stratRes` 為 null，`stratRes.strategies` 報錯）。

6. **JS API 回傳 null 安全檢查**：`fetchWithTimeout()` 在 API 失敗時回傳 `null`。所有 API 回應的屬性存取都需 null guard：
   ```javascript
   // ❌ 會 crash
   if (stratRes.strategies) { ... }
   // ✅ 安全
   if (stratRes && stratRes.strategies) { ... }
   ```

7. **Dashboard 熱力圖只有 2 檔股票**：`static/index.html` 的 `drawTreemap()` 中面積公式 `(50 - i) * 200 + 100` 只支援前 50 檔。當 API 回傳 >50 檔（`/api/heatmap` LIMIT 100），第 51 檔以後的 area 變負數，d3 treemap 會炸掉。解法：`.slice(0, 50)`。

8. **Dashboard 熱力圖空白或 `roundRect` 錯誤**：部分手機瀏覽器不支援 Canvas `ctx.roundRect()`（較新的 API）。`index.html` 有 `try/catch` fallback 到 `ctx.rect()`，若修改了那段要注意保留。

9. **Dashboard 熱力圖躺平（全部水平長條）**：Canvas 長寬比影響 squarified treemap 的區塊形狀。`H = W * 1.1`（接近正方形）效果最好。若設 `H = W * 0.65`（太扁）會產出大量橫條。

10. **Canvas Treemap 開發注意事項**：熱力圖使用 d3-hierarchy squarified treemap 渲染在 Canvas 上。已知陷阱：
    - `ctx.roundRect()` 舊版 Safari 不支援 → 加 try/catch fallback 到 `ctx.rect()`
    - 面積公式 `(50-i)*200+100` 只適用 ≤50 檔 → 務必先 `.slice(0,50)`
    - Canvas 長寬比 → `H = W * 1.1`（接近正方形），太扁會出長條區塊
    - 台股顏色慣例：紅漲綠跌（與歐美相反）
    - 區塊內文字統一白色，漲跌靠背景色區分
    - 標籤三層高度門檻：`r.h > 16`（股號）→ `> 26`（+股名）→ `> 34`（+漲跌幅）
    
    完整開發經驗紀錄：`references/canvas-treemap-lessons.md`

11. **專案路徑混淆（已多次踩坑）**：此專案位於 **`/opt/data/projects/taiwan-stock-cashflow-api/`**，但舊文件、看門狗腳本、以及部分 cron 設定曾指向不存在的 `/opt/data/taiwan-stock-cashflow-api/`（僅有過時的 `screening/` 子目錄）。此外，`/opt/data/archive_ai_stock_tw/` 也包含一份完整的 Flask app 副本（含 `app.py`、`start_server.py`、`restart_server.py`），該路徑曾有 cron/service 從此啟動。若服務無法啟動，第一步先確認 `app.py` 實際存在於哪個目錄、以及 `.venv/` 是否在對應目錄中。看門狗腳本 `scripts/taiwan-stock-cashflow-watchdog.py` 已於 2026-07-13 修復路徑。
    - **具體實例（2026-08-08 修復）**：`screening/auto_screen_and_notify.py` 內硬編碼結果保存路徑為 `/opt/data/taiwan-stock-cashflow-api/screening/latest_results.json`（少 `projects/`），導致 cron 指定的 `/opt/data/projects/.../latest_results.json` 一直是舊檔。檢查 cron 指定路徑的檔案時先看 mtime 是否為當日；已修正為含 `projects/` 的正確路徑（第 336 行保存 + 第 350 行提示訊息）。

12. **gunicorn worker 崩潰：numpy cross-venv 路徑問題**（2026-07-13 發現並修復）
    **症狀：** 啟動 gunicorn 後 worker 立即 crash，log 顯示 `ImportError: Unable to import required dependency numpy`，但用 `.venv/bin/python3 -c "import numpy"` 測試卻正常載入。
    **根因：** numpy 安裝在**其他 venv**（如 `/opt/data/.hermes-numpy-venv/`），該路徑透過 `.pth` 檔案或 `sys.path` 可被當前 venv 的 Python 看到。直接 `python3 -c` 測試時能找到 numpy，但 **gunicorn 的 worker 子程序在 fork 後只載入本機 site-packages，不繼承外部 `sys.path` 條目**，導致 pandas import numpy 時失敗。
    **修復：**
    ```bash
    # 在專案 venv 內強制重新安裝 numpy（寫入本機 site-packages 目錄）
    .venv/bin/pip install --force-reinstall --no-deps numpy
    ```
    **驗證：** 重啟 gunicorn，檢查 `/health` endpoint 回傳 200。
    **預防：** 建立或重建 venv 後，用完整路徑確認 numpy/pandas 在該 venv 的 site-packages 內可用：
    ```bash
    .venv/bin/python3 -c "import numpy; import pandas; print('numpy', numpy.__version__, 'pandas', pandas.__version__)"
    ```
    不要只依賴 `python3 -c "import numpy"`（可能使用外部 site-packages 路徑）。

13. **完整恢復程序（venv + 相依套件全遺失）**
    當系統升級、容器重啟、或磁碟清理後專案 venv 完全消失時：
    ```bash
    cd /opt/data/projects/taiwan-stock-cashflow-api   # 或 archive_ai_stock_tw（依實際部署路徑）
    # 建立 venv（使用系統 Python 的 venv 模組，uv 在容器內可能因 /root/.cache 權限不足失敗）
    python3 -m venv .venv
    # 安裝所有相依套件
    .venv/bin/pip install -r requirements.txt
    # 檢查 numpy 是否正確載入（有 cross-venv 風險，見 pitfall #12）
    .venv/bin/python3 -c "import numpy; import pandas; import flask; print('Deps OK')"
    # 啟動服務
    .venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 --timeout 60 app:app
    ```
    ⚠️ `uv` 在容器內可能因 `/root/.cache/` 權限問題失敗，改用 `python3 -m venv` + `venv/bin/pip install`。

## 自動重啟機制（Watchdog）

專案附帶一個看門狗腳本，用於 cron 環境下自動檢測 API 是否存活並重啟：

- **腳本位置：** `/opt/data/scripts/taiwan-stock-cashflow-watchdog.py`
- **運作方式：** 檢查 `http://127.0.0.1:5000/health` 是否回傳 200，若失敗則重新啟動 Flask 伺服器（double‑fork detach）
- **建議 cron 排程：** 每 5–10 分鐘執行一次，例如 `*/5 * * * * python3 /opt/data/scripts/taiwan-stock-cashflow-watchdog.py`
- **日誌位置：** `/opt/data/projects/taiwan-stock-cashflow-api/server.log`

## 同步到 Obsidian

若要將此技能的文件同步到 Obsidian Vault：

```
/opt/data/obsidian-vault/技能筆記/
```

### 注意事項
- `Hermes/` 目錄由 user `1000` 擁有，直接寫入會有權限問題
- 請使用 `技能筆記/` 目錄（hermes 用戶可寫入）
- 必要時可手動將檔案移至 `Hermes/` 目錄

## Verification Checklist

- [ ] 確認虛擬環境已啟動
- [ ] `curl localhost:5000/` 回傳預期 JSON
- [ ] `curl localhost:5000/analyze/2330` 回傳分析結果
- [ ] `curl localhost:5000/screen/strategies` 回傳策略列表
- [ ] Dashboard 熱力圖正常顯示 50 檔區塊
- [ ] `server.log` 無錯誤訊息
