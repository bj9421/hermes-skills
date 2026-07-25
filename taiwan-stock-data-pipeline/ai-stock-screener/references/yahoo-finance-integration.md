# Yahoo Finance 整合 — 已知坑與驗證紀錄

（更新：2026-07-11，yfinance 1.5.1 / pandas 2.x on RPi4 DietPi）

## 核心結論

台股三表（損益表 / 資產負債表 / 現金流量表）**可 100% 由 Yahoo Finance 供給**，免 token、無每日限額。
FinMind 只應保留給 Yahoo 缺資料的備援路徑（股息、股價、TaiwanStockInfo 清單）。

專案 `yf_fetcher.py` 之前三個 bug 導致 Yahoo 永遠回空、全部 fall back 到 FinMind，
把 FinMind 600/天配額刷爆 → IP 被 ban 30 分鐘 → `retry_after` 不存在 → 程式死循環。

---

## Bug 1 — yfinance 新版資料方向（致命）

yfinance 1.5.x 回傳的財報 DataFrame 是：
- **index = 會計科目（account names，字串）**
- **columns = 日期（Timestamp）**

舊程式直接對 `df.index` 做 `pd.to_datetime(df.index)`，去解析 `"Tax Effect Of Unusual Items"`
這種科目名 → `DateParseError` → 被 `except Exception: return None` 吞掉。

**修法：** 先 `.T` 轉置，讓 `index=日期, columns=科目`，再 `pd.to_datetime(df.index)`：

```python
def _normalize(df):
    if df is None or len(df) == 0:   # 用 len()，見 Bug 3
        return None
    df = df.T                         # index=dates, columns=accounts
    df.index = pd.to_datetime(df.index)
    return df.sort_index(ascending=False)
```

## Bug 2 — 欄位 MAP 方向反了

`INCOME_MAP` 等原本是 `{我們名: yahoo名}`，但映射時用：
```python
mapped.columns = [INCOME_MAP.get(c) for c in mapped.columns]  # c 是 yahoo 名
```
`INCOME_MAP.get("Operating Revenue")` 查不到（key 是 `"Revenue"`）→ 欄位名原封不動留下。
analyzer 用 `_safe(pivot, "Revenue")`（無空格）去查 `"Operating Revenue"`（有空格）→ 全 miss。

**修法：** MAP 反轉為 `{yahoo名: 我們名}`，輸出 analyzer 用的舊欄位名：

```python
INCOME_MAP = {
    "Operating Revenue": "Revenue",
    "Gross Profit": "GrossProfit",
    "Operating Income": "OperatingIncome",
    "Net Income": "NetIncome",
    "Diluted EPS": "EPS",
    "Cost Of Revenue": "CostOfGoodsSold",
    "Operating Expense": "OperatingExpenses",
}
BALANCE_MAP = {
    "Current Assets": "CurrentAssets",
    "Current Liabilities": "CurrentLiabilities",
    "Total Assets": "TotalAssets",
    "Total Liabilities Net Minority Interest": "TotalLiabilities",
    "Total Equity Gross Minority Interest": "Equity",
    "Cash And Cash Equivalents": "CashAndCashEquivalents",
    "Accounts Receivable": "AccountsReceivableNet",
    "Inventory": "Inventory",
}
CASHFLOW_MAP = {
    "Operating Cash Flow": "OperatingCashFlow",
    "Capital Expenditure": "CapitalExpenditure",
    "Free Cash Flow": "FreeCashFlow",
    "Depreciation And Amortization": "Depreciation",
    "Change In Working Capital": "WorkingCapital",
}
```

驗證：2026-07-11 實測 2330/2317/2454/2303/3008/2412/6505 全部欄位命中。

## Bug 3 — `not df.empty` 對新版 yfinance 拋 ValueError

yfinance 1.5.1 的 `cashflow` 在某些股票會回傳 `empty` 屬性為 **Series**（不是 bool），
`if not yf_df.empty:` → `ValueError: The truth value of a Series is ambiguous`。

**修法：** 用 `len(yf_df) > 0` 判斷；遍歷值時對單格 `pd.notna(val)` 包 `try/except (ValueError, TypeError)`。

## Bug 4 — cashflow_analyzer.py 完全沒接 Yahoo

`cashflow_analyzer.py` 是 app.py 抽出的獨立檔，原本**直接打 FinMind**，沒 import `yf_fetcher`。
要在 `CashFlowAnalyzer._fetch_cashflow_data` 開頭加 Yahoo 優先路徑（轉成
`{"date","type","value"}` records 格式），FinMind 降為備援。

---

## FinMind 封鎖行為（必須知道，避免死循環）

- 配額（Free）：`api_request_limit` = 600/天，`api_request_limit_hour` = 600/小時
- 超額回應：`402 {"msg":"Requests reach the upper limit"}`
- IP ban 回應：`403 {"msg":"ip banned","status":403}` → **沒有 `retry_after` 欄位**
- ban 時長：IP 自動封 **30 分鐘**，期間繼續打 4xx 會「再被封鎖」
- **致命陷阱**：舊程式 `body.get("retry_after", 300)` 永遠拿到 300，然後
  `time.sleep(300)` 後回傳 None 繼續跑下一支 → 每支又打 403、又睡 300s → 無限浪費。
  **修法**：偵測 403 就整批停，不要 per-stock sleep；ban 期間不打網路。

---

## 端到端驗證腳本（攔 FinMind 證明 Yahoo 覆蓋）

```python
import requests
guard = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("FinMind blocked"))
requests.get = guard
import financial_analyzers as fa, cashflow_analyzer as cf
cf.requests.get = guard
for code in ["2330","2317","2454","2303","3008","2412","6505"]:
    inc=fa.IncomeAnalyzer().analyze(code)
    bal=fa.BalanceAnalyzer().analyze(code)
    cfa=cf.CashFlowAnalyzer().analyze_stock(code)
    assert inc['success'] and bal['success'] and cfa['success']
# 若全部 PASS 且 guard 沒被呼叫 → Yahoo 完全覆蓋三表，FinMind 呼叫 = 0
```

## 單支股票 request 成本（修復前 vs 後）

| | 修復前 | 修復後 |
|---|---|---|
| income/balance/cashflow | 各走 FinMind ×1 | Yahoo（0 FinMind call）|
| ROE 計算重複抓 income/balance | +2 FinMind | Yahoo |
| 股息/股價 | +2 FinMind | FinMind（獨佔）|
| **單支合計 FinMind 呼叫** | **~7** | **~2（僅股息/股價）** |

541 支 × 7 ≈ 3800 >> 600/天 → 必 ban。修復後單支 ~2 且可由 Yahoo 再降。
