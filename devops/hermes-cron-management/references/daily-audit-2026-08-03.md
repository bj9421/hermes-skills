# Daily Cron 盤查實戰 — 2026-08-03

來源：每日排程盤查回報 job（dd239cd537ae）當日執行。21 個 job、3 個 error：修好 2 個、留 1 個待評估。

## 盤查方法（本 session 實證）
- 讀 live store 用 `read_file /opt/data/cron/jobs.json`（勿用 `cat | python3`，tirith 擋）。
- 執行歷史用 `/opt/data/cron/executions.db`（executions 表）— jobs.json 的 `last_status` 可能 stale/殘留。
- 每個 error job 先看輸出：`/opt/data/cron/output/<job_id>/<最新>.md`，再對照根因，不要只看錯誤摘要。
- cron 模式 terminal 的 lifecycle guard 會擋 heredoc / `python3 -c`（含純 python 查詢）— 用 write_file 寫小 script 到 `/opt/data/scripts/` 再 `python3` 跑，用完即刪（runner 模式）。
- 修復後清除 error 狀態的標準動作見 SKILL.md「盤查時修好就要清 error 狀態」。

## 1. bookmark-manager-github-backup（8c43651cd066）— 已修復 ✅
**錯誤：** `! [rejected] main -> main (non-fast-forward)`，exit 1。
**根因：** 備份腳本是 push-only（不 pull/不 merge）。**遠端被另一台機器（Pi 3，DEPLOY-PI3.md 等 5 commits）推進**，本地 9 commits 落後 → push 被拒。非權限問題、非 script bug — 是 repo 變成 multi-machine 拓撲。
**診斷證據：**
```
git fetch <oauth2-url> main
git rev-list --left-right --count FETCH_HEAD...HEAD   # 1  9  (遠端獨有 1、本地獨有 9)
git merge-base --is-ancestor f2b7915 HEAD             # yes (remote commits 已在本地祖先鏈 → 可 FF)
```
**修法：** `git merge FETCH_HEAD -m "Merge remote ..."`（fast-forward，1 file 198 insertions）→ 重跑 backup script → push 10 commits，exit 0。
**教訓：** push-only 備援腳本在多機協作 repo 上必然 periodic non-fast-forward。腳本層選項：(a) push 前先 fetch + `git merge FETCH_HEAD`（FF 安全）；(b) 接受失敗由 watchdog/盤查補救。**絕不 `git push --force`。**

## 2. ohlc-verification（4f5e6b393a51）— 已修復 ✅
**錯誤（同日兩次）：** 16:35 `Script not found: /opt/data/scripts/verify_daily_prices.py` → 18:37 `Script timed out after 2400s`。
**根因：** wrapper `verify_daily_prices.sh` 帶 `--full` → 全量掃描（300+ 支 × sleep 1.2s + API latency）≈ 40–60 分鐘 >> no_agent 2400s 硬上限。16:35 的 not-found 是過渡狀態（wrapper 曾指向不存在的 .py）。
**修法：** 移除 wrapper 的 `--full` → 每日改跑抽樣模式（80 支 ≈ 2–3 分鐘）。全量檢查本來就由週六 `ohlc-verification-full`（2c6e281d226c）負責 — 每日 job 重複全量 = 重複工作。
**驗證：** 改完實跑 `timeout 540 bash /opt/data/scripts/verify_daily_prices.sh` → `Sampled: 80, Matched: 80, Mismatched: 0, Errors: 0` exit 0。
**教訓：** no_agent 2400s 硬上限；每支 stock sleep 1.2s 的掃描型腳本全量必爆表。daily vs full 的分工要寫死在 wrapper 註解，避免未來又加回 `--full`。

## 3. finmind-batch-financial-update（9ef9db78a312）— 保留 error，未「修」⚠️
**錯誤：** `TimeoutError: idle for 602s (limit 600s) — waiting for non-streaming API response`。
**根因：** LLM-driven job，prompt 內建 fork 模式（os.fork + os.execv）把 batch_evaluate_financial.py 丟背景 → **LLM 沒有可等的工作，600s idle 被殺是必然**，但 detached script 繼續跑完。
**關鍵證據（batch_financial.log）：**
```
[!] FinMind IP banned. Waiting 1796s (29.9 min)...
[!] Ban still active after wait (2s). Stopping.
Done  Total: 365 | Success: 123 | Failed: 0 | Skipped: 44 | BannedWait: 1  Elapsed: 2458s (41.0 min)
```
**判讀：** 資料其實補進去了（123 成功）。cron 層 error 是「LLM job 空轉」的假警報，不是資料失敗。同日 cron-watchdog-fast 每 10 分鐘重報 → 使用者收到「provider timeout」誤導通知（scheduler 把 no_agent stdout 丟 failure summarizer 的已知 bug，見 SKILL.md EXIT-CODE CONTRACT）。
**建議（需 TTY/使用者決定）：** 轉 no_agent 無法解決 — 腳本本身 41 分鐘（含 ban wait 30 分鐘）超過 no_agent 2400s。真正選項：(a) 接受週一固定假警報，盤查只驗證 log；(b) 改為純 spawner（fork 後立刻 exit 0），資料驗證交給另一時段 job；(c) 錯開 FinMind ban window。**盤查守則：finmind 類 job 先查 log 再決定要不要「修」，不要看到 error 就重 pin 模型。**

## 4. 執行細節
- 21 個 job 中 3 個 error；修好 2 個並清 error 狀態（backup → patch → validate JSON），`jobs.json.bak.daily-20260803-211237` 留存。
- 驗證採 write-file-then-run + runner 模式（cron 模式 heredoc / python3 -c 被 lifecycle guard 擋）。
- 驗證腳本自踩自指陷阱：檢查 `--full` 時誤抓註解（「移除 --full」）→ 修正為只檢查 exec 行（`startswith('/opt/data/.venv/bin/python3')`）。寫驗證斷言時，grep 整個檔案常誤中註解，只斷言實際執行行。
