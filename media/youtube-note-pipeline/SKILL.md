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
| Synthesis | `notehub/core/synthesis.py` | 多來源合成（2026-08-07 改用完整逐字稿）|

## 🔧 LLM Fallback Chain（2026-08-01 更新）

### 🔴 呼叫原則（2026-08-06 實測）
**notehub 內新寫任何 LLM 呼叫一律用 `call_llm()`（含 Zen→AGNES→Groq fallback 鏈），不要直接 `call_zen()`**。`call_zen` 無 fallback — Zen timeout 時呼叫端直接拿 None → PPT 變 3 slides 基本版、整段提取失敗。ppt_gen.py / visual_gen.py（2026-08-06）與 podcast.py `_generate_script()` / `_translate_title()`（**2026-08-07 已修**）全部改走 call_llm。例外：需要 raw 回應的場景才用 call_zen。配合 pitfall 37：max_tokens 一律傳 0 或不帶。

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
- `scripts/ppt_preview_color.py` — 彩色 PPT 預覽渲染器（PPTX→HTML→Playwright 截圖，emoji 彩色）。交付 .pptx 前跑這個，取代單色 `ppt_preview_render.py`（見 pitfall 65）
- `references/playwright-mobile-verify.md` — Playwright 手機模式 UI 驗證 recipe（2026-08-06）：插測試 job → iPhone 13 viewport → DOM 驗證 → 截圖 → vision 確認 5 步流程，含 selector 坑（`.nh-checks` 非 `.nh-artifacts`）與可複製的 verify 腳本範本（/opt/data/tmp/verify_v15_merge_card.js、verify_v16_progress.js）
- `references/script-quality-scan-and-rebuild.md` — 口播 script.md 品質掃描 + 批量重建（2026-08-07）：**空行分段偵測**（連續行合併會誤判 20/22 → 正確只有 5 個）、標點密度 <5/100 字 = raw transcript 特徵、從 raw.md 直接 `produce_podcast()` 重建不需重新下載/轉寫（單支 100-230s）。使用者要求「刪掉無分段舊檔重作」時先看這份
- `references/script-quality-verification.md` — 口播腳本重寫率驗證 SOP（2026-08-08）：substring 覆蓋率 + 句子層級照抄率雙重指標、判讀準則、重跑方法、2026-08-08 實測數據（開源全史/死後旅程/理解能力）、口語稿 vs 逐字稿差異
- `references/opencc-s2twp-trap.md` — OpenCC s2twp 錯誤使用模式（2026-08-08）：**不要 zip 逐字比對**，會全毀檔案；正確用法是直接替換 + over-conversion fixes
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

49. **🔴 Notehub 統一輸出到口播資料夾（2026-08-07 ✅）** — 原本 YouTube/Bilibili/Instagram 走 `口播/`，其他來源（URL/PDF/文字）走 `notes/`。2026-08-07 統一改為全走 `口播/`，簡化目錄結構。`pipeline.py` 第 322-324 行移除 source_type 判斷。

50. **🔴 PPT emoji 自動美化（2026-08-07 ✅）** — 根據標題/bullets/summary 關鍵詞自動添加相關 emoji（100+ 映射表）。`_add_emoji()` 函數：① 檢查是否已有 emoji 避免重複；② 搜尋 `_EMOJI_KEYWORD_MAP`（AI→🤖、數據→📊、成長→🚀…）；③ 格式 `🎯  標題`（emoji 後雙空格）。生成流程：`_extract_key_points()` → `_add_emoji_to_data()` → 渲染。**驗證**：AI 視覺模型實測 → 標題/內文/bullets/結尾皆帶 emoji + 幾何超界 0 + 118 tests 全過。

