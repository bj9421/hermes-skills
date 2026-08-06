---
name: youtube-note-pipeline
description: YouTube/IG/Bilibili 影片轉口播 podcast 完整流程。Notehub CLI + bookmark-manager 整合。
related_skills: [verified-capabilities, taiwan-stock-data-pipeline, instagram-reel-podcast]
---

# NoteHub YouTube Pipeline

## 🎯 功能總覽

完整影片處理流程：YouTube/IG/Bilibili → Whisper 轉寫 → LLM 整理 → TTS 口播

## 📋 核心模組

| 模組 | 路徑 | 功能 |
|------|------|------|
| Pipeline | `notehub/core/pipeline.py` | 主流程協調 |
| LLM | `notehub/core/llm.py` | 多 provider fallback chain |
| Transcribe | `notehub/core/transcribe.py` | Whisper 三層 fallback |
| Podcast | `podcast.py` | 口播腳本生成 + TTS |
| Extractors | `notehub/extractors/` | YouTube/IG/Bilibili |
| Synthesis | `notehub/core/synthesis.py` | 多來源合成（2026-08-06 Phase 5）|

## 🔧 LLM Fallback Chain（2026-08-01 更新）

### 🔴 呼叫原則（2026-08-06 實測）
**notehub 內新寫任何 LLM 呼叫一律用 `call_llm()`（含 Zen→AGNES→Groq fallback 鏈），不要直接 `call_zen()`**。`call_zen` 無 fallback — Zen timeout 時呼叫端直接拿 None → PPT 變 3 slides 基本版、整段提取失敗。ppt_gen.py / visual_gen.py 原本直接 call_zen（2026-08-06 已改 call_llm）；podcast.py 正確。例外：需要 raw 回應的場景才用 call_zen。配合 pitfall 37：max_tokens 一律傳 0 或不帶。

### notehub pipeline（口播腳本）
```
1. OpenCode Zen (deepseek-v4-flash-free) — 20 RPM
   ↓ 429 限流
2. AGNES API (agnes-2.5-flash) — 20 RPM
   ↓ 失敗
3. Groq (llama-3.3-70b-versatile) — 30 RPM
   ↓ 失敗
4. 本地正則 (add_punctuation.py) — ∞
```

### bookmark-manager（書籤 enrich）
```
1. OpenCode Zen (deepseek-v4-flash-free)
   ↓ 429 限流
2. AGNES API (agnes-2.5-flash)
   ↓ 失敗
3. Groq (llama-3.3-70b-versatile)
   ↓ 失敗
4. 空回應（tags 保持不變）
```

## 🔑 API Key 讀取陷阱（2026-07-31 實測）

從 `.env` 讀取 API key 時，**必須去除換行符**：
```python
# ❌ 錯誤：會帶換行 → Authorization header 無效
key = os.environ.get('OPENCODE_ZEN_API_KEY', '')

# ✅ 正確：strip + 去除換行
with open('/opt/data/.env') as f:
    for line in f:
        if line.startswith('OPENCODE_ZEN_API_KEY='):
            key = line.split('=', 1)[1].strip()
            break
```

## 📚 References

