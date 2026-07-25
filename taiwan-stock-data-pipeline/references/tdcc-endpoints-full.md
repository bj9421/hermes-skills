# TDCC OpenAPI 完整端點列表

> 調查日期: 2026-07-10  
> Base URL: `https://openapi-t.tdcc.com.tw`  
> Swagger: `/tdcc-opendata-api-docs`  
> **結論: 不提供台股財務報表**

---

## 端點總覽（135 個）

### 股務資訊（15 個）
| 端點 | 功能 |
|------|------|
| `/v1/opendata/1-1` | 證券基本資料 |
| `/v1/opendata/1-5` | 集保戶股權分散表 |
| `/v1/opendata/2-41` | 集中保管ETF月分析表 |
| `/v1/opendata/2-22` | 上市股票異動月分析表 |

### 權益證券統計（24 個）
`/v1/opendata/2-1` ~ `/v1/opendata/2-44` — 保管統計、異動分析、ETF/TDR 月分析

### 固定收益統計（13 個）
`/v1/opendata/2-11` ~ `/v1/opendata/2-38` — 票券/國庫券/TAIBIR 利率報價

### TAIBIR 資訊（7 個）
`/v1/opendata/2-15` ~ `/v1/opendata/2-21` — 初級/次級利率報價

### 境外基金（28 個）
`/v1/opendata/3-1` ~ `/v1/opendata/3-31` — 基金基本資料/淨值/配息/銷售機構

### 境外結構型商品（29 個）
`/v1/opendata/4-1` ~ `/v1/opendata/4-29` — 商品總覽/參考價格/配息/銷售統計

### 期信基金（16 個）
`/v1/opendata/5-1` ~ `/v1/opendata/5-16` — 期貨信託基金資料

### 股東 e 票通（3 個）
`/v1/opendata/6-1` ~ `/v1/opendata/6-3` — 電子投票資訊

---

## 特色端點（適合整合的）

| 端點 | 用途 | 資料量 |
|------|------|--------|
| `/v1/opendata/1-5` | 集保戶股權分散表 | 68,017 筆 |
| `/v1/opendata/2-41` | ETF 月分析表 | 347 筆 |
| `/v1/opendata/2-22` | 上市股票保管異動 | 1,349 筆 |

## 調查方法

```bash
# 取得 Swagger spec
curl -s "https://openapi-t.tdcc.com.tw/tdcc-opendata-api-docs" | python3 -c "
import sys, json
spec = json.load(sys.stdin)
for path in spec.get('paths', {}):
    print(path)
"
```

## 關鍵結論

- TDCC **不提供** 台股財務報表（損益表/負債表/現金流量表）
- 主要提供：基金資料、股權分散、保管統計
- 與 Yahoo Finance / FinMind / TWSE OpenAPI 互補，不替代