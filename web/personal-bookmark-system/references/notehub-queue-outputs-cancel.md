# Notehub 佇列：輸出選項 + 取消機制（2026-08-05）

## 佇列表格輸出選項（批次）
- 表格欄位：`# | 工作名稱 | 口播(台女/台男) | PPT | 圖卡` — 全部 checkbox
- 口播：☑台女 / ☑台男，同勾 = 雙人模式（dual）
- PPT / 圖卡：各一個 checkbox，對應 notehub CLI `--ppt` / `--visual`
- 送出驗證：每筆**至少選一種輸出**（前端 toast 提醒 + 後端排除 reason='未選輸出'，全被排除回 400）
- job 表欄位：`ppt INTEGER DEFAULT 0`、`visual INTEGER DEFAULT 0`（db.py init_db ALTER TABLE migration）
- `create_notehub_jobs()` 接受 ppt/visual → `_process_job()` 依旗標組 CLI args

## 🔴 清佇列 = 清 queued + 取消 running（關鍵教訓）
**問題**：worker `_worker_loop` 每 2 秒 poll pending → `claim_notehub_job()`（原子 UPDATE WHERE status='queued'）→ job 送出後 3 秒內變 running。只清 queued 讓使用者「送出即變 running → 永遠清不掉」。

**修復**：
1. `_running_proc = {}` 全域 dict（worker 單執行緒，同時最多一個）— `_process_job` 改 Popen 存入，`communicate(timeout=1500)` 後 `finally pop`
2. clear scope='queued' 擴展：SELECT queued+running → running 的 job 從 `_running_proc` 找 Popen → `proc.kill()` + `proc.wait(timeout=10)` → 防「取消了還繼續產出檔案」
3. **DELETE 必須按 id 集合刪**（`WHERE id IN (...)`），不能用 status 條件！
   - 原因（競態）：subprocess 被 kill 後 worker 立刻 `update_notehub_job_status(conn, id, 'failed')` → job 變 failed → `DELETE WHERE status IN ('queued','running')` 漏掉 → 殘留 failed
4. API 回傳 `cancelled` 計數，前端 toast 顯示「（N 個處理中已取消）」

## 清佇列按鈕位置（頁籤版面教訓）
- 清佇列按鈕**必須放在工作佇列頁籤層級**（nh-tab-queue 內、nh-setup 外、nh-active-hint 上方）
- 曾誤放 nh-setup（勾選畫面）→ 沒勾選書籤時 nh-setup 隱藏 → 按鈕消失 → 使用者「功能失效」
- 完成工作頁籤的「關閉」按鈕已移除，統一右上 ✕（openNotehubSidebar 顯示）

## 驗證
- tests/test_clear_queued.py（4 個）：queued+running 一起清、不刪檔案、bad scope 400、running subprocess kill（假 Popen = sleep 60）
- tests/test_notehub_outputs.py（4 個）：ppt/visual 儲存、只 PPT 不口播、未選輸出排除、舊行為相容
- 端到端：送 job → 3 秒變 running → clear → `{"cancelled":1,"count":1}` → 確認無殘留