51. **🔴 PPT 新版型（2026-08-07 ✅）** — 新增 3 種版型：`comparison`（左右對比，用 → 分隔兩組）、`timeline`（時間軸/流程，箭頭連結）、`split`（左標題 + 右內容）。dispatch 依 `slide_type` 選版型，LLM 會自動依內容選擇合適版型。
52. **🔴 TTS 失敗：短 chunk 過濾（2026-08-07 實測）** — `_split_long_text()` 在切割長文本時，當 chunk 接近 max_chars（200）限制，剩下的 sentence 可能只有「。」或「.」等單一字元（標點符號-only）。edge_tts 無法處理這些空內容，回報 "No audio was received"。**已修**：`podcast.py` `_split_long_text` 新增過濾 `chunks = [c for c in chunks if len(c.strip()) >= 5]`。驗證：Job #84 修復後 arts=2, paths=2（原來 arts=3, paths=2 不符）。**延伸（同日上午再現）**：LLM 腳本中間插入 markdown 分隔線（`---`）也會被 `_parse_solo_script` 當成 TTS 段落 → 3 字元輸入同樣觸發 "No audio was received"（retry 3 次後該段被跳過 → mp3 缺 1 段、Merged 18/19 segments）。**已修**：`_parse_solo_script` 過濾 `re.match(r'^[-*_]{3,}$', line)` 的分隔線 + 段落級 `len(p.strip()) >= 5` 過濾。**注意**：`_parse_solo_script` 與 `_split_long_text` 是兩條獨立路徑，都要各自過濾 — 只修一個另一個仍會炸。驗證：重跑後 30/30 segments 全成功。
53. **🔴 script.md 無標點無分段（2026-08-07 實測）** — LLM prompt `_SOLO_PROMPT`/`_DUAL_PROMPT` 缺少「標點符號」和「分段」明確要求，導致生成的腳本是一整段連續文字（正常 script 28 個空行段落 vs 問題 script 只有 3 個）。TTS 朗讀無自然停頓，聽起來不自然。**已修**：prompt 新增 `9. 🔴 必須使用完整的標點符號（句號。逗號，頓號、問號？感嘆號！）` 和 `10. 🔴 自然分段，每段 3-5 句，段之間空一行` 和 `11. 🔴 如果輸入是結構化 markdown（標題、條列），請轉換成流暢的口播腳本，不要直接複製原始格式`。下次重新提交 job 會自動套用新 prompt。
54. **🔴 合成流程改用完整逐字稿（2026-08-07 實測）** — 原本 `_summarize_source()` 把每個來源濃縮成摘要，再合成報告，導致資訊遺失。**已修**：移除 `_summarize_source`，直接使用完整逐字稿（max_tokens 從 4096 提升至 8192），保留完整資訊。
55. **🔴 script.md 無標點無分段 = raw transcript fallback（2026-08-07 實測，#84）** — 即使 prompt 已加標點/分段要求（pitfall 53），Zen 429 限流時 `_generate_script()` 回 None → podcast.py fallback「using raw transcript for TTS」→ **直接把 Whisper 逐字稿寫成 script.md**（無標點無分段、跟 raw.md 幾乎一樣）。**症狀辨識**：job output 出現 `[WARN] Script generation failed — using raw transcript for TTS`；script.md 與 raw.md 內容雷同。**根因**：podcast.py `_generate_script()` 用 `call_zen` 直接呼叫，無 AGNES/Groq fallback。**✅ 已修（2026-08-07）**：`podcast.py` `_generate_script()` **和** `_translate_title()` 都改走 `call_llm()`（Zen→AGNES→Groq，`max_tokens=0`），`import re` 補上。修完 grep 驗證：`podcast.py` 內 `call_zen(` 應為 0 個。**時間因素**：#84 script.md 產出 04:31 < prompt 標點修正 commit 04:46 — 舊 job 用的還是舊 prompt，重送才會套用新 prompt。**批量重建**：無分段 script 的資料夾都留有 raw.md → 直接 `produce_podcast(transcript=<raw 內容>, title, url, lang='zh', mode, voice_a, voice_b, out_dir=<原資料夾>)` 重跑即可，**不需重新下載/轉寫**（單支約 100-230s）。讀 script.md 用 `python3 -c`/terminal（read_file 會把純 CJK UTF-8 誤判 binary）。
56. **🔴 PPT 必失敗：`name 'job' is not defined`（2026-08-07 實測，#84，已修）** — pipeline.py `_generate_outputs()` 呼叫 `generate_ppt(..., scheme=job.get('ppt_scheme', 'dark'))` 的 `job` 變數在該函數 scope 未定義（2026-08-07 加 ppt_scheme 功能時引入）。任何帶 `--ppt` 的 job 都報 `[ERROR] PPT failed: name 'job' is not defined`，job 照樣 done（status=done）但 PPT 沒產出。**查証**：`grep -n "job.get('ppt_scheme'" /opt/data/skills/media/youtube-note-pipeline/scripts/notehub/core/pipeline.py`。**✅ 已修（2026-08-07）**：`ppt_scheme` 改正式參數鏈，四處同步 — ① `_generate_outputs(..., ppt_scheme="dark")` ② `run_pipeline(..., ppt_scheme="dark")` + 兩處 `_generate_outputs` 呼叫 ③ CLI `__main__.py` 加 `--ppt-scheme` flag ④ worker `routes_notehub.py` 組 cmd 時 `['--ppt', '--ppt-scheme', job.get('ppt_scheme') or 'dark']`（synthesis 與 single 兩分支都要加）。**經驗**：新增功能參數（DB 欄位 → CLI → pipeline）時，任何一個環節漏接 = 變數未定義或永遠預設值，最常出在 pipeline 內部直接引用呼叫端才有的變數（如 `job`）— 一律走參數鏈傳遞。

