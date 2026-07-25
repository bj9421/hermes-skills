# Design It Twice — 設計兩次

當使用者想探索替代介面時，使用這個平行 sub-agent 模式。基於 Ousterhout 的 "Design It Twice" — 第一個想法通常不是最好的。

使用 SKILL.md 的詞彙 — **module**, **interface**, **seam**, **adapter**, **leverage**。

## 流程

### 1. 定義問題空間

在 spawn sub-agent 之前，先寫一段使用者導向的問題空間說明：

- 任何新介面都需要滿足的約束
- 依賴的分類（見 [DEEPENING.md](DEEPENING.md)）
- 粗略的程式碼 sketch 讓約束具體化 — 不是提案，只是具體化約束

給使用者看，然後立刻進入 Step 2。使用者在 sub-agent 平行工作時閱讀和思考。

### 2. Spawn Sub-agents

用 `delegate_task` 平行 spawn 3+ sub-agents。每個必須產出**截然不同**的介面設計。

每個 sub-agent 給不同的設計約束：

- **Agent 1：** 「最小化介面 — 目標 1-3 個進入點。最大化每個進入點的 leverage。」
- **Agent 2：** 「最大化彈性 — 支援多種使用場景和擴展。」
- **Agent 3：** 「優化最常見的呼叫端 — 讓預設案例超簡單。」
- **Agent 4（如適用）：** 「圍繞 ports & adapters 設計跨接縫依賴。」

每個 sub-agent 輸出：

1. **介面**（型別、方法、參數 + 不變式、順序、錯誤模式）
2. **使用範例** — 呼叫端怎麼用
3. **實作隱藏了什麼** — 接縫背後是什麼
4. **依賴策略和 adapters**（見 DEEPENING.md）
5. **Trade-offs** — leverage 高的地方、薄弱的地方

### 3. 呈現和比較

按順序呈現設計讓使用者吸收，然後散文式比較。對比維度：

- **深度** — 介面的 leverage
- **局部性** — 變更集中在哪裡
- **接縫位置** — 接縫放在哪裡

比較後給你的推薦：哪個設計最強、為什麼。如果不同設計的元素可以組合，提出混合方案。要有觀點 — 使用者要的是強烈的判斷，不是選單。

---

*Ported from [mattpocock/skills](https://github.com/mattpocock/skills) — `DESIGN-IT-TWICE.md` (MIT License)*