- `references/multi-source-synthesis.md` — NotebookLM 式多來源合成（2026-08-05）：決策已定（混合來源/兩階段/勾選入口）
- `references/ppt-prompt-resources.md` — PPT 提示詞資源庫（2026-08-06）：104 職場力大綱模組 / 2Slides 10 模板 / Meiko 生成器 + notehub ppt_gen.py 升級紀錄 + **PPT skill 研究（anysearch：siril9/presentation-skill 16 版型 / guizang 23.3k⭐）+ 中文字型設定（Noto Sans CJK TC / python-pptx a:ea 坑 / fontconfig XDG_DATA_HOME 路徑）**。階段 1（Prompt 升級）已實作；階段 2（slide_types）/ 階段 3（金句/數據/QA 頁版型）已實作。使用者問「哪裡有 PPT 提示詞 / 提升簡報質量」時先看這份
- `references/ppt-skills-research.md` — PPT agent skill 研究（2026-08-06 anysearch）：22 repo 篩出 9 個重點（siril9/presentation-skill 最相關：MIT + python-pptx 同棧 + 16 版型；op7418/guizang 23.3k⭐ 設計原則可借鑑但 AGPL + HTML deck）+ 找 skill repo 的 batch_search→grep→extract 工作流。PPT 階段 3 渲染升級前先看這份
- `references/ppt-design-patterns.md` — 新版型系統（9 種）+ emoji 美化 + 幾何驗證腳本 + 字型優先序
- `references/playwright-mobile-verify.md` — Playwright 手機模式 UI 驗證 recipe（2026-08-06）：插測試 job → iPhone 13 viewport → DOM 驗證 → 截圖 → vision 確認 5 步流程，含 selector 坑（`.nh-checks` 非 `.nh-artifacts`）與可複製的 verify 腳本範本（/opt/data/tmp/verify_v15_merge_card.js、verify_v16_progress.js）
- `references/cjk-font-rendering.md` — CJK 字型渲染：**Pillow 圖卡（visual_gen.py）**：芫荽 iansui 主字型/Noto Sans SC fallback/emoji 用 NotoEmoji（彩色版 Pillow 不能渲染）+ **python-pptx 中文字型坑（font.name 只設 Latin，需 a:ea 屬性）**

## ✅ UI 自我驗證 SOP（2026-08-06 使用者要求）

**使用者原話：「妳要自己截圖確認，不要沒確認又丟給我。」** 任何 notehub/UI 改動完成後，**必須自己跑完整驗證**才回報，不能只跑 unit tests 就丟給使用者：

1. Playwright 手機模式：`browser.newContext({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } })`（**不能只設 viewport** — 缺 deviceScaleFactor 截圖會糊）
2. 開 `http://localhost:5001` → 點 `button.hamburger-btn`（☰）→ 自動切「工作進度」頁籤 → 等 job 載入（waitForTimeout 1.5-2s）
3. DOM 斷言：卡片數、checkbox 數/勾選數（容器是 **`.nh-checks`**，不是 `.nh-artifacts`）、📁 檔案路徑數、展開後檔案種類（含 .pptx/.png）
4. `page.screenshot()` 存檔 → **vision_analyze 自己看截圖**確認視覺（勾選狀態/破版/截斷）
5. 全部通過才回報，附上截圖 MEDIA 路徑

插測試 job：sqlite3 直插 DB（title 用 `TEST-` 前綴），驗證完 `DELETE WHERE title LIKE 'TEST-%'` 清理。
模板：`templates/verify_notehub_ui.js`（複製改 job 標題/斷言值）。

## ⚠️ Pitfalls

20. **notehub 口播 pipeline 的 LLM 一律不用 NVIDIA** — 範圍限定本 pipeline，NVIDIA 只負責 Whisper 轉寫

32. **🔴 YouTube Shorts URL 偵測 bug（2026-08-04 實測，重做案例）** — `_extract_video_id()` 與 `YOUTUBE_PATTERNS` **都必須**包含 `youtube\\.com/shorts/`，否則 shorts 影片不被 `detect()` 認出 → fallback 到通用網頁抓取 → **把 YouTube 頁面雜訊（簡介/媒體/著作權/© Google LLC）當逐字稿** → LLM script 寫「內容不完整」道歉信 → podcast 唸道歉信。**症狀辨識**：raw.md 內容是 YouTube 頁面 chrome 文字 = extractor 誤判成通用網頁，不是影片真的沒字幕。已修：兩個 regex 都補 `youtube\\.com/shorts/`（extractors/youtube.py）。修復驗證：`_extract_video_id('https://youtube.com/shorts/XXXX')` 回 11 字元 id + `detect()` True，再接 `_fetch_via_api` 確認無字幕 → 走 Whisper fallback。

