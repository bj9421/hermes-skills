---
name: hermes-debug-protocol
description: "整合 systematic-debugging + debug-agent 的統一 8 步除錯 SOP。遇到任何 bug 自動觸發，強制根因調查才能修復。"
version: 1.0.0
author: Hermes_Pi (整合自 systematic-debugging v1.1.0 + millionco/debug-agent)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [debugging, root-cause, instrumentation, ndjson, hypothesis, systematic]
    related_skills: [systematic-debugging, debug-agent, test-driven-development]
---

# Hermes 綜合除錯協議

## 觸發條件
遇到任何 bug / 測試失敗 / 異常行為 / 生產事故 → 自動載入此流程，**不跳過、不例外**。

## 🔴 鐵律
```
沒有根因調查，不准修復。
```

## 8 步流程

### Step 0：觸發
載入 `systematic-debugging` + `debug-agent` skill。

### Step 1：Read — 讀懂錯誤訊息
- 完整讀 stack trace、error code、行號
- `read_file` 讀相關源碼，`search_files` 搜 error string
- **不做任何修改**

### Step 2：Loop — 建立 Tight Feedback Loop
- 寫一條指令能重現使用者的症狀
- 要求：快速、deterministic、只在 bug 存在時 fail
- 建立優先順序：failing test → curl/CLI → browser script → replay trace → git bisect
- **Loop 紅了（fail）才能進下一步**

### Step 3：Hypothesize — 產生 3–5 個假設
- 排序：最可能 + 最容易驗證的先排
- 每個假設寫：「如果是 X，觀察 Y 應該看到 Z」
- 使用者在線 → 先展示列表讓使用者排

### Step 4：Instrument — 插 NDLOG 樁
- 結構化日誌，每個 log 對應至少一個假設
- 標記 `hypothesisId`、`location`、`data`
- 用 `#region debug log` / `#endregion` 包起來
- 典型 2–6 個 log，不超過 10 個
- **Python**: append NDJSON 到 log 檔案
- **JS/TS**: fetch POST 到 debug server endpoint
- **禁止**記錄 secrets / tokens / PII

### Step 5：Reproduce — 收集日誌
- 清空 log 檔案 → 執行重現指令 → 等完成
- 讀 NDLOG，逐假設判定：
  - ✅ CONFIRMED — log 證據支持
  - ❌ REJECTED — log 反駁
  - ❓ INCONCLUSIVE — 需要更多插樁

### Step 6：Fix — 100% 確信才修
- 只保留 CONFIRMED 假設的修復
- 撤銷 REJECTED 的程式碼變更
- 一次只改一個東西
- **日誌樁留著不删**

### Step 7：Verify — Before/After 對比
- 同一條 Loop 指令重跑
- 比對修復前後日誌，引用具體 log line
- 使用者確認無誤才算成功

### Step 8：Cleanup — 清理 + 報告
- grep `#region debug log` → 全部刪除
- `git diff` 確認只剩修復
- 寫 5W1H 除錯報告

## 🚨 停下來的紅旗（任一觸發 → 回到 Step 1）
- 「先試試看再說」
- 「應該是 X，直接改」
- 修了 2 次以上還沒好 → **停！質疑架構**
- 修一個地方冒出新問題 → **架構層級問題，找使用者討論**
- 不理解但覺得「可能有用」→ **不准動**
- 3+ 次修復失敗 → 質疑整體架構設計

## 重複失敗處理
| 修復次數 | 動作 |
|---------|------|
| 1–2 次 | 回到 Phase 1，帶新資訊重新分析 |
| 3 次 | **停止**，質疑架構，與使用者討論 |
| 3+ 次 | 不再嘗試修復，要求架構層級 re-design |

## 效果對比
| 指標 | 跟流程 | 亂猜 |
|------|--------|------|
| 修復時間 | 15–30 min | 2–3 hr |
| 首次成功率 | 95% | 40% |
| 引入新 bug | 近零 | 常見 |

## 整合工具
- `read_file` / `search_files` — 讀源碼、搜 error string
- `terminal` — 跑 Loop、git bisect、pytest
- `delegate_task` — 複雜多元件除錯時，派 subagent 調查
- `web_search` / `web_extract` — 查 error 訊息、文件
