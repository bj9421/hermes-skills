# Code Review 2026-08-05 — 19 bugs, 18 fixed（未 commit，改動在工作區）

獨立 reviewer subagent 深查 5 個核心檔案（routes_notehub / routes_bookmarks / llm_enhance / db / bookmark_io），
多數 bug 用真實 SQLite probe 實測確認。**18 個已修（改動在 git working tree，commit 被權限閘攔下）**。
修復 + 18 個 regression tests → **97 tests 全綠**（原 79）。下次 session 先 `git status` 確認並 commit。

## HIGH（2）

1. **FTS5 搜尋不平衡引號 → 整頁 500**（db.py build_filters）
   實測：`MATCH '"""'` / `'abc"'` → `OperationalError: unterminated string`。
   原 escape `"` → `""`（FTS5 標準 phrase escape）在字串以引號結尾時產生不平衡 `"abc""`。
   **修法：`search.replace('"', '')` 移除引號再包 phrase**（trigram 搜尋不需保留引號，任何輸入不 crash）。
   測試 `test_build_filters_search_trailing_quote` 防回歸。

2. **list_bookmarks_json limit 負數 → 全庫 dump**（routes_bookmarks.py:161）
   實測 `LIMIT -5` → SQLite 無上限 → 一次吐 58 筆（未認證 API）。非數字 → ValueError 500。
   **修法：`limit = max(1, min(request.args.get('limit', 20, type=int) or 20, 50))`** — type=int 失敗回 default + clamp [1,50]。

## MEDIUM（12，全修）

3. **canonicalize_url 無 path 但有 query 剝不掉 tracking**（db.py）
   regex host group `[^/]+` 把 `example.com?utm_source=x` 整段吃進 host。
   **修法：先 `partition('?')` 拆 query 再拆 host**，query 處理移到後面。

4. **tag LIKE wildcard 誤配**（db.py build_filters）
   tag 含 `%`/`_` 當 wildcard（`AI_` 撈出 AI、AI工具；`100%` 誤配任何含 100 的標籤）。
   **修法：`LIKE ? ESCAPE '\'` + 轉義 `\ % _`**。

5. **小紅書 float duration 判 None**（routes_notehub.py _parse_xhs_duration）
   `__INITIAL_STATE__` duration 可為 float（104.5）→ `isinstance(dur, int)` False → None → 永遠查不到時長。
   **修法：`isinstance(dur, (int, float))`**，與 yt-dlp 路徑 `int(float(raw))` 一致。

6. **add_bookmark daemon thread DB 連線洩漏**（routes_bookmarks.py _fetch_duration）
   每支影片書籤洩一個 sqlite3 connection（無 app context 的獨立連線，成功才 close）。
   **修法：`c = None` + `finally: if c is not None: c.close()`**。

7. **durations 端點 duration_checked_at 從不被 consult**（routes_notehub.py）
   查不到的 URL（NULL duration 但有 checked_at）每次請求都丟回 missing 重查 → 4 個平行 subprocess 卡 45s 塞爆 waitress 8 threads。
   **修法：讀取條件改 `duration is not None or duration_checked_at is not None`**（已查過直接回 NULL）+ SELECT 補欄位。

8. **LLM 回傳型別未驗證**（llm_enhance.py _call_llm）
   tags 回 list → `.split(',')` AttributeError；summary null → `None[:500]` TypeError。
   **修法：list 用 join 正規化、`str()` 後截斷**。

9. **stderr 優先丟失產出 marker**（routes_notehub.py _process_job）
   `(stderr or stdout)[-3000:]`：stderr 有內容就整段丟 stdout → `Raw saved:`/`Script saved:`/`Podcast saved:` marker 遺失
   → failed job 半成品（數百 MB mp3）刪不掉、running 進度卡 10%。
   **修法：`(stderr or '') + (stdout or '')` 合併，>3000 時頭尾各留 1500 + 中段截斷標記**。

10. **worker 重啟殘留 running job 重跑**（routes_notehub.py _ensure_worker）
    server 被 kill 時 running job 殘留 → 重啟後 get_pending 撈到重跑（重複產出 podcast）。
    **修法：啟動時 `UPDATE notehub_jobs SET status='queued', output='' WHERE status='running'`**。