35. **🔴 小紅書 URL 直接抓會 SSL 失敗（2026-08-05 實測）** — `xhslink.com` 短鏈 / `xiaohongshu.com` 在台灣被 DNS 污染，notehub `URLExtractor` 用 urllib 直接抓 → `SSL: CERTIFICATE_VERIFY_FAILED self-signed certificate`，job 秒失敗（status=failed、finished 0 秒，錯誤樣本 job #24「英伟达开源AI视觉模型…」xhslink.com/m/8qWhW4ScJIU）。**已修**：`notehub/extractors/url.py` 新增 `_is_xhs_url()` + `_fetch_xhs()` 專用路徑（解法搬自 bookmark-manager `llm_enhance.py fetch_xiaohongshu_meta()`）：
   - 短鏈 302 追蹤：`curl -s -o /dev/null -w '%{url_effective}' -A <iPhone UA> -k -L`
   - DoH 查 **www 子域**真實 IP：`https://dns.google/resolve?name=www.xiaohongshu.com&type=A`（根域會拿到錯 IP）
   - `curl --resolve 'www.xiaohongshu.com:443:<IP>'` 繞 DNS 污染抓頁面（手機 UA + `-k`）
   - parse `window.__INITIAL_STATE__`（大括號平衡 + `undefined→null`）→ `noteData.data.noteData` 的 title/desc/tagList
   - 產出文字格式：`標題：…\\n<desc>\\n標籤：…`，title 取第一行去「標題：」前綴
   - **注意**：小紅書圖文筆記無逐字稿，口播 pipeline 以 title+desc+tags 為基礎擴寫屬預期；影片筆記目前未接 yt-dlp+Whisper，需另做。

36. **🔴 CLI `--synthesize` 參數解析 bug（2026-08-06 Phase 5 實測）** — 原始實作 `sources = [a for a in args[idx+1:] if not a.startswith("--")]` 只會過濾 flag 本身（`--lang`、`--podcast`），**不會過濾 flag 的值**（`zh`、`solo`、`台女`）。結果 `--lang zh` 的 `zh` 被當成 source URL → 來源清單含 `['url1', 'url2', 'zh']` → 合成報告多一筆「來源 3（zh）」處理失敗記錄、標題包含 zh 字樣。

   **正確修法**（已實作）：掃描時遇到 flag 跳過下一個值：
   ```python
   raw = args[idx + 1:]
   sources, skip_next = [], False
   for a in raw:
       if skip_next:
           skip_next = False
           continue
       if a.startswith("--"):
           skip_next = a in ('--lang', '--podcast', '--voice-a', '--voice-b')
           continue
       sources.append(a)
   ```
   **驗證指令**：`python3 -c "args=['--synthesize','url1','url2','--lang','zh']; ... print(sources)"` 應輸出 `['url1', 'url2']`。

   **端對端驗證**：跑 `python -m notehub --synthesize <url1> <url2> --lang zh` → 檢查 obsidian 報告 frontmatter 的 `sources:` 欄位（不含 `zh`）、報告標題無 `zh` 字眼、STDERR 無「來源處理失敗 zh」。

37. **🔴 call_zen 一律不傳 max_tokens（2026-08-06 實測，PPT 提取整段失敗的根因）** — deepseek-v4-flash 是 **reasoning 模型**，輸出在 `reasoning_content`；設定 `max_tokens`（如 2000/1500）會被思考過程吃光 → `content` 空 → `call_zen` 回 None → 呼叫端 fallback「無法提取」（PPT 就變爛簡報）。**症狀**：`call_zen` 回 None 但 HTTP 沒報錯（200 但 content 空），單獨健康檢查有時成功有時 None（20 RPM 限流也會 None）。**修法**：`max_tokens=0`（或不帶參數，call_zen 預設 0 → payload 不帶 max_tokens）。ppt_gen.py（原 2000）與 visual_gen.py（原 1500）2026-08-06 已修正；podcast.py 原本正確。**以後任何 call_zen / call_llm 呼叫一律不傳 max_tokens**，除非該模型確定非 reasoning。

38. **🔴 PPT 提取失敗的診斷順序（2026-08-06 實測）** — `_extract_key_points` 回 None 時依序查：① `call_zen` 是否回 None（限流 20 RPM → 等 3s 重試，或看 stderr `[RATE_LIMIT]`/`[WARN] Zen LLM HTTP`）② 是否誤傳 max_tokens（pitfall 37）③ LLM 回傳 JSON 格式瑕疵（已由 `_parse_json_loose` 容錯：找第一個 `{` → raw_decode → rfind `}` 截斷再試；`key_points` 結構會 normalize 成 `points`）。2026-08-06 階段 1 升級後，質量驗證：`/opt/data/tmp/test_ppt_prompt_v1.py`（7 頁/heading≤12/bullet≤20）+ `test_ppt_e2e.py`（8 slides 生成）。詳見 `references/ppt-prompt-resources.md`。

