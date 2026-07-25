---
name: codebase-design
description: "模組設計紀律：設計或重構模組時，追求「小介面 + 大行為」的深度模組。Use when: 設計新模組、重構現有 code、決定接縫位置、提升可測試性、或需要模組設計詞彙表。"
version: 1.0.0
author: Hermes Agent (ported from mattpocock/skills)
license: MIT
platforms: [linux, macos, windows]
tags: [design, architecture, modules, interfaces, seams, testability]
related_skills: [brainstorming, simplify-code, improve-codebase-architecture]
---

# Codebase Design — 深度模組設計

> **核心理念：** 好的模組 = 小介面 + 大行為。使用者學很少的東西就能用，維護者改一個地方就修好所有地方，測試者透過介面就能驗證。

## 何時觸發

- 設計新模組、新 API、新介面
- 重構現有 code，想提升可測試性
- 決定模組之間的接縫（seam）在哪裡
- 需要統一的設計詞彙表
- 其他 skill 需要深度模組詞彙時

## 核心詞彙

> ⚠️ 用這些詞，不要替換。一致的語言是重點。

| 詞 | 定義 | 避免用 |
|---|---|---|
| **Module（模組）** | 有介面和實作的任何東西 — 函式、class、package、跨層級的切片 | unit, component, service |
| **Interface（介面）** | 使用者必須知道的一切：型別簽名、不變式、順序約束、錯誤模式、設定需求、效能特性 | API, signature（太窄） |
| **Implementation（實作）** | 模組內部的程式碼 | — |
| **Depth（深度）** | 介面的 leverage：使用者每學一個介面單位，能觸發多少行為 | — |
| **Seam（接縫）** | 介面存在的位置 — 可以在不改該處的情況下改變行為 | boundary（與 DDD 混淆） |
| **Adapter（適配器）** | 在接縫處滿足介面的具體實作 | — |
| **Leverage（槓桿）** | 介面的回報：學一次介面，N 個呼叫端 + M 個測試都受益 | — |
| **Locality（局部性）** | 變更、bug、知識集中在一個地方，不散落各處 | — |

## 深度 vs 淺薄

### 深度模組 ✅（追求）

```
┌─────────────────────┐
│   Small Interface   │  ← 少少的方法，簡單的參數
├─────────────────────┤
│                     │
│  Deep Implementation│  ← 複雜邏輯藏在裡面
│                     │
└─────────────────────┘
```

### 淺薄模組 ❌（避免）

```
┌─────────────────────────────────┐
│       Large Interface           │  ← 很多方法，複雜參數
├─────────────────────────────────┤
│  Thin Implementation            │  ← 只是 pass through
└─────────────────────────────────┘
```

### 設計介面時問自己

1. 能不能減少方法數量？
2. 能不能簡化參數？
3. 能不能把更多複雜度藏在裡面？

## 四個設計原則

1. **深度是介面的屬性，不是實作的屬性。** 深度模組內部可以是小的、可 mock 的、可替換的元件 — 只要它們不在介面上。

2. **刪除測試。** 想像刪掉這個模組：如果複雜度消失了，它是 pass-through；如果複雜度出現在 N 個呼叫端，它值得存在。

3. **介面就是測試面。** 使用者和測試走同一個接縫。如果你想測「穿過」介面，模組形狀可能不對。

4. **一個適配器 = 假設的接縫。兩個適配器 = 真實的接縫。** 不要有真實變化就不引入接縫。

## 可測試性設計

1. **接受依賴，不要建立依賴。**
   ```python
   # ✅ 可測試
   def process_order(order, payment_gateway):
       ...

   # ❌ 難測試
   def process_order(order):
       gateway = StripeGateway()  # 硬編碼
   ```

2. **回傳結果，不要產生副作用。**
   ```python
   # ✅ 可測試
   def calculate_discount(cart) -> Discount:
       ...

   # ❌ 難測試
   def apply_discount(cart) -> None:
       cart.total -= discount  # 改外部狀態
   ```

3. **小表面積。** 方法越少 = 測試越少。參數越少 = setup 越簡單。

## 模組關係圖

```
Module ──has──→ Interface（唯一的）
                    │
                  measured by → Depth（深度）
                    │
                  lives at → Seam（接縫）
                    │
              satisfied by → Adapter（適配器）
                    │
              produces → Leverage（對使用者）+ Locality（對維護者）
```

## 實作步驟

### 當你要設計一個新模組

1. **定義介面** — 使用者需要知道什麼才能正確使用？
2. **檢查深度** — 介面夠小嗎？行為夠多嗎？
3. **找接縫** — 介面放在哪裡最乾淨？
4. **設計依賴** — 依賴接受進來，不要自己建立
5. **驗證可測試性** — 透過介面能測到所有行為嗎？

### 當你要重構一個淺薄模組

1. **分類依賴** — 见 [references/DEEPENING.md](references/DEEPENING.md)
2. **找真正的接縫** — 兩個以上適配器才是真實接縫
3. **深化** — 縮小介面、增加行為
4. **替換測試** — 舊的單元測試在新介面測試存在後就刪除

## 進階：Design It Twice

> 第一個想法通常不是最好的。

想探索替代介面？見 [references/DESIGN-IT-TWICE.md](references/DESIGN-IT-TWICE.md) — 用平行 sub-agent 設計多種截然不同的介面，然後比較深度、局部性和接縫位置。

## 何時不用

- 只是改 bug，不涉及設計（用 `systematic-debugging`）
- 一行修改、config 調整
- 使用者說「不用想太多，直接改」

## 原始出處

Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `codebase-design` skill (MIT License).