57. **🔴 口播角色命名：曉萱＋永康（2026-08-07，使用者拍板，✅ 驗證通過）** — 使用者抱怨雙人腳本直接稱呼「A」「B」唸出來很怪（「A 你怎麼看？」一聽就很怪）。**已改 podcast.py**：① `_DUAL_PROMPT` 角色 = **曉萱（女聲主持人，A:）+ 永康（男聲評論員，B:）**，`A:`/`B:` 前綴**保留**（解析用標記，TTS 不會唸出來），但 🔴 對話內容提及對方一律用名字（「曉萱，你怎麼看？」「永康補充說…」），絕對禁止「A」「B」「主持人」「評論員」稱呼；② `_SOLO_PROMPT` 主持人 = 曉萱，開頭自介「大家好，我是曉萱」，全程以「我」自述；③ `DEFAULT_VOICE_A/B` 註解與 script.md header（`雙主持人（曉萱＋永康）`）同步改名。**名字是使用者指定，不是 agent 猜**：第一次 agent 自取「曉臻＋雲哲」被使用者否決 → 使用者指定 女=曉萱、男=永康。**⚠️ 改 code 前必須先問**（使用者糾正「妳沒問我同意嗎」）：開放式要求（「幫他們取名字」）要先用 clarify 提出方案＋名字、等使用者拍板才動手。**✅ 驗證**：grep 舊名 0 殘留、新名 12 處；`_parse_dual_script` 5 段解析 OK；`_parse_solo_script` 3 段 OK；prompt 對應關係正確。只影響**之後新生成**的腳本，舊檔重送才套用。詳見 `references/voice-shortcuts.md`。

