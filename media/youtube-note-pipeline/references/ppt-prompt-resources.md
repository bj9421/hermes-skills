# PPT 生成提示詞資源庫（2026-08-06 蒐集）

提升 notehub `ppt_gen.py` 產出質量的外部資源 + 現況診斷 + 升級建議。
使用時機：使用者問「哪裡有 PPT 提示詞 / 如何提升簡報質量」、或要改 `ppt_gen.py` 的 `_extract_key_points` prompt。

## 資源清單（anysearch 實測抓取驗證過）

### 🥇 中文（最推薦）

1. **104 職場力「投影片大綱規劃模組」** — `blog.104.com.tw/ai-presentation-outline-generation-prompt-guide/`
   - 7 步執行流程：① 依簡報時長估頁數（每 1-2 分鐘一頁）② 整合目標/受眾/資料定 **Story Line** ③ 拆 3-5 章節 ④ 每章節拆「核心訊息」當投影片標題 ⑤ **先寫完整口語講稿、再從講稿提取投影片文字**（講稿遠多於投影片文字）⑥ 依頁面類型決定文字密度/格式 ⑦ 審視串連故事線
   - 頁面類型規則：封面 / 目錄（章節≤4 用插圖、>4 用清單）/ 章節頁（半圖半文）/ **金句頁（2-3 張、無插圖、H1 大小）** / 純內文頁（Tagline 標題 ≤10 字、bullet 最多一層子階層）/ **數據圖表頁（標題+「(須人工補充圖表)」+ 核心洞見一句話 + 建議圖表類型）** / QA 頁（3 建議問題 + 1 CTA）
   - 輸出格式：Markdown `# Slide N｜主標題` + bullet 內文 + `/* 口語講稿 */` 註記 + `:: 設計風格` 指令；`---` 分隔投影片

2. **2Slides「10 個 AI 提示詞模板」** — `2slides.com/zh-TW/blog/10-ai-prompt-templates-perfect-presentation-slides`
   - 10 種場景模板：募資簡報 / 季度業務審查 / 產品發布 / 每週團隊更新 / 培訓入職 / 銷售提案 / 會議演講 / 行銷回顧 / 策略計畫 / 數據分析
   - 提升提示品質 6 技巧：指定投影片數量、指明受眾、**貼實際數據**（不要說「包含我們的數據」）、設定語氣、bullet 結構、每張投影片一個關鍵指標

3. **Meiko「NotebookLM 簡報 Prompt 生成器」**（互動工具）— `meikochang.github.io/ppt-prompt/`
   - 表單選：頁數/時間/角色/場景/受眾/語氣/CTA/大綱架構（問題解決法/起承轉合/時間軸/SCQA/結論先行）/視覺風格 → 自動產出繁體中文完整 prompt

### 英文

4. **SurePrompts「30 AI Prompts for Presentations」** — `sureprompts.com/blog/ai-prompts-for-presentations`
   - 核心原則：**one-idea-per-slide**（一頁一個想法）+ 指定受眾知識水平 + 講者備註
5. **AI Academy「20 ChatGPT Prompts for Presentations」** — `academy.techpresso.co/prompts/chatgpt-prompts-presentations`
6. Claude storytelling：hook → problem → solution → 案例 → 行動（LinkedIn sanskritibokde 8 prompts）

## notehub 現況（ppt_gen.py `_extract_key_points`）

目前 prompt 很基本：只要求「4-6 個重點、每個 2-3 bullets」的 JSON（title/subtitle/points/summary）。缺：
- **故事線**（hook→問題→解決→案例→行動）
- **頁面類型多樣化**（只會做封面 + 內文兩種版型；無金句/數據/QA 頁）
- 標題無 Tagline 化（≤10 字）、無講稿/內文分離

渲染端（`_add_title_slide`/`_add_content_slide`）：暗藍底（0x1A1A2E）+ 暖紅 accent（0xE84D3D），編號 badge + heading + ▸ bullets。呼叫端：`generate_ppt(script, title, lang, out_dir)` — **out_dir 要用 keyword `out_dir=`**（位置參數會當 lang）。

## 升級建議（低風險優先）

| 層級 | 作法 | 風險 |
|------|------|------|
| Prompt 升級 | 104 模組精神寫進 `_extract_key_points`：先定 Story Line、每頁一個核心訊息、tagline 標題 ≤10 字 | 低（只改 prompt，不動渲染）|
| 輸出結構擴充 | JSON 加 `story_line`、`slide_types`（hook/problem/data/quote/action）、每頁 tagline | 中（前端渲染要對應）|
| 渲染升級 | ppt_gen.py 支援金句頁/數據頁/QA 頁版型 + 視覺風格指令 | 高（較大工程）|

## 搜尋發現

- 中文 PPT prompt 資源品質高於英文（104/2Slides 都是結構化模組，非單一咒語）
- 通用 prompt 優化文（pxz.ai/aiworks）是圖像生成向，不適合投影片 — 要搜「簡報 大綱 模組」而非「提示詞」
- 搜尋順序用 anysearch batch_search 多查詢並行（中英各 2-3 個）再挑高價值頁面

## 階段 1 實作（2026-08-06 ✅）

`ppt_gen.py` + `visual_gen.py` 三項升級（端到端驗證 8 slides 成功）：

1. **Prompt 升級**（`_extract_key_points`）：角色=簡報架構師；內部思考流程=敘事弧線（Hook→問題→論點/證據→案例→行動）；one-idea-per-slide；heading 用 tagline（≤10 字、動詞/問句）；bullets ≤15 字具體有畫面；summary 含 takeaway+行動建議；points 5-7 個首=Hook 末=行動；**禁 ASCII 雙引號**（中文引號「」）避免破壞 JSON。
2. **JSON 容錯解析**：`_parse_json_loose()`（找第一個 `{` → raw_decode → 失敗 rfind `}` 截斷再試）+ `key_points` 結構 normalize 成 `points`（title→heading、description/details→bullets）。取代原本只 strip code fence + json.loads。
3. **🔴 max_tokens=0 bug（重要教訓）**：deepseek-v4-flash 是 reasoning 模型，設 `max_tokens` 會被思考過程吃光 → `content` 空 → 回 None → 提取失敗 fallback「無法提取」。ppt_gen.py 原傳 2000、visual_gen.py 原傳 1500 → 都改 0（不帶）。podcast.py 原本就正確。**以後 call_zen 一律不傳 max_tokens。**

驗證：`/opt/data/tmp/test_ppt_prompt_v1.py`（質量檢查：7 頁/heading≤12/bullet≤20 全過）、`test_ppt_e2e.py`（8 slides 生成成功）。

## 後續階段

- 階段 2：輸出結構加 `story_line` / `slide_types`（hook/problem/data/quote/action）— 渲染要對應
- 階段 3：ppt_gen.py 支援金句頁/數據頁/QA 頁版型 + 視覺風格指令（104 模組的頁面類型規則）
