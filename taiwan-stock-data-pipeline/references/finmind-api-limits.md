# FinMind API 限制與封鎖防護（官方文件引文 + 實測 2026-07-11）

## 官方限制（finmind.github.io → BanIPPolicy / api_usage_count / StressTest）

### 配額（Free / level 1）
- `api_request_limit`（每日）：**600**
- `api_request_limit_hour`（每小時）：600
- 查詢方式：`GET https://api.web.finmindtrade.com/v2/user_info`
  - Header：`Authorization: Bearer <token>`
  - 回傳欄位：`user_count`、`api_request_limit`、`api_request_limit_hour`、`level`、`level_title`
- 超額回應：`402 {"msg":"Requests reach the upper limit. https://finmindtrade.com/","status":402}`

### 封鎖（IP Ban）
- 觸發：短時間內累積大量 **4xx**（無效 token、參數錯誤、**超額請求 402**）
- 被封鎖回應：
  ```json
  {"msg":"ip banned","status":403}
  ```
  ⚠️ **注意：body 沒有 `retry_after` 欄位**（舊文件/我們程式碼都誤以為有）
- 封鎖時長：**30 分鐘**後自動解除，無需人工介入
- 若解除後**仍持續發送大量無效請求（含 4xx）會再次被封鎖** → 死循環
- 官方建議：
  - `TokenIllegal`(400) / `TokenLevelTooLow` → 停止用該 token 重試，重登取得新 token
  - 4xx 是請求本身的問題，**不要無限 retry**；5xx 才用 exponential backoff 但限制次數
  - 速率參考壓力測試：colab ~10 req/s（36k/hr），linode(日本) ~50 req/s（180k/hr）
    → 保守建議 **≤ 8s/req 單執行緒**，避免突發

### 壓力測試建議速率（StressTest 頁）
- colab：10 併發 1000 req，均值 10 req/s，平均回應 72ms
- linode(日本)：10 併發 1000 req，均值 50 req/s，平均回應 17ms

## 實測（2026-07-11，RPi4 實際 token = bj9421@gmail.com / Free）
- `user_count=0`，`api_request_limit=600`，`api_request_limit_hour=600`，`level_title=Free`
- 無 token 直接打 `api/v4/data` → 200（公開端點可免 token 讀；但建議一律帶 token 以利配額識別）
- **我們程式被 ban 的真正原因（非 FinMind 問題）：**
  1. 單支股票 burst ~7 次 FinMind（income+balance+cashflow 各 1 + ROE 重抓 income+balance + 股息+股價）
  2. 541 支 backlog × 7 ≈ 3800 次 >> 600/天 → ~2.4 分鐘刷爆 → 402 → 觸發 IP ban
  3. **Ban 偵測 bug（致命）**：程式 `body.get("retry_after", 300)` 永遠拿到 300（FinMind 根本沒這欄位）；
     `financial_analyzers` / `cashflow_analyzer` 在 403 時 `time.sleep(300)` 後回傳 None 繼續跑下一支
     → 每支又打 403、又睡 300s ×541 = 無限浪費 + 持續打 4xx 讓 IP 一直 ban（正是官方說的死循環）
  4. 快取無效：`api_cache` 是記憶體內 24h、每次執行重來；`cashflow_analyzer` 根本沒用快取
     → 週一 cron + 手動 + 每日策略 job 每次全重抓，重複燒配額
  5. **Yahoo Finance 在這台 Pi 完全壞掉**（income/balance/cashflow 對 2330/2317/2454 全回空）
     → 原本「Yahoo 優先、FinMind 備援」變 100% 走 FinMind

## 推薦防護設計（待實作）
- 單一 `screening/finmind_client.py` 給所有模組共用
- **磁碟快取**（sqlite, TTL 7 天）→ 跨執行保留，消除重複抓取
- **全域每日配額守衛**：開跑前查 `user_info`，逼近 600 就優雅停止（不硬幹 402）
- **斷路器**：偵測 `403 ip banned` → 整批立即停，等一次 30 分鐘，期間不打網路；
  絕不在每支股票各自 `sleep`
- **速率限制**：最小間隔 ~8s/req，避免突發
- 去除 income/balance 重複抓取（ROE 直接吃 analyzer 已抓的資料）
- backlog 分批：~110 支/天（含備援 ≈770 次/天），約 5 天填滿快取，之後只補增量

## 錯誤回應速查
| status | body | 意義 | 正確處理 |
|--------|------|------|---------|
| 200 | `{"msg":"success","status":200,"data":[...]}` | OK | 取 `data` |
| 402 | `{"msg":"Requests reach the upper limit...","status":402}` | 超額 | 停止本批，等下個計費週期 |
| 403 | `{"msg":"ip banned","status":403}` | IP 被封 | 整批停，等 30 分鐘，期間零網路 |
| 400 | `{"msg":"TokenIllegal"/"TokenLevelTooLow",...}` | token 無效 | 停止用該 token 重試，換新 token |
