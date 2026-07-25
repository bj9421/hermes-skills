---
name: grill-with-docs
description: "需求追問 + 自動產出決策紀錄（ADR + 詞彙表）。訪談過程中同步建立永久紀錄，讓決策有據可查。Use when: 重要技術決策需要留下紀錄、新專案架構設計、多團隊協作需要 shared context。"
version: 1.0.0
author: Hermes Agent (ported from mattpocock/skills)
license: MIT
platforms: [linux, macos, windows]
tags: [requirements, alignment, interview, planning, socratic, adr, documentation]
related_skills: [grilling, grill-me, brainstorming, writing-plans, codebase-design]
---

# Grill With Docs — 需求追問 + 決策紀錄

> **這是 wrapper skill。** 核心訪談邏輯在 `grilling` primitive。本 skill 加上文件輸出能力。

## 觸發條件

- 重要技術決策需要留下永久紀錄
- 新專案架構設計
- 多團隊協作需要 shared context
- 使用者說「把決策記下來」「留個紀錄」

## 執行

載入 `grilling` skill 並執行訪談。在訪談過程中**同步建立**以下文件：

### 1. CONTEXT.md — 領域詞彙表

訪談中每當一個術語被精確定義，**即時更新** `CONTEXT.md`：

```markdown
# [專案名] 領域詞彙表

> 最後更新：YYYY-MM-DD

| 術語 | 定義 | 備註 |
|------|------|------|
| [術語] | [精確定義] | [相關決策連結] |
```

**規則：**
- 純詞彙表，不含實作細節
- 術語與既有詞彙矛盾時 → 立刻指出
- 模糊用語 → 提出精確替代詞
- 即時更新，不要累積後批次寫入

### 2. ADR — Architecture Decision Record

只有在以下**三個條件都滿足**時才建立 ADR：

1. **難以逆轉** — 以後改主意成本很高
2. **沒有上下文會令人困惑** — 未來讀者會問「為什麼這樣做？」
3. **真正的權衡** — 有 genuine alternatives，不是唯一選擇

缺一個都不寫。

**ADR 格式：**

```markdown
# ADR-NNNN: [決策標題]

## 狀態
[提議 | 採納 | 已棄用 | 已取代]

## 背景
[為什麼需要做這個決定？]

## 決策
[我們決定採用 X，原因是 Y]

## 考量的替代方案
- 方案 A — [優缺點]
- 方案 B — [優缺點]

## 後果
[這個決定帶來什麼影響？]
```

**存放位置：** `docs/adr/` 目錄，檔名格式 `ADR-NNNN-標題.md`

### 3. 訪談結束時的確認

```
✅ 我們已達成共識。確認的事項：

1. [目標] — [確認內容]
2. [範圍] — [確認內容]
3. [技術方案] — [確認內容]
...

📄 已建立的文件：
- CONTEXT.md — [N] 個術語
- ADR-NNNN — [決策標題]
- ...

要我開始動手嗎？還是有需要調整的地方？
```

## 適用場景

需要留下永久紀錄的訪談：新專案、重要架構決策、多團隊協作。

## 與 grill-me 的差異

| | grill-me | grill-with-docs |
|---|---|---|
| 文件輸出 | ❌ | ✅ ADR + CONTEXT.md |
| 適用 | 快速對齊 | 需要留下決策紀錄 |
| 輸出物 | 對話中的理解 | CONTEXT.md + ADR + 對話 |

## 原始出處

Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `grill-with-docs` + `domain-modeling` skills (MIT License)。