58. **🔴 合成分塊 bug：每塊獨立合成 → 報告後半重複混亂（2026-08-07 實測，K2 三來源）** — `synthesis.py _synthesize()` 對 >24,000 字的合併逐字稿用 `_chunk_text(max_chars=24000, overlap=1000)` 分塊後，**每塊各自帶完整 SYNTHESIS_PROMPT 獨立合成** → chunk 2 輸出另一份完整報告結構（來源一~七重複章節），直接 append 在 chunk 1 之後 → `synthesis_report.md` 後半（4,177 字）是重複/混亂內容。**症狀辨識**：同一章節（如【📌 共通主題】）出現兩次；前半只有來源一~三、後半卻冒出來源四~七。**診斷**：搜尋報告中重複章節標題、比對 offset。**✅ 已修（當天實作）**：`synthesis.py` 新增 `CONTINUATION_PROMPT` — chunk 0 走 SYNTHESIS_PROMPT 完整合成；chunk 1+ 走接續模式（只輸出「### 補充：<主題>」新內容、禁止重複共通主題/整體結論等總覽章節）；parts join 用 `\n\n`（不用 `---`）。**驗證（K2 重做）**：新報告 7,509 字、【共通主題】僅 1 次、無來源四~七、章節結構乾淨（共通→三來源→差異→結論+補充）。**合成再生產**：synthesis job 完整逐字稿存 notes 表 `raw_content` → `_synthesize(raw)` → `produce_podcast(report)` 直接重做，不需重新下載/轉寫（同 pitfall 39/55 概念）。**影響**：口播/PPT/圖卡都吃這份報告 → 混亂後半會污染下游產出。

59. **🔴 合成口播腳本過度濃縮（2026-08-07 實測，K2 三來源）** — 三來源逐字稿 30,568 字 → 合成報告 13,104 字 → 口播腳本只有 3,936 字（3.3x 濃縮）→ MP3 僅 10.8 分鐘，使用者嫌「太短」。**根因**：`_SOLO_PROMPT`/`_DUAL_PROMPT` 無長度下限要求，LLM 傾向把結構化報告濃縮成重點摘要；`__main__.py` synthesis 分支把 `report_content`（含 YAML frontmatter + markdown 標題）直接餵給 `produce_podcast`。**✅ 已修（當天實作）**：① `_DUAL_PROMPT`/`_SOLO_PROMPT` 加完整性/長度要求 — 「完整涵蓋輸入內容所有章節（共通/各來源/差異/結論行動建議）+ 保留數據劑量細節、目標 ≥4500 字（約 20-25 分鐘）」② 重做前先修 pitfall 58（避免把混亂後半餵給 LLM）③ 確認三來源真的合併：查 notes DB `raw_content`（`WHERE source_type='synthesis' AND title LIKE '%K2%'`），用 `### 來源：` split 統計各來源字數（K2：Brad 13,714 + Berg 7,945 + 楊 8,909 = 30,568）。**驗證（K2 重做）**：腳本 5,737 字（原 3,936）、44 段 TTS（原 18 段）、MP3 **992 秒 = 16.5 分鐘**（原 650 秒 = 10.8 分鐘，+53%）、曉萱/永康各互稱 4 次、主持人A/評論員B 殘留 0、報告 7,118 字無重複結構、三來源完整涵蓋。重做腳本 `/opt/data/tmp/regen_k2.py`（DB raw_content → _synthesize → produce_podcast）。

60. **🔴 Telegram 無法預覽 .pptx：交付 PPT 要附 PNG 預覽（2026-08-07 實測，K2）** — 使用者收到 .pptx 附件說「ppt 還是沒看到」，但檔案明明存在且有效（python-pptx 開得起來、7 頁正常）。**根因**：Telegram 只把 .pptx 當一般檔案附件發送，沒有視覺預覽（不像 .png/.jpg/.mp3/.mp4 有內嵌預覽）→ 使用者以為「沒生成/沒收到」。**✅ 修法**：`scripts/ppt_preview_render.py` 用 python-pptx 讀出每頁文字 → Pillow 畫成 PNG（深藍底、白字/橘字粗體、960x540）→ MEDIA: 傳全部 slide_NN.png 給使用者（一次可多個 MEDIA: 行）。**注意**：這是**內容預覽**不是版型還原 — 背景/圖片/形狀/精確排版不會重現，用途是「確認內容存在且可讀」；要精確版型仍需 PowerPoint/LibreOffice（本機沒裝）。**經驗**：交付產出到 Telegram 前，先想「這個格式 Telegram 有沒有視覺預覽」— 沒有就要附 PNG/JPG 預覽，不要只丟原始檔。**⚠️ 流程教訓（使用者質問「為何沒用新的腳本跑」）**：`scripts/ppt_preview_render.py` 早在 2026-08-06 就存在，卻在 `/opt/data/tmp` 自寫 `ppt_to_png.py` 重造一模一樣的輪子。**規矩：動手前先搜尋既有 script（`search_files scripts/`），確認沒有才自寫** — 使用者對「重複造輪子」會直接質疑。

