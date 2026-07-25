# 增量更新設計模式 (Two-Tier Incremental Update)

## Overview

`update_daily.py` 使用兩層效率機制來確保每日盤後更新能在 cron timeout (2400s) 內完成：

```
Tier 1: Today-data Filter (pre-loop)
  └─ 查 DB 中已有今日資料的股票 → 直接從 code_list 移除
  └─ 效果：盤後執行時只需補 ~600-800 檔缺漏股

Tier 2: Checkpoint Resume (mid-batch)
  └─ 每 50 檔寫一次 checkpoint JSON
  └─ 效果：若 timeout 提前發生，下次執行可接續
```

**跨日重置**：shell script (`run_daily_incremental_update.sh`) 每天 16:00 先 `rm -f update_checkpoint.json`，確保當日從頭開始。Tier 1 是主要效率來源，Tier 2 是安全網。

## 為何不用 checkpoint 跨日

早期版本讓 checkpoint 跨日累積（每天只補剩餘的股票），但遇到以下問題：
1. checkpoint 跨日可能因前一日中途失敗卡住
2. 當日無新資料時，腳本秒退（`remaining=0`），跳過技術指標更新
3. 無法區分「今天已經補過了」vs「前天說補完了但昨天有新資料」

**解法**：每日重置 checkpoint，讓 today-data filter 從 DB 動態判斷哪些股票需要更新。

## 執行流程 (16:00 cron)

```
16:00 → shell script start
  │
  ├─ rm -f checkpoint.json         ← 每日重置
  │
  ├─ update_daily.py start
  │   ├─ SELECT DISTINCT stock_code FROM daily_prices WHERE date = today
  │   │   → 若有資料，從 code_list 移除（Tier 1）
  │   ├─ remaining = 1925 - already_have ≈ 600-800
  │   ├─ todo = remaining[:800]
  │   ├─ for each code: fetch_from(今年, 本月) → INSERT
  │   └─ every 50: checkpoint write（Tier 2）
  │
  ├─ (if timeout 2400s → next cron tick resumes via checkpoint)
  │
  └─ update_all_tech_indicators.py (timeout 600s)
```

## 時間估算

| 階段 | 數量 | 單檔時間 | 總時間 |
|------|------|---------|--------|
| today-data filter (SQL) | 1 | ~0.1s | ~0.1s |
| 抓取 800 檔 | 800 | ~1.5s | ~20 分 |
| checkpoint write (每 50 檔) | 16 次 | ~0.01s | ~0.2s |
| 技術指標更新 | 1925 檔 | ~0.006s | ~12s |
| **總計** | | | **~21 分** |

安全裕度：2400s timeout ≈ 40 分，21 分實際執行 ≈ 52% 利用率。

## BATCH_SIZE 調整歷史

| 日期 | 值 | 原因 |
|------|-----|------|
| ~2026-07 | 2000 | 原始值，無 today-data filter → 需掃全部 1925 檔，但超過 2400s timeout |
| 2026-07-15 | 800 | 加上 today-data filter 後，盤後只需補 ~600-800 檔，800 剛好 cover |

調整原則：`BATCH_SIZE` 應略大於「盤後缺漏股數」的典型峰值（目前約 600-800），讓多數時候一輪跑完，少數極端情況靠 checkpoint 續傳。

## --force 用法

```bash
# 僅在手動回補或驗證時使用
.venv/bin/python3 update_daily.py --force
```

`--force` 跳過 today-data filter + checkpoint，強制重新抓取全部股票。cron 不使用 `--force`。

## 失敗復原

### 情境 A：update_daily.py 在 2400s timeout（最常見）

下次 cron 執行時（下一分鐘或隔天）：
1. shell script 重置 checkpoint
2. today-data filter 查到已有部分今日資料
3. 只補剩餘的股票

### 情境 B：技術指標更新超時（timeout 600s）

不會影響股價資料。下次 cron 會重新跑技術指標。

### 情境 C：twstock API 全面失靈

症狀：大量 `Failed to resolve 'www.tpex.org.tw'` 或 `api_fetch_failed`。
處理：等上游恢復後重新手動 `--force`。
注意：2026-07-10 事件中 twstock 曾全面失靈導致 OHLC 比對 0/80 一致。
