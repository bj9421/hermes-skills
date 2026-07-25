# OHLC 交叉比對驗證 — `verify_daily_prices.py`

## Overview

驗證工具，用外部 API（twstock → yfinance fallback）交叉比對 `daily_prices` 資料庫中的 OHLC 價格，確保資料正確性。

**路徑：** `screening/verify_daily_prices.py`（在 taiwan-stock-cashflow-api 專案中）
**DB：** `/opt/data/taiwan_stocks.db`
**輸出：** `screening/output/ohlc_verification_latest.json` + `ohlc_verify_report.txt`

## Modes & Timing

| Mode | Flag | 抽樣數 | Sleep/筆 | 總時間 | 適用情境 |
|------|------|--------|----------|--------|----------|
| **Sampled**（預設） | 無 | 80 支 | 1.2s | ~2 分鐘 | 每日 cron 快速檢查 |
| **Full** | `--full` | 1,925 支 | 1.2s | ~38 分鐘 | 手動深度驗證 |

> ⚠️ **`--all-dates` 不存在。** 僅支援 `-h` 與 `--full` 兩個旗標。

Full mode 不適合 cron（會吃 38 分鐘＋大量 API 請求）。預設抽樣 80 支即可涵蓋交易時段、跨類股。

## 資料來源先後順序

1. **twstock**（TWSE/TPEX 官方 API）— 首選
2. **yfinance**（Yahoo Finance）— twstock 回 null 時啟用
3. 兩者都失敗 → `reason: "api_fetch_failed"`

## 結果判讀

### 比對邏輯
- `compare_prices()` 用**比例偏差 ≤ 1%** 為標準
- DB close vs API close 比對
- 偏差率公式：`abs(DB - API) / API`

### 結果分類

| Reason | 意義 | 是否須關注 |
|--------|------|-----------|
| `match` | 價格一致 (≤1%) | ✅ 正常 |
| `missing_data` | **DB 中該股該日無資料** | ⚠️ 若比例偏高，檢查 pipeline 是否跑完 |
| `api_fetch_failed` | twstock 與 yfinance 都失敗 | ⚠️ 少數屬網路波動，多數需查 stock code |
| `deviation_xx%` | 價格偏差超過 1% | 🔴 **重要 — 需人工審視** |
| `api_zero` | API 回傳 0 | 極少見，暫不致命 |

### 實戰經驗

- **所有 mismatch 幾乎都是 `missing_data`**（DB 尚未完整匯入），不是真正的價格偏差。
- 正常交易日 DB 覆蓋量：~1,918–1,919 支（全部 ~1,925 支）。
- 若抽樣中 `missing_data` 超過 10% 或 API 覆蓋 vs DB 覆蓋量級差大，應檢查 `daily_prices` 管線是否正常完成該日匯入。

## 使用方式

```bash
# 預設抽樣（80 支，快速檢查）
cd /opt/data/projects/taiwan-stock-cashflow-api
.venv/bin/python3 -u screening/verify_daily_prices.py

# 全量檢查（1,925 支，～38 分鐘）
.venv/bin/python3 -u screening/verify_daily_prices.py --full
```

## 輸出範例

```json
{
  "date": "2026-07-17",
  "mode": "SAMPLE",
  "total_sampled": 80,
  "matched": 48,
  "mismatched": 31,
  "errors": 1,
  "details": [
    { "stock_code": "9907", "db_close": null, "api_close": 15.1,
      "matched": false, "reason": "missing_data" }
  ]
}
```

文字報告輸出至 `screening/output/ohlc_verify_report.txt`：
```
📊 OHLC 交叉比對 (全量檢查) - 2026-07-16
✅ 一致: 1899/1925
❌ 不一致: 21 支
⚠️ API 失敗: 5 支
```