61. **🔴 PPT「太單調」≠ 沒套模板 — 先查 emoji 映射表主題是否涵蓋內容領域（2026-08-07 實測，K2）** — 使用者嫌 K2 PPT「沒套用昨天模板 skill 及 noto emoji 嗎太單調」。**調查結論**：模板/版型其實有套（v2 8 頁，hook/qa/content/data/action 分布正常、9 版型系統有跑），問題出在 `_EMOJI_KEYWORD_MAP` — **321 個關鍵字全是科技/AI 主題**（ai/數據/rocket/cloud/chat/code…），**健康醫療關鍵字 = 0**（維生素/鈣/心臟/骨骼/藥全無）→ K2 健康內容套不到任何 emoji → 看起來像單調白底黑字。**診斷順序**：① 確認版型有跑（slide_type 分布正常）② `import ppt_gen; len(ppt_gen._EMOJI_KEYWORD_MAP)` + 檢查該內容領域的關鍵字是否在映射表（`[k for k in emoji_map if '心' in k or '鈣' in k ...]`）。**✅ 已實作（同日，K2 v3）**：擴充 `_EMOJI_KEYWORD_MAP` 健康醫療組 — 💊維生素/补充/保健、🦴鈣質/骨骼/骨質/骨密度、❤️心臟/心血管/冠狀動脈、🩸血液/血壓、🌿健康/養生、🔬試驗/研究/臨床、⚖️劑量/dose、🩺醫生/醫師。**🔴 單字關鍵字陷阱**：`_add_emoji` 是 substring 匹配（`keyword in text_lower`）且越長越優先 — 單字「鈣」會誤配「鈣化」（K2 報告出現 31 次，鈣化是中性詞不該配 🦴）→ 用「鈣質」「骨質」等長詞，**不要用單字**；下關鍵字前先 `grep -oE` 報告詞頻決定長度。**驗證**：重跑後 emoji 6→17、封面「💊 維生素K2：鈣的導航員」+「🔬 解析最新臨床試驗」、XML `<a:t>` 確認 17 字元正確寫入、幾何 0 超界。走 `notehub/generators/ppt.py` wrapper 重跑（用戶要求用正式腳本，見 pitfall 60 流程教訓）。**教訓：emoji 映射表要覆蓋內容領域，不能只為 AI/科技主題設計**；使用者說「太單調」時不要急著重做，先查根因（版型沒跑 vs emoji 沒套 vs 字型沒生效）。改 code 前先問（pitfall 57 規矩）。

62. **🔴 PPT 預覽圖 emoji 顯示成方框 ≠ PPTX 沒 emoji（2026-08-07 實測）** — pitfall 60 的 `scripts/ppt_preview_render.py` 原本只用 Source Han Sans TC（**無 emoji glyph**）→ PPTX 內的 emoji 在預覽 PNG 顯示成 ☑ 替代方框，看起來像「PPT 沒套 emoji」。**真相在 XML**：`zipfile` 解開 .pptx → 抽 `<a:t>` 文字節點（`re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)`）確認 💊❤️🦴 等字元**確實寫入** → PowerPoint/手機開檔是**彩色 emoji**，預覽圖只是渲染器字型不足。**✅ 已修 `ppt_preview_render.py`**：新增 `draw_mixed()` — emoji codepoint（`\U0001F000-\U0001FAFF` / `\u2600-\u27BF` / `\u2B00-\u2BFF` / `\u2460-\u2473` / `\uFE0F`）用 `/opt/data/fonts/NotoEmoji-Regular.ttf` 渲染、其餘用主字型（NotoEmoji 是**單色白線條**，非彩色，但可辨識形狀）；需 `import re`。**驗證流程**：先寫 `/opt/data/tmp/ppt_preview_emoji.py` 驗證可行 → 再 merge 回正式 script。**教訓：預覽圖失真 ≠ 產出檔案有問題 — 先檢查原始檔案（XML/二進位內容）再怪生成器**；渲染器缺字型是第一嫌疑。