11. **單筆刪除不同步 tags → 孤兒標籤**（routes_bookmarks.py delete_bookmark）
    batch delete 有 sync，單筆 DELETE 沒有 → tags 表殘留 0 使用數標籤。
    **修法：DELETE 後 `sync_tags_from_bookmark(conn, all_mode=True)`**。

12. **PATCH /tags 缺 to_traditional_tags**（routes_bookmarks.py update_tags）
    全系統標籤轉繁唯獨此入口漏掉 → 簡體混入；list/null 直接 500。
    **修法：`isinstance(raw_tags, str)` 檢查 + `to_traditional_tags(raw_tags.strip())`**。

13. **fetch-meta SSRF**（routes_bookmarks.py fetch_bookmark_meta / fetch-meta-form）
    `file:///etc/passwd`、`http://169.254.169.254` 等可被 urllib 讀取/探測。
    **修法：抽 `_check_fetch_url_safe(url)` helper — 只允許 http/https + `socket.gethostbyname` 後
    `ipaddress` 檢查 is_private/is_loopback/is_link_local 拒絕**；兩個 fetch 端點都套用。

14. **tags-only 新增 summary 永久空白**（routes_bookmarks.py add_bookmark）
    enrich 條件 `not summary and not tags` → 只帶 tags 的新增 processed=1 永不補摘要。
    **修法：條件改 `not data.get('summary')`；使用者有提供 tags 時保留原 tags 不被 LLM 覆蓋**
    （`if data.get('tags'): enriched_tags = to_traditional_tags(ensure_source_tag(url, data.get('tags','')))`）。

16. **batch ids 型別未驗證**（routes_bookmarks.py batch_action）
    ids 為字串 `"1,2,3"` → placeholder 5 個只綁 1 參數 → incorrect number of bindings 500。
    **修法：`isinstance(ids, list) and all(isinstance(i, int) for i in ids)` 否則 400**。

18. **sync_tags NOT IN (NULL) 語意相反**（db.py sync_tags_from_bookmark）
    used 空時 fallback `NOT IN ('NULL')` → SQL 中 `NOT IN (NULL)` 恆為 unknown → 一行都不刪
    （實測：241 標籤應全刪卻 0 行）。本意應清空 tags 表。
    **修法：`if not used: conn.execute("DELETE FROM tags")` else 原邏輯**。

19. **缺 busy_timeout → database is locked 500**（db.py _connect）
    waitress 8 threads + worker + cron 同時寫入，長交易讓其他寫入 5s 後拋 locked。
    **修法：`PRAGMA busy_timeout=10000`**。

## LOW（2，全修）

15. **_llm_request 例外路徑 HTTP connection 不關**（llm_enhance.py）
    close 只在 getresponse 成功後；例外 → conn 等 GC。
    **修法：`conn = None` + try/finally close**（重寫乾淨版，勿用註解混亂的半套）。

17. **import_bookmarks 無 try/except + 計數失真**（bookmark_io.py）
    executemany 失敗未捕 → 500；`imported += 1` 在 INSERT 前累加，INSERT OR IGNORE 被 UNIQUE 擋掉會 over-report。
    **修法：包 try/except + `cur.rowcount` 精確計數**。

## 已驗證無問題（排除項）

- Netscape parser 巢狀資料夾（Chrome 匯出 + Firefox 裸 DL 實測）
- durations 端點 ThreadPoolExecutor 共用 conn（UPDATE 只在主 thread）
- SQL injection：全參數化，placeholders 只有 `?`
- canonicalize_url 含 port / 大小寫 host / 無 scheme 皆正常

## 流程筆記（全專案 bug 掃描，非 pre-commit diff）

1. `git status` + 全測試 baseline（79 passed）+ server 健康（HTTP 200）
2. 靜態安全掃描：硬編碼密鑰 / os.system / eval / pickle / SQL f-string（`f"...{placeholders}"` 是安全的，placeholders=`?`）
3. dispatch 獨立 reviewer subagent（read_file 5 個核心檔案，回報 檔案:行號/嚴重度/描述/修法，繁體中文）
4. **對可疑點先實測再修**（SQLite probe 驗證 FTS5 crash、LIMIT -5、NOT IN NULL 才動手）
5. 每修一類跑測試（97 passed）+ 端點層級 test_client 驗證（limit 負數/搜尋引號/batch 字串/file:// scheme）
6. 重啟 server 需使用者確認（waitress 無 reloader）；watchdog 每 10 分確保拉起
