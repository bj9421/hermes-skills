# fix_incomplete_v3.py — 回補缺失交易日資料

## Problem
`fix_incomplete_v3.py` 原本有兩個致命設定導致回補失敗：
1. `MAX_RUNTIME = 540`（9 分鐘）— 但 7/17 缺了 777 檔，每分鐘只能抓 ~40 檔 → 需要 ~20 分鐘
2. `per_minute = 40` — 實際測試發現 twstock API 回應極慢（~2.7 秒/檔），遠超速率限制

## Symptoms
- Cron job `補完股票缺失資料` (每週一至五 18:00) 每次跑完都回報 "Need more passes"
- 7/17 從 1,142 筆只增加到 ~1,391 筆，然後因超時中斷
- 連續執行多次都卡在同樣的缺口

## Root Cause
`twstock.Stock.fetch_from()` 每次呼叫都要：
1. Rate limiter wait (0.5-1s)
2. TWSE/TPEX API 回應 (1-2s，有時更久)
3. DB commit
總計 ~2.7 秒/檔。以 40 rpm = 1.5 秒間隔，API 回應本身就超了 → 實際速率被 API 拖慢。

## Fix (applied 2026-07-18)
```python
# Before:
MAX_RUNTIME = 540
# RateLimiter init: per_minute=40

# After:
MAX_RUNTIME = 3600  # 1 hour — enough for 700+ stocks at ~2.7s/stock
# RateLimiter init: per_minute=60  # modest increase, still safe
```

## Verification After Fix
- 第 1 次執行 (540s): 1,142 → 1,391 (補 249 檔)
- 第 2 次執行 (540s): 1,391 → 1,592 (補 201 檔)
- 第 3 次執行 (3600s, 修正後): 1,592 → **1,918/1,925** (補 326 檔)
- 剩餘 7 檔缺：1589, 1591, 3426, 4804, 4987, 5236, 6806 — 疑似新上市/下市或 API 無法取得

## Future Prevention
1. 每次修補後檢查是否還有缺口 — 不要只相信 "ALL DATES COMPLETE" 就結束
2. 如果 `fix_incomplete_v3.py` 返回 exit code 1，表示還有缺口，應手動再跑
3. 建議將 `MAX_RUNTIME` 設為 3600s 以上，`per_minute` 設為 60
4. 7 檔持續缺的，可手動查詢 twstock API 是否真的無法取得