39. **🔴 script 重用（2026-08-06，使用者洞察）** — 同影片重送不同輸出（如 #77 純口播成功後 #80 加 PPT）不該重跑完整 pipeline（下載→轉寫→LLM）。`_find_existing_script(source)` 按 YouTube video_id 找 `口播/*[id]*/script.md`，有 → 跳過 extract 直接吃 script.md 產出（23-26 秒 vs 10-20 分鐘）。**陷阱**：glob pattern `*[video_id]*` 的 `[]` 是字元集語法 → 必須 `glob.escape(f'[{video_id}]')`，否則誤匹配（NEVEREXIST999 也找到的 bug）。僅 YouTube 支援重用（非 YouTube 無下載脆弱性）。

40. **🔴 generate_ppt/generate_visual 的 out_dir positional bug（2026-08-06 實測）** — 簽名是 `(script, title, lang, out_dir)`，pipeline 舊 code 傳 `generate_ppt(content, title, out_dir)` → 第三參數 `out_dir` 被當 `lang` → PPT/圖卡存到 **cwd**（server worker 目錄）而非輸出目錄！**必須用 keyword**：`generate_ppt(script, title, lang=lang, out_dir=out_dir)`。同修 visual_gen.py。

41. **🔴 yt-dlp 下載暫態失敗會整支 job 掛（2026-08-06 實測）** — 同一影片 #77 成功 #80 失敗：`[WARN] yt-dlp audio download produced no file` → 三層 extract 策略全失敗 → job failed。修：`_download_audio` 加 retry×2（間隔 3/6 秒）。同場加映：ppt_gen/visual_gen 改用 `call_llm`（Zen→AGNES→Groq fallback）— 原本直接 call_zen，Zen timeout 就 fallback 成 3 slides 基本版簡報。

42. **🔴 重送合併原卡不開新卡（2026-08-06 方案 1，使用者要求）** — 同 bookmark 重送（如加 PPT）不該開新卡。`queue_jobs` 檢查同 bookmark 非 failed job → 合併：`ppt/visual` OR 原值 + mode 升級（none→solo/dual）+ done 設回 queued 讓 worker 增量重跑。**關鍵設計**：① `_job_artifacts` 的 ppt/visual 用**產出標記**（output 有 `PPT saved`/`Visual summary saved`）不是 DB 勾選欄位 → checkbox 反映實際產出（「PPT 完成後 checkbox 打勾」）② `_process_job` 增量執行：`arts` 判斷已產出（`arts['mp3']` 有就不跑 podcast、`arts['ppt']` 有就不跑 PPT），全部都有 → `need_run=False` 直接 done 不動 ③ `_worker_loop` output 用「`--- 追加輸出 ---`」合併保留舊 markers（否則 raw/script/mp3 的 checkbox 全掉）④ `_SAVED_MARKERS` 的 ppt pattern 用 lazy match `(.+?\\.pptx)` — **路徑含空格**（如「Cherry Studio V2 來了…」）`\\S+\\.pptx` 會在空格斷掉抓不到。驗證：重送 {id:110,ppt:true} → job_ids=[77] 合併、job 數不增、117 tests 全過。

43. **🔴 進度不倒退（2026-08-06 方案 1 續，使用者確認設計）** — done job 重送加 PPT/圖卡時，進度不該崩回 0%（視覺：100% → 0% → 95% → 100% 很怪）。`_job_progress` 以**已產出**為基礎：`arts['mp3']` 有（口播完成）→ queued 也顯示 95%；增量製作 PPT 中（ppt 勾選未產出）→ 96%；增量圖卡中 → 97%；全新 job 仍 0% 起跳。視覺：100% → 95% → 96% → 100%。驗證：`test_job_progress_no_regression`（8 場景）+ Playwright 手機模式（TEST-增量-PPT 卡 96% + 進度條寬度 96% + 「🔄 處理中」）通過。

