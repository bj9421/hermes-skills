# NotebookLM 式多來源合成 — 可行性評估與決策（2026-08-05）

> 使用者需求：多個來源連結 → 產出一份詳細內容 → 後續可用口播 / PPT / 圖卡。
> 狀態：**決策已定，Phase 1（批次輸出選項）+ Phase 2（合成）程式碼完成 🔨，端到端待實測**。

## 結論：可行性高（非從零開發）

現有 notehub pipeline 已具備 80% 零件，缺的核心只有「多來源合併 + 合成 prompt」。

| 零件 | 現況 | 重用？ |
|------|------|--------|
| 多種來源 extractor | YouTube / 網頁 URL / PDF / 文字檔（`detect_source()` + `extractors/`）| ✅ 直接重用 |
| 三種輸出 | 口播（podcast.py）、PPT（ppt_gen.py）、圖卡（visual_gen.py）| ✅ 直接重用 |
| LLM fallback 鏈 | Zen → AGNES → Groq（`core/llm.py`）| ✅ 直接重用 |
| 長文分塊 | `_chunk_text()` | ✅ 直接重用 |
| **多來源合成** | `run_pipeline(source, ...)` 只吃單一 source | 🆕 已新增 `core/synthesis.py` |

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
- 按鈕：「🚀 開始批次（逐一產生）」= 現有行為（每筆各自產出）；「🧬 開始合併」= 合成（Phase 5 已啟用）
- **關閉按鈕已移除**，統一右上 ✕

Phase 1 實作（bookmark-manager）：
- `notehub_jobs` 表加 `ppt INTEGER DEFAULT 0` / `visual INTEGER DEFAULT 0`（schema.sql + db.py init_db PRAGMA migration）
- `create_notehub_jobs()` 接受 ppt/visual
- queue API：items 接受 `ppt`/`visual`，驗證至少選一種（全排除 → 400 + excluded）
- `_process_job()`：job 有 ppt/visual → CLI 加 `--ppt` / `--visual`（對應 notehub `__main__.py` 的 flags）
- 前端：表頭/row 加 PPT/圖卡 cell、submitNotehubQueue 收集 + 驗證、submitNotehubSynthesis（Phase 5 已啟用）
- 測試：tests/test_notehub_outputs.py 4 筆（ppt/visual 儲存、只 PPT 不口播、未選輸出排除、舊行為相容）

### 🔴 mode='none' 語意（2026-08-05 Phase 5 新增）

Phase 4 隱藏 bug：**只勾 PPT/圖卡（沒勾口播）時 mode 仍設 'solo' → worker 組 `--podcast solo` → 多產口播**。修法：queue/synthesize API 判定沒勾口播 → `mode='none'`（dual > solo > none），`_process_job` 兩分支處理 none（不加 --podcast）。

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

## 🧬 Phase 5 實作細節（2026-08-05 程式碼完成）

**notehub 端（skills repo，commit skills）**：
- `notehub/core/synthesis.py`：
  - `synthesize_sources(sources, lang='zh', title_hint='')` → `(out_dir, report_path, title)`
  - `_summarize_source(text, title)`：單來源 LLM 摘要（>20000 chars 分塊，每塊 2048 tokens）
  - `_synthesize(combined, lang)`：SYNTHESIS_PROMPT 合成（>24000 chars 分塊，末塊補【整體結論】）
  - 輸出：`obsidian-vault/notes/<safe_title> [synthesis-YYYYMMDD]/synthesis_report.md`（YAML frontmatter 含 sources 清單）+ SQLite index（source_type='synthesis'）
- `__main__.py` `--synthesize` 分支：`python -m notehub --synthesize <url1> <url2> ... [--podcast solo|dual] [--ppt] [--visual] [--lang zh] [--voice-a 台女] [--voice-b 台男]` — 需 ≥2 來源；階段二輸出重用 `produce_podcast` / `generate_ppt` / `generate_visual`
- ⚠️ **`generate_ppt(script, title, lang='zh', out_dir='.')` 參數順序陷阱**：第 3 位置參數是 lang 不是 out_dir — 呼叫要 `generate_ppt(report_content, title, lang=lang, out_dir=out_dir)`，傳位置參數會把 out_dir 當 lang（檔案寫錯位置）

**bookmark-manager 端（commit「Phase 5 多來源合成」）**：
- `notehub_jobs` 表加 `kind TEXT DEFAULT 'single'` / `source_urls TEXT DEFAULT ''`（JSON 陣列；migration 慣例同 ppt/visual）
- `create_synthesis_job(conn, bookmark_ids, title, source_urls, mode, voice_a, voice_b, ppt, visual)` → 回 job_id
- `POST /api/notehub/synthesize` body `{ids, voice_a, voice_b, ppt, visual}`：≥2 筆 + 至少一輸出 → 查書籤 URL → 標題 = 前兩筆 title + 「等 N 筆（合成）」→ 建 job → `_ensure_worker()`
- worker `_process_job` kind='synthesis' 分支：`json.loads(source_urls)` → `['--synthesize'] + urls` + mode 對應 flags（dual/solo → --podcast；none → 不加）
- 前端 `submitNotehubSynthesis()`：selectedIds ≥2 → 輸出選項**取第一筆勾選**（合成 = 一份內容）→ POST → toast → switchNhTab('queue') + pollNotehubJobs
- 測試：`tests/test_synthesize_api.py` 5 筆 → **117 tests 全綠**

**⏳ 待辦**：端到端實測（CLI 真合成 2-3 來源 → 報告 .md）需網路請求 + 使用者同意（approval gate 擋離線 terminal 網路指令）；手機端合併實測。

## ⚠️ 已知限制（設計時納入）

1. **來源數建議 3-5 個** — 每支影片逐字稿可能數萬字，太多來源超過 LLM 處理上限（有分塊但合成品質稀釋）
2. **免費層大請求慢** — Zen 對複雜合成回應慢（90s timeout 已調），複雜合成建議**兩階段**：先各來源摘要 → 再綜合
3. **bookmark-manager 整合**（第二層）：書籤勾選多筆 → 送合成 job，估 1-2 天