63. **🔴 emoji「沒有套色」根因：`_EMOJI_FONT` 是死碼（2026-08-07 實測，K2）** — 使用者嫌「emoji 沒有套色」→ XML 檢查發現 emoji 字元（💊❤️🦴）**有寫入**，但該 run 的 `<a:latin typeface="Source Han Sans TC"/>` → PowerPoint 用思源黑體畫 emoji = 黑白/fallback，非彩色。**根因**：`ppt_gen.py:241` 宣告 `_EMOJI_FONT = "Noto Color Emoji"` 但**全檔無一處讀取**（`grep -n _EMOJI_FONT` 只有定義行）；`_apply_cjk_font()` 把所有 run（含 emoji run）都設 `latin/ea = Source Han Sans TC` → emoji 字型被覆蓋。**診斷**：zipfile 抽 `<a:r>` 看含 emoji run 的 `<a:latin typeface>` 是否為 emoji 字型（寫入 XML ≠ 有彩色字型）。**修法方向（尚未實作，等使用者拍板）**：`_apply_cjk_font` 後拆 run — 含 emoji 的字元獨立成 run 並設 `Segoe UI Emoji`（Windows/Mac 彩色），或 `_apply_cjk_font` 跳過 emoji run。**教訓：宣告變數 ≠ 生效 — 新功能寫完要 grep 確認真的有被讀取**；「字型設好了」要在 XML 驗證 run 層級。
64. **🔴 generate_ppt 每次重跑都重新 LLM 提取 → 同報告不同 scheme 頁數會變（2026-08-07 實測，K2）** — 換配色重跑同一份 synthesis_report.md：`blue` = 9 頁、`green` = 8 頁（LLM 提取變異），且每次重跑都吃一次 LLM 呼叫（Zen timeout → AGNES fallback 單次可達 1-2 分鐘）。**影響**：① 比較配色不是 apples-to-apples（內容都不同）② 只想換配色卻花完整提取成本。**現況**：`generate_ppt(script, title, lang, out_dir, scheme)` 簽名沒有吃已提取 data 的入口 — 要公平比較需先改 code（提取一次、多 scheme 渲染共用）；在此之前用同 scheme 重跑比對版型分布會被 LLM 變異干擾。**COLOR_SCHEMES 有 4 種**（dark/blue/green/light）但預設只有 dark — 使用者問「skill 中沒有其他樣板嗎」時，除了版型（9 種）也要提配色（4 種）都可選，`generate_ppt(scheme=...)` 或 CLI `--ppt-scheme`。詳見 `references/ppt-design-patterns.md`。

65. **🔴 彩色 emoji 預覽：Pillow 做不到，用 Playwright + Chromium 後製套色（2026-08-07 實測，K2 ✅）** — 使用者問「黑白 emoji 不是妳可以後製套色嗎」→ 目標是**預覽 PNG 有彩色 emoji**（PPTX 本身 PowerPoint 開就是彩色，問題只在 Pi 上渲染預覽）。**試過的死路**：① `ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")` → Pillow 報 **`invalid pixel size`** — NotoColorEmoji 是 CBDT bitmap 格式，Pillow 不支援（pitfall 62 的 NotoEmoji-Regular.ttf 是單色白線條，可辨識但不彩色）；② browser 工具開 `file://` 被安全限制擋；③ python venv 沒裝 playwright。**✅ 可行解法**：node playwright（`/opt/data/tmp/node_modules/playwright`）→ PPTX 抽文字 → 生成 HTML（每頁一個 `.slide` div，`position:relative`，否則 `.page-no` absolute 定位跑掉）→ `page.$('#sN').screenshot()` 逐頁截圖 → **彩色 emoji 完整渲染**（💊 黃紅、🔬 青藍、📈 紅色折線 — vision_analyze 逐一驗證）。**已封裝**：`scripts/ppt_preview_color.py`（`python ppt_preview_color.py <file.pptx> <out_dir> [dark|blue|green|light]`）— 取代 pitfall 60 的單色 `ppt_preview_render.py` 做「給使用者看的預覽」。**教訓：使用者說「可以後製嗎」通常是提示解法存在 — 先想替代渲染路徑（瀏覽器/其他工具）再回報做不到**；Pillow 彩色 emoji 是已知限制，別浪費時間反覆試。

