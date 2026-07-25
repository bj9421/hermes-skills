# 台股資料來源 API 比較分析

> 建立於 2026-07-09，最後重大更新 2026-07-10。
> 完整報告另存於 `/opt/data/projects/taiwan-stock-cashflow-api/API_COMPARISON.md`

## ⚠️ 重大變更（2026-07-10）

**Yahoo Finance 已取代 FinMind 成為主力資料來源。** 原因：
1. FinMind 免費額度耗盡（402 錯誤）
2. Yahoo Finance 提供完整三大財報（損益表+負債表+現金流量表）
3. TDCC 經調查確認**不提供台股財務報表**

---

## 資料來源總覽（2026-07-10 更新）

| 來源 | 財報覆蓋 | 即時行情 | 免認證 | 穩定性 | 備註 |
|------|----------|----------|--------|--------|------|
| **Yahoo Finance** | ✅ 完整 | ✅ | ✅ | ✅ | **主力來源** |
| **FinMind** | ✅ 完整 | ✅ | ✅ | ⚠️ 限額 | 備援 |
| **TWSE OpenAPI** | ⚠️ 部分 | ✅ | ✅ | ✅ | 現金流量表端點失效 |
| **TPEX OpenAPI** | ❌ 無法存取 | ❌ | ✅ | ❌ | Cloudflare 保護 |
| **TDCC OpenAPI** | ❌ 無此資料 | ❌ | ✅ | ✅ | 基金/股權分散/統計 |
| **yfinance (library)** | ❌ 不完整 | ✅ | ✅ | ✅ | 僅價格資料 |

## 1. Yahoo Finance（主力來源，2026-07-10 起）

- **用途:** 損益表 + 負債表 + 現金流量表（完整覆蓋）
- **認證:** 免認證
- **實作:** `yf_fetcher.py` + `financial_analyzers.py` 整合
- **速度:** ~1-2 秒/檔
- **覆蓋:** 100% 台股（上市+上櫃+興櫃）
- **欄位映射:** 見 `references/yahoo-finance-integration.md`

### 欄位對照（Yahoo → 內部）
- 損益表: `Operating Revenue` → revenue, `Gross Profit` → gross_profit, `Net Income` → net_income, `Diluted EPS` → eps
- 負債表: `Total Assets` → total_assets, `Total Equity` → equity, `Current Assets` → current_assets, `Cash And Cash Equivalents` → cash
- 現金流量表: `Operating Cash Flow` → operating_cash_flow, `Capital Expenditure` → capital_expenditure, `Free Cash Flow` → free_cash_flow

### 已知問題
1. Date parsing warning: `UserWarning: Could not infer format` — 無害
2. `verify=False` SSL warning from urllib3 — 僅 cosmetic
3. 新上市/小型公司可能回傳 NaN

## 2. FinMind（備援）

- **用途:** 備援來源（quota 耗盡時自動切換）
- **認證:** API Key（JWT Token，存放於 `/opt/data/.env` 的 `FINMIND_API_KEY`）
- **關鍵端點:** `FinancialStatements`, `BalanceSheet`, `CashFlowsStatement`
- **限制:** 免費額度有限，批量處理易觸發 402
- **已修復:** 所有腳本已注入 token（2026-07-09 完成）

## 3. TWSE OpenAPI（上市股票備援）

- **Base URL:** `https://openapi.twse.com.tw/v1`
- **認證:** 免認證
- **端點數量:** 143 個
- **財務報表端點:**
  - `t187ap03_L` — 上市公司基本資料（含市值）✅ 可用
  - `t187ap06_L` — 損益表 ✅ 可用
  - `t187ap07_L` — 負債表 ✅ 可用
  - `t187ap08_L` — 現金流量表 ❌ 302 redirect（失效）
- **限制:** 僅上市股票，無現金流量表
- **優勢:** 免認證、無 quota、適合大規模批次請求

