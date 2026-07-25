# Deepening — 深化浅薄模組

如何安全地深化一簇淺薄模組，考量其依賴關係。假設已熟悉 SKILL.md 的詞彙 — **module**, **interface**, **seam**, **adapter**。

## 依賴分類

評估候選深化目標時，先分類其依賴。類別決定測試策略。

### 1. In-process（程序內）

純計算、記憶體狀態、無 I/O。**永遠可以深化** — 合併模組，直接透過新介面測試。不需要 adapter。

### 2. Local-substitutable（本地可替換）

依賴有本地測試替代品（PGLite 代替 Postgres、記憶體檔案系統）。**如果有替代品就可以深化。** 深化模組用替代品跑測試。接縫是內部的；模組外部介面上沒有 port。

### 3. Remote but owned（遠端但自有）

自己的跨網路服務（微服務、內部 API）。在接縫處定義一個 **port**（介面）。深度模組擁有邏輯；傳輸層以 **adapter** 注入。測試用記憶體 adapter。生產用 HTTP/gRPC/queue adapter。

> 建議格式：*"在接縫處定義 port，實作 HTTP adapter 用於生產、記憶體 adapter 用於測試，讓邏輯集中在一個深度模組，即使部署跨越網路。"*

### 4. True external（真實外部，Mock）

第三方服務（Stripe、Twilio 等）無法控制。深化模組以注入的 port 接受外部依賴；測試提供 mock adapter。

## 接縫紀律

- **一個適配器 = 假設的接縫。兩個適配器 = 真實的接縫。** 不要有至少兩個 adapter（通常是 production + test）就不引入 port。單一 adapter 的接縫只是間接層。
- **內部接縫 vs 外部接縫。** 深度模組可以有內部接縫（private，自己的測試用）和外部接縫（介面上的）。不要因為測試用就把內部接縫暴露到介面上。

## 測試策略：替換，不要疊加

- 舊的淺薄模組單元測試，在深化模組的介面測試存在後就變成廢物 — **刪除它們。**
- 在深化模組的介面寫新測試。**介面就是測試面。**
- 測試透過介面斷言可觀察的結果，不測內部狀態。
- 測試應該在內部重構後仍通過 — 描述行為，不描述實作。如果實作一改測試就要改，那就是在測介面之外的東西。

---

*Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `DEEPENING.md` (MIT License)*
