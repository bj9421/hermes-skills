# NotebookLM 式多來源合成 — 可行性評估與決策（2026-08-05）

> 使用者需求：多個來源連結 → 產出一份詳細內容 → 後續可用口播 / PPT / 圖卡。
> 狀態：**決策已定，Phase 1（批次輸出選項）已完成上線，Phase 2（合成）開發中**。

## 結論：可行性高（非從零開發）

現有 notehub pipeline 已具備 80% 零件，缺的核心只有「多來源合併 + 合成 prompt」。

| 零件 | 現況 | 重用？ |
|------|------|--------|
| 多種來源 extractor | YouTube / 網頁 URL / PDF / 文字檔（`detect_source()` + `extractors/`）| ✅ 直接重用 |
| 三種輸出 | 口播（podcast.py）、PPT（ppt_gen.py）、圖卡（visual_gen.py）| ✅ 直接重用 |
| LLM fallback 鏈 | Zen → AGNES → Groq（`core/llm.py`）| ✅ 直接重用 |
| 長文分塊 | `_chunk_text()` | ✅ 直接重用 |
| **多來源合成** | `run_pipeline(source, ...)` 只吃單一 source | 🆕 唯一新寫 |

## ✅ 已定決策（2026-08-05 使用者確認）

1. **輸入來源：混合**（YouTube + 網頁 + PDF）— 三種 extractor 都現成，成本一樣，書籤本來就各種來源都有
2. **輸出流程：兩階段** — 先產「詳細報告 .md」→ 確認內容 OK → 再選口播/PPT/圖卡。理由：免費層大請求慢（Zen 90s timeout），一次全自動容易失敗或品質稀釋
3. **入口：bookmark-manager 勾選多筆 → 送合成 job（進現有佇列）** — 勾選 + 佇列機制已做好，整合成本最低

## 🎛️ 佇列表格輸出選項（Phase 1 已完成 2026-08-05）

使用者定案的 UI 設計（不只合成，單筆批次也適用）：

```
# | 工作名稱 | 口播(台女/台男) | PPT | 圖卡
1 | xxx      | ☑台女 ☐台男     | ☑   | ☐
```

- 口播維持 ☑台女 ☑台男（同勾 = 雙人模式）；PPT / 圖卡各一個 checkbox
- **每筆至少選一種輸出**才能送（前端 toast + 後端 excluded reason='未選輸出'）
- 按鈕：「🚀 開始批次（逐一產生）」= 現有行為（每筆各自產出）；「🧬 開始合併」= 合成（Phase 2）
- **關閉按鈕已移除**，統一右上 ✕

Phase 1 實作（bookmark-manager）：
- `notehub_jobs` 表加 `ppt INTEGER DEFAULT 0` / `visual INTEGER DEFAULT 0`（schema.sql + db.py init_db PRAGMA migration）
- `create_notehub_jobs()` 接受 ppt/visual
- queue API：items 接受 `ppt`/`visual`，驗證至少選一種（全排除 → 400 + excluded）
- `_process_job()`：job 有 ppt/visual → CLI 加 `--ppt` / `--visual`（對應 notehub `__main__.py` 的 flags）
- 前端：表頭/row 加 PPT/圖卡 cell、submitNotehubQueue 收集 + 驗證、submitNotehubSynthesis（Phase 2 完成前是 stub「開發中」提示）
- 測試：tests/test_notehub_outputs.py 4 筆（ppt/visual 儲存、只 PPT 不口播、未選輸出排除、舊行為相容）

### 🔴 清佇列按鈕位置 bug（2026-08-05 修復，UI 設計教訓）

頁籤改版時把「清佇列」按鈕放在 `#nh-setup`（勾選畫面）內 → 該區塊只有 `selectedIds.size > 0`（有勾選書籤）才 `display:block` → **沒勾選書籤時清佇列按鈕整個消失**，使用者回報「功能失效」。

**教訓：清除/操作類按鈕要放在頁籤層級（panel 直接子層），不要放在條件顯示的區塊內。** 修復：清佇列移到 `nh-tab-queue` 層級（nh-setup 外、佇列列表上方），勾不勾選都顯示。這也符合使用者原始設計「工作佇列頁面放清除佇列按鈕」。

其他相關教訓（同日）：
- `onclick` 引用的函數必須存在於全域 scope（診斷：curl 頁面 + regex 收集 onclick 函數 vs `function NAME(` 定義比對，缺失 = bug）
- 改 HTML/JS 後跑 `node --check` 驗證語法；改 sw.js CACHE 版本讓 PWA 快取更新（手機端需刷新 2 次：第 1 次裝新 sw、第 2 次切換）

## 架構藍圖（Phase 2）

```
輸入：勾選 3-5 筆書籤（混合來源）+ 選擇輸出

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

## ⚠️ 已知限制（設計時納入）

1. **來源數建議 3-5 個** — 每支影片逐字稿可能數萬字，太多來源超過 LLM 處理上限（有分塊但合成品質稀釋）
2. **免費層大請求慢** — Zen 對複雜合成回應慢（90s timeout 已調），複雜合成建議**兩階段**：先各來源摘要 → 再綜合
3. **bookmark-manager 整合**（第二層）：書籤勾選多筆 → 送合成 job，估 1-2 天