## 4. TPEX OpenAPI（上櫃股票 — 2026-07-10 調查確認不可用）

- **Base URL:** `https://www.tpex.org.tw/openapi`
- **Swagger JSON:** 可下載（476KB），定義 225 個端點（含 33 個財務報表端點）
- **財務報表端點:** 綜合損益表×6 + 資產負債表×6 + 財報資訊×6 + 興櫃損益表×6 + 興櫃負債表×5 + 財測×3
- **實際狀態:** 所有 API 端點（含 `/openapi/api/mopsfin_t187ap06_O_ci`）返回 HTTP 302 → `https://www.tpex.org.tw/errors`
- **原因確認:** Cloudflare Challenge Page 保護（IP 172.65.90.66/67 均為 CF IP）
- **測試記錄 (2026-07-10):**
  - ✅ Swagger JSON 可下載
  - ❌ 所有財務報表端點 302 redirect 到 `/errors`
  - ❌ 加上 Referer/User-Agent 仍被擋
  - ❌ 直接呼叫相對路徑（`/mopsfin_t187ap06_O_ci`）返回 404 HTML
- **結論:** TPEX OpenAPI **完全不可用**，上櫃股票財報應改用 Yahoo Finance

## 5. TDCC OpenAPI（股權分散/統計 — 非財報來源）

- **Base URL:** `https://openapi-t.tdcc.com.tw`
- **認證:** 免認證
- **Swagger:** `/tdcc-opendata-api-docs`
- **端點數量:** 135 個
- **資料類別:** 股務資訊(1-x)、權益證券統計(2-x)、境外基金(3-x)、境外結構型商品(4-x)、期信基金(5-x)、股東e票通(6-x)
- **關鍵發現:** **不提供台股財務報表（損益表/負債表/現金流量表）**
- **適用場景:** 股權分散表(1-5)、ETF月分析(2-41)、保管異動(2-22) 等獨家統計資料
- **完整端點列表:** 參閱本次調查生成的完整報告

## 6. yfinance Library（不建議作為主要來源）

- **限制:** 台股財報資料大多缺失，僅價格資料可用
- **注意:** 與 Yahoo Finance API 不同，yfinance library 對台股財報支援有限
- **建議:** 僅作為補充，不建議整合為主要來源

## 最終策略（2026-07-10 起）

```
┌─────────────────────────────────────────────┐
│         資料來源策略                        │
├─────────────────────────────────────────────┤
│ 主力: Yahoo Finance（完整三表，免認證）      │
│ 備援: FinMind（quota 有限）                  │
│ 補充: TWSE OpenAPI（上市行情/外資/融資）     │
│ 補充: TDCC（股權分散/ETF統計，非財報）       │
│ 待定: TPEX（Cloudflare 問題待解決）          │
└─────────────────────────────────────────────┘
```

## 資料缺口分析

| 資料類型 | Yahoo | FinMind | TWSE | TPEX | TDCC | 備註 |
|----------|-------|---------|------|------|------|------|
| 損益表 | ✅ | ✅ | ✅ | ❌ | ❌ | 上市可用 TWSE |
| 負債表 | ✅ | ✅ | ✅ | ❌ | ❌ | 上市可用 TWSE |
| 現金流量表 | ✅ | ✅ | ❌ | ❌ | ❌ | Yahoo/FinMind |
| 上櫃財報 | ✅ | ✅ | ❌ | ❌ | ❌ | TPEX API 不可用 |
| 興櫃資料 | ✅ | ❌ | ❌ | ✅ | ❌ | 無可靠來源 |
| 歷史行情 | ✅ | ✅ | ✅ | ✅ | ❌ | 四來源皆可 |
| 股權分散 | ❌ | ❌ | ❌ | ❌ | ✅ | **TDCC 獨有** |
| ETF 分析 | ❌ | ✅ | ✅ | ✅ | ✅ | 多來源 |