44. **🔴 PPT 繁中字型（2026-08-06）** — Noto Sans SC 是**簡體**字型（SC=Simplified Chinese），繁體內容細看字形偏簡體規範。已下載安裝：**Noto Sans CJK TC**（Google 官方繁中，內部 family name 是 "Noto Sans CJK TC" 不是 "Noto Sans TC"！）+ **Source Han Sans TC 思源黑體**（Adobe 官方）→ `/opt/data/fonts/` + `/opt/data/.xdg/data/fonts/`（fc-cache 認得的位置；/usr/share/fonts 無權限）。**python-pptx 字型陷阱**：`run.font.name` 只設 latin typeface，中文必須另外設 `a:ea`（East Asian）屬性才生效 — `_apply_cjk_font()` 遍歷全部 run 設 `rPr.find(qn('a:ea'))` + `typeface='Noto Sans CJK TC'`。visual_gen.py `_load_font` 優先序：**思源黑體 Source Han Sans TC > Noto Sans CJK TC > Noto Sans SC > Iansui > WenQuanYi**。驗證：解壓 PPTX 檢查 `a:ea typeface="Source Han Sans TC"` ✅。三者都是 SIL OFL 授權，免費商用。

45. **🔴 PPT/圖卡更名保留（2026-08-06，使用者要求）**— 重送同名檔**不覆蓋**：ppt_gen.py/visual_gen.py 各加 `_unique_path(base)` — 路徑已存在 → `標題_v2.pptx` / `標題_summary_v2.png`（遞增 _v3/_v4…）。**配套（routes_notehub.py）**：`_job_paths` 原本 `pat.search()` 只抓第一個 marker → 多版本時 UI 顯示舊版。改 `findall()` 取**最後一個**（worker 追加輸出新版本在最後）= UI 顯示最新產出；`_delete_job_artifacts` 改 `finditer()` 刪全部版本。輸出 marker 抓 `.+?\\.pptx` lazy match 對 `_v2.pptx` 也有效。注意：生成會走 LLM（每次 90s 上限），端到端測試 4 次生成可能 5-10 分鐘 — 用背景執行 + notify_on_complete 或縮小測試範圍。CLI 第二次生成（script 重用）約 1-2 分鐘出 `_v2.pptx`。

46. **🔴 PPT 階段 2+3 — 版型系統（2026-08-06 ✅）** — **階段 2**（輸出結構）：`_extract_key_points` prompt 加 `slide_type` 欄位 + 版型規則（hook/content/data/quote/qa/action/comparison/timeline/split）。**階段 3**（渲染升級）：新增 8 個版型渲染函數 — hook（開場大標題置中）、content（一般內文）、data（數字卡動態寬度）、quote（金句置中 + 「「」裝飾）、qa（3 問題❓ + CTA →）、action（行動步驟→）、comparison（左右對比）、timeline（時間軸/流程）、split（左標題 + 右內容）。dispatch 依 `slide_type` 選版型。修既有 bug：content 版型 bullets 容器太高（4→2.6 inch）→ 超界。**驗證**：幾何超界 0 + LLM 端到端（Cherry Studio V2 → 7 頁，版型分佈 hook:1+content:3+data:1+quote:1+action:1 ✅ 無缺版型）+ 118 tests + Playwright 手機模式（_v3.pptx 路徑顯示 + 無破版）✅ + 新版型測試（11 slides 全部生成，幾何驗證通過）。

48. **🔴 PPT 配色方案選擇（2026-08-07 ✅）** — `COLOR_SCHEMES` 字典含 4 種配色：`dark`（深藍底+暖紅 accent，預設）、`blue`（深蓝底+藍 accent）、`green`（深綠底+綠 accent）、`light`（淺灰底+紅 accent）。`generate_ppt()` 新增 `scheme` 參數，自動套用配色到背景、文字、accent。需 try-except 包裹 `run.font.color.rgb` 存取（避免 `_NoneColor` AttributeError）。**整合**：notehub_jobs 新增 `ppt_scheme` 欄位（ALTER TABLE + schema.sql），`routes_notehub.py` queue_jobs 接收並存入 job，`pipeline.py` 調用 `generate_ppt(scheme=job.get('ppt_scheme', 'dark'))`。**驗證**：4 種配色生成測試通過 + 118 tests 全過。