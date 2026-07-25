# Yahoo Fetcher 修復與覆蓋率測量 (2026-07-11)

## 推翻前版錯誤結論
2026-07-10/11 曾記錄「Yahoo 在本機完全回空，FinMind 承擔 100% 財報流量」。此結論**錯誤**——根因是 `yf_fetcher.py` 的 bug，不是 Yahoo 不可用。修復後 Yahoo 實際是有效主力來源（但非 100% 覆蓋）。

## yf_fetcher.py 三個 bug（已修，yfinance 1.5.1）
1. **缺轉置**：yfinance 回傳 index=會計科目、columns=日期，需 `.T` 轉置成 (日期, 科目)。沒轉置 → 後續 pivot 全空。
2. **MAP 方向反**：原本是「我們欄位名 → Yahoo名」，但取欄位時要用「Yahoo名 → 我們名」。反向導致 `Operating Revenue` 沒對應到 `Revenue`。修法：MAP 反轉為 Yahoo名→我們名，且輸出舊欄位名（Revenue/NetIncome/Operating Cash Flow）讓 analyzer 不用改。
3. **empty 判斷錯**：`cashflow_analyzer.py` 原用 `not yf_df.empty`，當 yf_df 是 Series 時拋 ValueError。改用 `len(yf_df) > 0`。

## 修復後覆蓋率（1880 支 active universe）
- Income / Balance / Cashflow 各 **53.8%**（1011/1880 三表全成功）
- **869 支 (46.2%) Yahoo 缺資料 → 需 FinMind 備援**
- 抽測 30 支 Yahoo-missing 股票，備援路徑（新版 `finmind_client`）**30/30 三表全成功**
- `get_active_universe()` 排除金融/保險/證券/ETF，故 1880 ≠ DB 全量 1925（差 45 支金融股）。1925 全量掃描含金融股另測。

## 覆蓋率測量方法（可複現）
```python
# 腳本要放在專案目錄下執行（勿放 /tmp，見下方坑）
import sys; sys.path.insert(0, "/opt/data/projects/taiwan-stock-cashflow-api")
import requests, pickle, time
from screening.screener_db import get_active_universe
import financial_analyzers as fa, cashflow_analyzer as cf
# 擋掉 FinMind → 量 Yahoo-only 覆蓋
orig = requests.get
def guard(*a, **k): raise RuntimeError("blocked")
requests.get = guard; fa.requests.get = guard; cf.requests.get = guard
universe = get_active_universe()   # 或直查 stock_meta 全表拿 1925
done = {}
ia, ba, ca = fa.IncomeAnalyzer(), fa.BalanceAnalyzer(), cf.CashFlowAnalyzer()
for i, s in enumerate(universe):
    c = s["stock_code"]
    if c in done: continue
    done[c] = {"inc": ia.analyze(c)["success"],
               "bal": ba.analyze(c)["success"],
               "cf": ca.analyze_stock(c)["success"]}
    if (i+1) % 100 == 0:
        pickle.dump(done, open("/tmp/yahoo_cov_progress.pkl", "wb"))  # checkpoint 續傳
```
⚠️ **背景進程坑**：`terminal(background) cd PROJ && python /tmp/x.py` 的 cwd **不會**進 `sys.path`（sys.path[0]=腳本目錄 /tmp）→ `ModuleNotFoundError: No module named 'screening'`。**解法**：腳本開頭硬編 `sys.path.insert(0, PROJ)` 或把腳本寫進專案目錄（已寫 `coverage_full_scan.py` 於專案根）。1880 支約 30 分鐘，必須 checkpoint。

## 驗證備援路徑的坑（避免假陰性）
勿手寫 `finmind_client.fetch("TaiwanStockFinancialStatements", {"dataset":...})`——第二個位置參數是 `data_id`（股票代碼字串），不是 dict。錯傳會拿到空資料，誤判「FinMind 也沒資料」。要用**真實 analyzer 的呼叫簽名**：`finmind_client.fetch("TaiwanStockFinancialStatements", stock_code, start_date)`。

## finmind_client.py（新建：配額守衛 + 磁碟快取）
- 位置：`screening/finmind_client.py`，singleton `finmind_client`
- **磁碟快取**：sqlite `screening/finmind_cache.db`（TTL 7 天），跨 cron job / 跨執行共享。舊 `api_cache` 是純記憶體，每次重跑清空 → 這是 cron 之間重複打 FinMind 的根因。
- **配額守衛**：`_check_quota()` 查 `user_info`，剩 ≤20 次就 raise `QuotaExceeded` 優雅停；本地計數器遞減，5 分鐘才重查一次（避免配額檢查本身刷 API）。
- **斷路器**：`403 ip banned` → 睡一次 30 分鐘後重試一次，絕不在每支股票各自 sleep（修掉舊 `retry_after` 死循環 bug）。
- **接法**：`financial_analyzers.py` / `cashflow_analyzer.py` 的 `_do_fetch*` 改 call `finmind_client.fetch(...)` 並 catch `(QuotaExceeded, IPBanned)`。

## 配額數學（關鍵）
869 支 × 3 表 = 2607 次呼叫 >> 600/天。配額守衛會在 ~580 次自停。→ 需**分批回填**（~100 支/天 ≈ 300 次，約 9 天填滿快取），填完後日常只打 Yahoo（免費）。
