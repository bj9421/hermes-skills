---
name: grill-me
description: "需求追問（Grilling Session）：在動手前，agent 反覆追問使用者關於 plan/decision/idea 的每個面向，直到雙方達成共識。Use when: 開始新專案前、設計新功能前、做重要決策前、或使用者說'幫我想想/幫我分析'。"
version: 1.1.0
author: Hermes Agent (ported from mattpocock/skills)
license: MIT
platforms: [linux, macos, windows]
tags: [requirements, alignment, interview, planning, socratic]
related_skills: [grilling, brainstorming, writing-plans, codebase-design, grill-with-docs]
---

# Grill Me — 需求追問入口

> **這是 wrapper skill。** 核心訪談邏輯在 `grilling` primitive。本 skill 只負責觸發。

## 觸發條件

- 使用者描述一個新功能、專案、或設計想法
- 使用者說「幫我想想」「幫我分析」「我有個 idea」
- 使用者要求做重要技術决策
- `brainstorming` skill 需要更深度的需求挖掘時

## 執行

載入 `grilling` skill 並執行訪談。無文件輸出，只有對話中的理解對齊。

## 適用場景

快速對齊、小決策、不需要留下永久紀錄的訪談。

## 與 grill-with-docs 的差異

| | grill-me | grill-with-docs |
|---|---|---|
| 文件輸出 | ❌ | ✅ ADR + 詞彙表 |
| 適用 | 快速對齊 | 需要留下決策紀錄 |

## 原始出處

Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `grill-me` + `grilling` skills (MIT License)。
