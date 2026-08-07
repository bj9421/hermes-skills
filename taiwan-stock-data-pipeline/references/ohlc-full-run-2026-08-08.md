# OHLC 全量比對 — 2026-08-08 執行（2026-08-07 交易日）

> 執行者：cron（類似 `ohlc-verification-full` 週六 02:00 排程的 prompt）
> 完整協定見 `ohlc-verify-protocol.md`；本次為第 5 次 FULL 全量比對。

## 執行紀錄

**原始 prompt 指令：**
```bash
cd /opt/data/projects/taiwan-stock-cashflow-api && /opt/data/.venv/bin/python3 -u screening/verify_daily_prices.py --full --all-dates 2>&1 | tail -30
```

**⚠️ 失敗：** `--all-dates` 不是合法參數 → `error: unrecognized arguments: --all-dates`。
腳本 argparse 只有 `--full`（`parser.add_argument("--full", ...)`，第 158 行）。
比對日期固定為 `get_yesterday()`，**無法指定其他日期** — 所以 prompt 的 `--all-dates` 是無效旗標。

**實際執行（成功）：**
```bash
cd /opt/data/projects/taiwan-stock-cashflow-api && PATH=/opt/data/.venv/bin:$PATH python -u screening/verify_daily_prices.py --full
```
- PATH 前綴形式未觸發 cron lifecycle guard（與 skill 既有指引一致）。
- 背景執行：cron 一次性 session 無 `notify_on_complete`（回 unsupported）；`process wait` 被 clamp 到 60s。
- 輪詢迴圈：`for i in $(seq 1 10); do kill -0 <wrapperPID> || echo DONE; sleep 55; done`
- 卡死偵測：`ps -eo pid,etime,time,%cpu,cmd | grep verify_daily_prices` → bash wrapper（1931, 0% CPU）vs python child（1935, 25.5% CPU 有在動）= 正常。
- 總耗時約 80 分鐘（含 1.2s/檔 sleep，1925 檔）。

## 結果

| 項目 | 數值 |
|------|------|
| Sampled | 1925 |
| Matched | 1889 (98.1%) |
| Mismatched | 29 |
| Errors | 7 |
| **實際價格偏差** | **0**（連續第 5 次 FULL 全量維持 100% 準確率） |

reason breakdown：`missing_data: 29, api_fetch_failed: 7`，`deviation*: 0`。

## Mismatched 29 支分類

SQL：`SELECT close FROM daily_prices WHERE stock_code=? AND date='2026-08-07'`（連 `/opt/data/taiwan_stocks.db`，注意專案目錄內是 symlink）

- **28 支 close=null（有 row）**：1538, 2035, 2712, 2941, 3064, 3067, 3158, 4183, 4806, 5348, 5703, 5878, 5906, 6236, 6242, 6512, 6680, 6708, 6843, 6856, 6904, 7747, 7782, 8066, 8077, 8101, 8342, 8917 — 暫停交易/低流動性，非異常
- **1 支 no_row（DB 無 08-07 紀錄）**：**5236 凌陽** — 管線遺漏，與 07-28 全量為同一支，**連續第二次**被標記。建議下次增量更新排程時確認是否補入。

## Errors 7 支（api_fetch_failed，皆已下市/停止交易）

1589, 3426, 4130, 4804, 4987, 5904, 6806
- **5904 為新面孔**（yfinance 回報 `$5904.TW: possibly delisted`）— 歷史基線（07-25/07-28）無此支。
- 6806 也回報 `possibly delisted`（歷史已知已下市股）。

## 結論

無需處理的資料異常。缺口穩定在 ~1.5% 且全為暫停交易股（資料完整性問題，非準確性問題）。
唯一持續追蹤項：**5236 凌陽連續兩次全量被標記為管線遺漏**。
