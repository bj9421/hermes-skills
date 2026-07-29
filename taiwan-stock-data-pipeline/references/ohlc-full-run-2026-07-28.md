# OHLC 全量比對 — 2026-07-28（週二）

## 執行記錄

| 項目 | 內容 |
|------|------|
| **執行時間** | 2026-07-29 16:44 ~ 約 18:00（~76 min） |
| **目標日期** | 2026-07-28（週二） |
| **模式** | `--full` 全量 1,925 檔 |
| **執行背景** | Hermes cron job（`scheduled cron job`）/ 背景 process polling |
| **腳本** | `screening/verify_daily_prices.py` |

## 執行過程

### 首次嘗試 — foreground timeout
```bash
# 前景執行（timeout=300s）→ 在約 50/1925 處超時
cd /opt/data/projects/taiwan-stock-cashflow-api && \
  /opt/data/.venv/bin/python3 -u screening/verify_daily_prices.py --full 2>&1 | tail -30
# → exit_code=124, 耗時 300s 時僅完成 ~50 檔
```

### 改用背景 + polling
```bash
# 背景執行（stdout 導向檔案）
cd /opt/data/projects/taiwan-stock-cashflow-api && \
  /opt/data/.venv/bin/python3 -u screening/verify_daily_prices.py --full \
  > /tmp/ohlc_full_run.log 2>&1 &

# 定期檢查進度
tail -1 /tmp/ohlc_full_run.log        # 每 5 分鐘查看一次
sleep 300 && tail -1 /tmp/ohlc_full_run.log
```

**進度取樣：**
| 時間點 | 進度 | 經過時間 |
|--------|------|----------|
| 首次讀取 | 50/1925 | ~2 min |
| +2 min | 100/1925 | ~4 min |
| +5 min | 150/1925 | ~9 min |
| +5 min | 200/1925 | ~14 min |
| +5 min | 250/1925 | ~19 min |
| +5 min | 300/1925 | ~24 min |
| +5 min | 400/1925 | ~29 min |
| +5 min | 500/1925 | ~34 min |
| +5 min | 600/1925 | ~39 min |
| +5 min | 700/1925 | ~44 min |
| +5 min | 800/1925 | ~49 min |
| +5 min | 1000/1925 | ~54 min |
| +5 min | 1100/1925 | ~59 min |
| +5 min | 1200/1925 | ~64 min |
| +5 min | 1300/1925 | ~69 min |
| +5 min | 1550/1925 | ~74 min |
| - | 1900/1925 + Summary | ~76 min |

**估算速率：** ~25 檔/min（含 1.2s sleep + API 回應時間），推估 1,925 檔約需 **77 分鐘**。

### 過程中觀察到的 API 錯誤

| 股票 | 錯誤訊息 |
|------|---------|
| 3426 | `HTTP 404: Quote not found for symbol 3426.TW` → 已下市 |
| 4130 | `HTTP 404: Quote not found for symbol 4130.TW` → 已下市 |
| 4804 | `possibly delisted; no timezone found` |
| 4987 | `possibly delisted; no timezone found` |
| 6806 | `possibly delisted; no price data found` |

## 結果

```
Sampled:    1925
Matched:    1890 (98.2%)  ✅
Mismatched: 30   (1.6%)   ❌  → 全部為 missing_data
Errors:      5   (0.3%)   ⚠️  → 已下市股
Deviation>1%: 0           (無實際價格偏差)
```

### Mismatch 詳情分類

| 類型 | 筆數 | 代碼 | 說明 |
|------|------|------|------|
| **both_missing** (DB+API 皆 null) | 27 | `1213,2035,2924,2937,2941,3064,3067,3085,3115,3226,4183,4192,4198,4305,5703,5906,6236,6527,6597,6624,6692,6708,6881,6997,8087,8272,8444` | 正常：無交易或已下市 |
| **db_only_missing** (DB null, yfinance 有值) | 2 | `1459 (15.8), 1589 (5.54)` | 已下市/暫停交易，yfinance 殘值 |
| **db_only_missing** (DB null, yfinance 有完整 OHLC) | 1 | `5236 (143.5)` | 凌陽 — 可能有真實資料缺口 |
| **api_fetch_failed** (雙來源皆失敗) | 5 | `3426,4130,4804,4987,6806` | 已下市，screen_cache 雜訊 |

## 一致性趨勢（跨次 FULL 比較）

| 執行日期 | 目標日期 | Matched | Mismatched | Errors | Dev>1% |
|----------|----------|---------|------------|--------|--------|
| 07-17 | 07-16 | 1,899 (98.65%) | 21 | 5 | **0** |
| 07-24 | 07-23 | 1,891 (98.2%) | 29 | 5 | **0** |
| 07-25 | 07-24 | 1,891 (98.2%) | 29 | 5 | **0** |
| **07-29** | **07-28** | **1,890 (98.2%)** | **30** | **5** | **0** |

## 關鍵洞察

1. **零實際偏差已是穩定常態。** 連續 4 次 FULL 比對（07-16, 07-23, 07-24, 07-28）皆出現 `Deviation>1%: 0`，`daily_prices` 的價格品質可靠。
2. **Mismatch 數量微幅波動（21→29→29→30）** 來自 `both_missing` 的新增/減少，不是真正的價格問題。
3. **已下市股固定 5 支（3426, 4130, 4804, 4987, 6806）** 反覆貢獻 `api_fetch_failed`，可考慮從 screen_cache 清理以減少噪音。
4. **FULL 模式執行耗時穩定在 ~38-77 分鐘**，視 twstock API 延遲而異。SAMPLE 模式（80 檔, ~3 min）即可偵測大規模異常。

## 執行技術筆記

### Foreground 超時問題
`--full` 模式需要 38~77 分鐘，前景 terminal(timeout=300s) 甚至 max=600s 都不夠。若在 cron job 中執行：
- **不建議前景直接跑** — 一定超時
- **背景跑 + 定期讀取 log 檔** — 可監控進度
- **或只用 SAMPLE 模式（80 檔, ~3 min）** — 日常檢查足夠

### 背景執行模式
```bash
# 啟動
python3 -u script.py --full > /tmp/run.log 2>&1 &

# 監控（每 5 分鐘）
tail -3 /tmp/run.log

# 讀取最終結果
cat /tmp/run.log | tail -15
```

### 速率
- 每 5 分鐘推進 50-60 檔
- 包含 1.2s `time.sleep` + twstock/yfinance API 回應時間
- 推測瓶頸在 sleep（1,925 × 1.2s = 38.5 min 為下限）
