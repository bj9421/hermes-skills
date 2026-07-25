---
name: grilling
description: "Interview the user relentlessly about a plan, decision, or idea until every branch of the decision tree is resolved. Core primitive used by grill-me and grill-with-docs."
version: 1.0.0
author: Hermes Agent (ported from mattpocock/skills)
license: MIT
platforms: [linux, macos, windows]
tags: [interview, alignment, planning, socratic, primitive]
related_skills: [grill-me, grill-with-docs, brainstorming, writing-plans, codebase-design]
---

# Grilling — 蘇格拉底式訪談原語

> **核心理念：** 大多數 AI coding agent 的失敗來自 Alignment — 使用者以為 agent 理解了，但其實沒有。Grilling 透過結構化追問，在動手前把所有不確定性逼出來。

## 這是什麼

`grilling` 是**可組合的訪談原語** — 其他 skill 可以直接叫它，不用自己重寫訪談邏輯。它只做一件事：用蘇格拉底式追問把隱藏假設逼出來。

- **不產出文件** — 只有對話中的理解對齊
- **不急著動手** — 等到明確確認才結束
- **可被任何 skill 調用** — ha-powers Phase 0、brainstorming 前置、獨立使用

## 執行流程

```
┌─────────────────────────────────────────┐
│  1. 請使用者描述想法/目標                    │
│  ↓                                       │
│  2. 先查環境（檔案、工具、歷史）               │
│     → 能查到的事自己查，不要問                 │
│  ↓                                       │
│  3. 一次只問一個問題                         │
│     → 每個問題附帶你的建議答案                 │
│  ↓                                       │
│  4. 等使用者回答後再問下一個                   │
│     → 不要一次問多個，會讓人混亂                │
│  ↓                                       │
│  5. 決策樹每個分支都走到                      │
│     → 解決決策之間的依賴關係                   │
│  ↓                                       │
│  6. 確認「我們已達成共識」                     │
│     → 明確列出已確認的事項                     │
│  ↓                                       │
│  7. 使用者確認後才行動                       │
└─────────────────────────────────────────┘
```

## 追問策略

### 分類 Fact vs Decision

每次收到使用者的回答，先判斷：

- **Fact（事實）** → 可以透過探索環境（檔案、程式碼、文件）驗證 → **自己查，不要問**
- **Decision（決策）** → 取決於使用者偏好、業務邏輯、優先順序 → **問使用者，等回答**

### 問題類型（依序追問，依情境跳過不適用的）

1. **目標** — 你真正想解決什麼問題？
2. **範圍** — 哪些要做、哪些不做？
3. **約束** — 時間、平台、效能、預算限制？
4. **成功標準** — 「完成」長什麼樣子？
5. **替代方案** — 考慮過哪些其他做法？為什麼不選？
6. **風險** — 最可能出錯的是什麼？
7. **整合** — 跟現有系統怎麼接？影響哪些既有功能？

### 每個問題的格式

```
**Q: [問題]**

建議：[你的推薦答案 + 一句話理由]

A: 
```

## 決策樹行走

- 每個決策都是一個分支，先走父決策再走子決策
- 前面的回答可能改變後面的問題走向
- 發現矛盾 → 立刻指出，不要等到最後
- 不確定的分支 → 問；已確定的分支 → 跳過

## 結束條件

當以下全部滿足時，明確宣告：

```
✅ 我們已達成共識。確認的事項：

1. [目標] — [確認內容]
2. [範圍] — [確認內容]
3. [技術方案] — [確認內容]
...

要我開始動手嗎？還是有需要調整的地方？
```

## 鐵律

- **一次只問一個問題** — 絕對不要打破
- **不要假設** — 不確定就問
- **不要急著動手** — 等到明確的「可以開始」才做
- **跟隨使用者語言** — 中文或英文
- **遇到矛盾要指出** — 回答之間有衝突立刻提出

## 與其他 skill 的差異

| | grilling (原語) | brainstorming | writing-plans |
|---|---|---|---|
| 範圍 | 專注在需求對齊 | 研究現有方案 + 產出 spec | 分解成可執行任務 |
| 輸出 | 共識清單（對話中） | 正式 design spec 文件 | 實作計畫 |
| 觸發 | 模型可自動或用戶手動 | 用戶手動 | 用戶手動 |
| 適用 | 快速對齊、小決策、任何 skill 前置 | 新專案完整設計流程 | spec 確認後 |

## 原始出處

Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `grilling` skill (MIT License)。結合原版極簡哲學與結構化追問流程。