66. **🔴 PPT 字體大小在 paragraph 層級，不在 run 層級（2026-08-07 實測，K2「字太小」）** — 使用者嫌 PPT「字太小」→ `bump_existing_pptx.py` 只改 `run.font.size` 得到 **0 個 run 被改**（v4 檢查：32 個 run 全 None、字體大小分布全空）→ 真正的大小設在 **`para.font.size`（paragraph 層級）**。python-pptx 生成器（ppt_gen.py）用 `p.font.size = Pt(n)` 設定（p=paragraph），run 層級沒設。**修改既有 PPTX 字體時 run/paragraph 兩層都要查**（有值的那層才是生效處）。**✅ 已修 ppt_gen.py**：字體全面放大一級 — 16→20、18→22、20→24、22→26、28→32、32→36、34→40、36→40、40→44（35 處）。**使用者偏好：內容文字 ≥20pt**（16-18pt 會被嫌太小）。**⚠️ 放大技巧**：regex 一次性替換 `Pt(\d+)` 查表（**不要 sed 連鎖** — Pt(16)→Pt(20) 後會被 20→24 規則再匹配一次，全部跑一輪就對）。**經驗：python-pptx 字體屬性三層級（run/paragraph/defRPr），生成器常用 paragraph 層級 — 改檔案別只查 run。**

67. **🔴 產出檔名含 `?` → Android/FAT32 同步失敗（2026-08-07 ✅ 已解決，K2）** — 使用者問「為何 pptx syncthing 無法同步」→ 根因：K2 資料夾檔名 `Should You Take Vitamin K2? (New Trial).pptx` **含半形 `?`** — Android 手機儲存（FAT32/exFAT）`?` 是**非法字元** → Syncthing 接收端無法建立該檔 → 同步卡住重試失敗；其他檔名正常的檔案（md/mp3）早就同步成功，吻合「只有 pptx 沒同步」。**環境確認**：Syncthing 跑在**宿主機 DietPi Docker 容器**（lscr.io/linuxserver/syncthing:latest v2.1.1-ls220，container /syncthing，bind `/home/syncthing_cfg:/config` + `/home/hermes_data/obsidian-vault:/rpi4_hermes_obsidian`，port 8384 publish 宿主 0.0.0.0）— **hermes 容器內看不到其進程/API 屬正常**（不同 network namespace；172.17.0.2:8384 可達但 API key 不符 → Forbidden）。**✅ 已修**：8 個檔案 `?` → 全形 `？`（U+FF1F，合法字元）`mv -- "$f" "$(echo "$f" | sed 's/?/？/g')"` + `chmod -R 777` → 手機同步成功。**🔴 鐵律：產出檔名一律 sanitize 半形 `?`（改用全形 `？` 或刪除），`:` `*` `<` `>` `|` `"` 也同樣非法** — 有 Android/Windows 同步端時尤其重要；建立檔名後 `find . -name '*\?*'` 驗證 0 殘留。**教訓：Syncthing 同步失敗先查接收端（手機）檔案系統非法字元，別先怪同步設定。**
68. **🔴 口播腳本「逐字稿化」：LLM 只加標點沒改寫（2026-08-08 實測，#87 開源全史）** — 使用者聽 MP3 感覺「像逐字稿沒有 llm 整理」。**診斷**：script vs raw 的 substring 覆蓋率 66.4%（≥20 字連續相同片段）；句子層級 90%+ 照抄率偏高。**根因**：`_SOLO_PROMPT`/`_DUAL_PROMPT` 的 #3「保留原文核心觀點」+#13「完整涵蓋所有章節」+#14「保留細節不要過度濃縮 ≥4500 字」被模型理解成「整篇保留」→ 只加標點/分段/開場結尾，內文逐句照抄。**對比 K2（pitfall 59 過度濃縮 3.3x → 加完整涵蓋要求 → 矯枉過正變零濃縮）**。**✅ 已修**：兩 prompt 各加「🔴🔴 最重要的要求：用你自己的話重新講述，禁止逐句複製或照抄逐字稿…改寫率至少 70%」（solo #15 / dual #11）+ 原 #3/#1 改「用自己的話重新表達，不要照抄原文」。**驗證**：重跑後 substring 覆蓋 66.4%→55.5%、句子層級照抄率 25.3%（320 句只有 81 句 90%+ 相同；照抄的多為「UNIX 一開始非常粗糙」這類事實陳述句）、段落 58→85、主持人加註解（「被強行截胡了」）、MP3 43:19→44:44。**🔴 直接 produce_podcast 重跑不含 TC 繁中轉換** — 要自行 OpenCC s2twp + 套 pipeline 的 over-conversion fixes（`指令碼→腳本` 等），否則 script.md 會殘留簡體字（如「晓萱」）。**診斷工具**：`/opt/data/tmp/scan_all_overlap.py` 掃全部口播資料夾 substring 覆蓋率（>50% 🔴、>30% ⚠️）；2026-08-06 前舊 job 也有此問題（死後旅程 75%、理解能力 54%），用 raw.md 直接 produce_podcast 重跑即可，不需重新下載/轉寫。

