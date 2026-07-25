---
name: twse-openapi-integration
description: >-
  整合 TWSE OpenAPI 作為 FinMind 備援資料來源。
  免認證、無 quota 限制，適用於損益表+資產負債表。
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [twse, openapi, financial-statements, backup-source]
    related_skills: [taiwan-stock-data-pipeline, ai-stock-screener]
---

# TWSE OpenAPI Integration

## Overview

TWSE OpenAPI (`https://openapi.twse.com.tw/v1`) 是免認證的免費資料來源，
涵蓋 143 個端點，可用於上市股票財報/行情/外資資料。

**關鍵優勢：** 免認證、無 quota 限制、無封鎖風險 → 適合大規模批次請求。

## 關鍵端點

### 財報資料（已驗證可用）

| 端點 | 用途 | 驗證 | 狀態 |
|------|------|------|------|
| `t187ap03_L` | 上市公司基本資料（市值、產業別、股數） | ✅ | 可用 |
| `t187ap06_L_ci` | 綜合損益表（一般業） | ✅ | 可用（JSON） |
| `t187ap07_L_ci` | 資產負債表（一般業） | ✅ | 可用（JSON） |

### 財報資料（不可用）

| 端點 | 用途 | 狀態 |
|------|------|------|
| `t187ap08_L_ci` | 現金流量表（一般業） | ❌ 302 redirect |
| `t187ap09_L_ci` | 綜合損益表（含非控制權益） | ❌ 302 redirect |
| `t187ap05_L_ci` | 財務報表（彙總） | ❌ 302 redirect |

## 呼叫範例

```bash
# 損益表
curl "https://openapi.twse.com.tw/v1/api/data/t187ap06_L_ci?selectType=all&response=json"

# 資產負債表
curl "https://openapi.twse.com.tw/v1/api/data/t187ap07_L_ci?selectType=all&response=json"

# 基本資料（含市值）
curl "https://openapi.twse.com.tw/v1/api/data/t187ap03_L?selectType=all&response=json"
```

## 回應格式

### 損益表（t187ap06_L_ci）

```json
[
  {
    "出表日期": "1150710",
    "年度": "115",
    "季別": "1",
    "公司代號": "1101",
    "公司名稱": "台泥",
    "營業收入": "33168148.00",
    "營業成本": "26959758.00",
    "營業毛利": "6208390.00",
    "營業費用": "3416199.00",
    ...
  }
]
```

### 資產負債表（t187ap07_L_ci）

```json
[
  {
    "出表日期": "1150710",
    "年度": "115",
    "季別": "1",
    "公司代號": "1101",
    "公司名稱": "台泥",
    "流動資產": "184722314.00",
    "非流動資產": "412892972.00",
    "資產總額": "597615286.00",
    "流動負債": "82516661.00",
    "負債總額": "292869670.00",
    "股本": "77231817.00",
    "資本公積": "74917132.00",
    "保留盈餘": "60971176.00",
    ...
  }
]
```

## 混合策略（2026-07-10 更新）

### Yahoo Finance 成為主力備援（2026-07-10 新增）

**發現：** Yahoo Finance (`yfinance` Python lib) 提供完整的損益表、資產負債表、現金流量表。
- ✅ 損益表：Total Revenue, Operating Income, Net Income, Gross Profit, EPS...
- ✅ 資產負債表：Total Assets, Current Assets, Total Liabilities, Retained Earnings...
- ✅ 現金流量表：Operating Cash Flow, Free Cash Flow, Capital Expenditure...
- ✅ 免認證、無 quota 限制、無封鎖風險
- ✅ 涵蓋上市 + 上櫃（用 `.TW` 後綴）

**新策略：**
```
┌─────────────────────────────────────────────┐
│         優先級資料來源策略                      │
├─────────────────────────────────────────────┤
│ 1. FinMind（付費版）→ 主力                  │
│ 2. Yahoo Finance → 全資料來源備援            │
│ 3. TWSE OpenAPI → 僅損益表+負債表備援        │
│ 4. TPEX → 不可用（Cloudflare）               │
└─────────────────────────────────────────────┘
```

**實作步驟：**
1. `financial_analyzers.py` 的 `IncomeAnalyzer` / `BalanceAnalyzer` → 優先用 Yahoo Finance，fallback 到 TWSE OpenAPI
2. `cashflow_analyzer.py` → 改用 Yahoo Finance（不再依賴 FinMind）
3. 完全免除 FinMind quota 限制

## 注意事項

- 僅涵蓋上市股票（約 870-1089 檔），不含上櫃/興櫃
- 現金流量表端點 302 redirect → 不可用
- 無 rate limit 限制 → 可安全大規模請求
- 建議批次請求間加 0.1s 延遲以避免伺服器壓力

## 資料來源比較（2026-07-10 更新）

| 來源 | 損益表 | 負債表 | 現金流量表 | 認證 | Quota | 備註 |
|------|--------|--------|------------|------|-------|------|
| FinMind | ✅ | ✅ | ✅ | 需要 | 有限（402） | 原主力，quota 耗盡 |
| Yahoo Finance | ✅ | ✅ | ✅ | 免 | 無 | **最佳備援，全覆蓋** |
| TWSE OpenAPI | ✅ | ✅ | ❌ 302 | 免 | 無 | 僅損益+負債 |
| TDCC OpenAPI | ❌ | ❌ | ❌ | 免 | 無 | **不提供財報**，僅境外基金/統計 |
| TPEX OpenAPI | ❌ | ❌ | ❌ | 免 | — | Cloudflare 封鎖 |

### TDCC OpenAPI 調查結果（2026-07-10）
- 網址：`https://openapi-t.tdcc.com.tw/swagger-ui/index.html`
- Swagger spec：`/tdcc-opendata-api-docs`
- 所有端點分類：股務資訊(1-x)、權益證券統計(2-x)、境外基金(3-x)、境外結構型商品(4-x)、期信基金(5-x)、股東e票通(6-x)
- **結論：TDCC 不提供台股財報資料，無法取代 FinMind**
- 詳情見 `references/tdcc-api-investigation.md`