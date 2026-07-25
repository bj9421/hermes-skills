---
name: handoff
description: "Session 交接文件：把當前對話壓縮成交接文件，讓下一個 session 或另一個 agent 能直接接續工作。Use when: session 即將結束、專案跨多個 session、或使用者說'先停在這裡/下次再繼續'。"
version: 1.0.0
author: Hermes Agent (ported from mattpocock/skills)
license: MIT
platforms: [linux, macos, windows]
tags: [handoff, continuity, session-management, documentation]
related_skills: [grill-me, writing-plans, obsidian]
---

# Handoff — Session 交接文件

> **核心理念：** Multi-session 專案最大的痛點是「上次做到哪裡了？」。Handoff 把當前上下文壓縮成結構化文件，下次 session 讀一次就能接續，不用重新說明。

## 何時觸發

- 對話已很長，即將結束
- 專案跨多個 session（大型功能、多步驟任務）
- 使用者說「先停在這裡」「下次再繼續」「先到這」
- 使用者要求把工作交接給另一個 agent

## 執行流程

```
1. 掃描當前對話，提取關鍵資訊
   ↓
2. 檢查已產出的 artifacts（spec、plan、commit、文件）
   ↓
3. 生成交接文件
   ↓
4. 存到 ~/handoffs/YYYY-MM-DD-<topic>.md
   ↓
5. 回報文件路徑給使用者
```

## 交接文件格式

```markdown
# Handoff: [專案/任務名稱]
- **日期：** YYYY-MM-DD HH:MM
- **Session：** [簡述這個 session 做了什麼]

## 📋 當前狀態
[用 1-3 句話描述目前進度]

## ✅ 已完成
- [完成的事項 1]
- [完成的事項 2]

## 🔲 待辦（下次繼續）
- [ ] [待辦事項 1 — 明確描述下一步動作]
- [ ] [待辦事項 2]

## 🧩 關鍵決策
- [決策 1]：[理由]
- [決策 2]：[理由]

## 📁 相關文件
- Spec：`[路徑或 URL]`
- Plan：`[路徑或 URL]`
- Code：`[路徑或 URL]`
- 其他：`[路徑或 URL]`

## ⚠️ 注意事項
- [踩過的坑、已知問題、需要特別注意的地方]

## 🔗 建議載入的 Skills
- `skill-name-1` — [為什麼需要]
- `skill-name-2` — [為什麼需要]

## 💬 使用者偏好/指令
- [使用者明確說過的偏好或限制]
```

## 生成規則

### 必須包含
1. **當前狀態** — 一句話總結
2. **已完成 vs 待辦** — 明確切分
3. **下一步動作** — 待辦事項要夠具體，下一個 agent 不用猜
4. **相關文件路徑** — 不複製內容，引用路徑或 URL

### 不要包含
1. **敏感資訊** — API key、密碼、個資 → 自動遮蔽或省略
2. **重複的 artifacts** — 已經在 spec/plan/commit 裡的內容 → 引用路徑就好
3. **對話流水帳** — 不需要逐句紀錄，只要提取決策和結果

### 語言
- 跟隨使用者的語言（中文/英文）
- 保持簡潔，每個 section 3-5 點為主

## 下次 Session 如何使用

在新 session 開始時：

```
請讀取 ~/handoffs/YYYY-MM-DD-<topic>.md 並接續上次的工作。
```

或直接：
```
@handoff 讀取上次的交接文件
```

Agent 會：
1. 讀取交接文件
2. 載入建議的 skills
3. 根據「待辦」清單繼續工作
4. 不重複已完成的事項

## 存放位置

預設：`~/handoffs/`（即 `/opt/data/handoffs/`）

目錄結構：
```
~/handoffs/
├── 2026-07-25-17uu-hotels-feature.md
├── 2026-07-24-stock-dashboard-refactor.md
└── ...
```

## 注意事項

- **不要在交接文件裡寫執行緒** — 下一個 agent 不需要知道你問了幾個問題
- **待辦事項要 actionable** — 「繼續做 dashboard」❌ →「在 dashboard.py 加上 /api/summary endpoint」✅
- **敏感資料自動過濾** — 看到 key/token/password 就遮蔽
- **一個專案一個文件** — 不要混在一起

## 原始出處

Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `handoff` skill (MIT License).
