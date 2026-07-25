# 股票腳本盤點與清理 SOP

## 什麼時候做

- 用戶主動問「有測試或舊版可刪除嗎」
- 感覺到 scripts/ 目錄累積了過多不明腳本
- 管線迭代（新腳本上線後）— 清理舊版

## 盤點流程

### Step 1: 全面掃描

```bash
# 所有 stock 相關檔名
find /opt/data/scripts -name '*stock*' -o -name '*twse*' -o -name '*tech*' -o -name '*ohlc*' | sort

# 所有 .db / .json 資料檔
ls -lh /opt/data/*.db /opt/data/*.json

# projects/ 下的相關腳本
ls /opt/data/projects/taiwan-stock-cashflow-api/screening/
```

### Step 2: 檢查引用

對每個候選檔案確認三層：

1. **Cron 引用** — `cronjob list` 看是否有 no_agent script 或 prompt 引用此檔案
2. **跨檔案引用** — `grep -rl "檔名" /opt/data/scripts/ /opt/data/projects/ --include="*.py" --include="*.sh" | grep -v __pycache__`
3. **Shebang 是否還活著** — 頭兩行是否指向存在的 venv/unix 工具

### Step 3: 分類

| 類別 | 判定 | 處置 |
|------|------|------|
| **孤兒** | 零引用 + 已失能 | 可安全刪除（先備份） |
| **舊版迭代** | 命名含 v1/v2/v3-old / 明顯被 `update_daily.py` 取代 | 保留最新版 + 備份舊版後刪除 |
| **死連結** | shebang 指向 `/opt/hermes/`（已不存在） | 備份後刪除 |
| **測試腳本** | 無 cron 引用 + 測試目的 | 確認無引用後可刪；正式 pytest 保留 |
| **工具類** | 功能獨立（fetch_dividend_yield, check_progress） | 保留 |
| **第三方專案測試** | tw-stock-radar/tests/ 等 | 不動（不是你的） |

### Step 4: 備份後刪除

```bash
# 建立日期標記的歸檔目錄
mkdir -p /opt/data/archive/stock-scripts-$(date +%Y-%m-%d)

# 批量複製
cp -v /path/to/file1 /path/to/file2 ... /opt/data/archive/stock-scripts-YYYY-MM-DD/

# 確認備份成功 → 刪除原始檔
rm -v /path/to/file1 /path/to/file2 ...
```

### Step 5: 報告

向用戶報告：
- 刪了哪些檔案（列表 + 大小）
- 為什麼（被取代 / 零引用 / 死連結）
- 備份位置
- 殘留內容摘要

## 實際案例

### 2026-07-15 清理（7 檔）

**孤兒舊版（5 檔）：** `fetch_stocks.py`, `update_stocks.py`, `run_twse_batch.py`, `verify_twse_data.py`, `test_twse.py`
→ 屬最早版 twstock 抓取器，被 `update_daily.py` 取代，零 cron 引用

**死連結（1 檔）：** `run_twse_daily_update.sh` → shebang 指向已不存在的 `run_twse_daily_update.py`

**死包裝器（1 檔）：** `run_update_with_timeout.py` → 管線已改用 `run_daily_incremental_update.sh` 直接呼叫

**結果：** `stock-tools/` 從 7 檔減為 2 檔（check_progress.py, fetch_dividend_yield.py），乾淨整齊。

### 2026-07-10 清理（~51 檔）

批量清理測試遗留檔（`test_twse_*.py`, `test_tpex_*.py`, `test_finmind_*.py`, `test_tdcc_*.py`）及舊版迭代腳本（`fix_incomplete_{dates,fast,parallel,targeted,v4}.py` 等）。
原則：同名系列保留最新版，被 cron 引用的保留，純測試用途的刪除。