69. **🔴 口播短/中/長三檔長度參數（2026-08-08 ✅ 實作+端到端驗證）** — 仿 NotebookLM 的絕對目標分鐘數邏輯（非來源百分比）：**短 = 1,500–1,800 字（~5 分鐘）、中 = 3,000–3,500 字（~10 分鐘）、長 = 6,000–7,000 字（~20 分鐘）**。CLI：`--length short|medium|long`（預設 long = 舊行為，向後相容）。**參數鏈五處同步**：① `podcast.py` 新增 `_LENGTH_INSTRUCTIONS` 字典（三檔，含「第 8 條長度指示」文字）② `_generate_script(..., length="long")` + `produce_podcast(..., length="long")` — prompt format 時注入 `{length_instruction}` ③ `script.md` frontmatter 記 `length:` 欄位 ④ `__main__.py` `--length` flag（pipeline 與 `--synthesize` 兩分支，unknown value fallback long）⑤ pipeline.py `run_pipeline/_generate_outputs` + worker `routes_notehub.py` 組 cmd `['--length', job.get('length') or 'long']`（synthesis 與 single 兩分支）。**移除 pitfall 59 的「至少 4500 字」硬錨點**（solo #14 / dual #10 改「在目標字數內盡量完整」），長度由第 8 條統一控制。**端到端實測**：3,107 字 raw → short 版 script 1,854 字（目標 1,500–1,800 +3% 浮動內）→ MP3 5.7 分鐘 ✅；未知 length fallback 不炸。**測試**：`/opt/data/tmp/test_podcast_length.py`（28 單元）+ `test_podcast_length_e2e.py`（真 LLM+TTS）。**待辦**：DB notehub_jobs 尚無 `length` 欄位、UI 無選單 — worker 已支援 `job.get('length')`，要接 UI 需 ALTER TABLE + 前端選單。**🔴 字數密度**：中文口播實測 ~348 字/分鐘（edge-tts 含停頓，比理論 250-280 快），短版 5.7 分鐘吻合。**教訓：長度錨點用絕對字數區間（可預期 token/時長），不要用來源百分比**（3 萬字影片 50% = 1.5 萬字唸 1 小時，一點都不短）。