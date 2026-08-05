# NotebookLM 式多來源合成 — 可行性評估（2026-08-05）

> 使用者需求：多個來源連結 → 產出一份詳細內容 → 後續可用口播 / PPT / 圖卡。
> 狀態：**設計評估，尚未開工**。本文是可行性結論 + 架構藍圖，不是已驗證流程。

## 結論：可行性高（非從零開發）

現有 notehub pipeline 已具備 80% 零件，缺的核心只有「多來源合併 + 合成 prompt」。

| 零件 | 現況 | 重用？ |
|------|------|--------|
| 多種來源 extractor | YouTube / 網頁 URL / PDF / 文字檔（`detect_source()` + `extractors/`）| ✅ 直接重用 |
| 三種輸出 | 口播（podcast.py）、PPT（ppt_gen.py）、圖卡（visual_gen.py）| ✅ 直接重用 |
| LLM fallback 鏈 | Zen → AGNES → Groq（`core/llm.py`）| ✅ 直接重用 |
| 長文分塊 | `_chunk_text()` | ✅ 直接重用 |
| **多來源合成** | `run_pipeline(source, ...)` 只吃單一 source | 🆕 唯一新寫 |

## 架構藍圖

```
輸入：多個來源（3-5 個，YouTube/網頁/PDF/文字混合）+ 主題名稱（可選）

流程：
1. 逐個 extract（重用現有 extractors，各來源 raw 文字標註來源）
2. 合併所有文字
3. LLM 合成一份詳細內容（🆕 SYNTHESIS_PROMPT）：
   ├── 共通主題
   ├── 各來源獨特觀點
   ├── 差異/衝突處
   └── 整體結論
4. 後續輸出（任選）：詳細報告 .md / 口播腳本→MP3 / PPT / 圖卡
```

新增程式碼估 2-3 天（多來源收集 + synthesis prompt）。

## ⚠️ 已知限制（設計時納入）

1. **來源數建議 3-5 個** — 每支影片逐字稿可能數萬字，太多來源超過 LLM 處理上限（有分塊但合成品質稀釋）
2. **免費層大請求慢** — Zen 對複雜合成回應慢（90s timeout 已調），複雜合成建議**兩階段**：先各來源摘要 → 再綜合
3. **bookmark-manager 整合**（可選第二層）：書籤勾選多筆 → 送合成 job，估 1-2 天

## 待使用者決策（開工前問）

1. 輸入來源：純「多支 YouTube 影片」？還是「影片+網頁+PDF 混合」？
2. 輸出：先產詳細報告再決定口播/PPT/圖卡？還是全自動？
3. 入口：從 bookmark-manager 勾選送？獨立 CLI？網頁貼 URL 清單？
