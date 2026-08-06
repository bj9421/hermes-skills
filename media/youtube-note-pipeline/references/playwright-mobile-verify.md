# Playwright 手機模式 UI 驗證 Recipe（bookmark-manager notehub）

2026-08-06 v11-v16 反覆使用的 QA 模式。**使用者要求：改 UI 後必須自己 Playwright 驗證 + 截圖 + vision 確認，不准沒確認丟給使用者看**（「妳要自己截圖確認 不要沒確認又丟給我」）。

## 流程（5 步）

1. **插測試 job** — 直接 DB INSERT（比 API 快、可控狀態）：
   ```python
   import sqlite3;c=sqlite3.connect('/opt/data/projects/bookmark-manager/bookmarks.db')
   c.execute("INSERT INTO notehub_jobs (bookmark_id,title,url,kind,source_urls,mode,voice_a,voice_b,ppt,visual,status,output,created_at,started_at) VALUES (2,'TEST-XXX','https://example.com/v1','batch','','solo','台女','台男',1,0,'running','[OK] Podcast saved: /tmp/t_podcast.mp3',datetime('now'),datetime('now'))")
   c.commit();c.close()
   ```
   - `output` 塞 marker（`Raw saved`/`Script saved`/`Podcast saved`/`PPT saved`/`Visual summary saved`）控制 artifacts/進度顯示
   - 測進度：running + mp3 marker = 95%，+ ppt 勾選未產出 = 96%

2. **手機 viewport**（iPhone 13 尺寸）：
   ```js
   const { chromium, devices } = require('playwright');
   const browser = await chromium.launch({ headless: true, executablePath: EXEC, args: ['--no-sandbox'] });
   const context = await browser.newContext({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } });
   ```
   EXEC = `/opt/data/tmp/pw-browsers/chromium_headless_shell-1234/chrome-linux/headless_shell`

3. **開頁 + 進 notehub**：`page.goto(BASE)` → `page.locator('button.hamburger-btn').first().click()` → waitForTimeout(1500) → ☰ 打開自動切「工作進度」頁籤（`switchNhTab('progress')`）。等 job 載入再 waitForTimeout(2000)。

4. **DOM 驗證**（每項 print + failed++ 計數）：
   - 卡片數：`.nh-progress-item` count（預期 2 = #77 + #75）
   - checkbox：`.nh-checks input[type="checkbox"]` count + `:checked` count（容器是 `.nh-checks`，**不是** `.nh-artifacts` — 2026-08-06 踩過）
   - 檔案路徑：`details.nh-path-toggle summary` 文字含 `(N)`；展開後 `.nh-path` count + 含 `.pptx`
   - 百分比：`.nh-pct` 文字 + `.nh-bar-fill` style.width
   - 狀態標籤：`.nh-status` 含「處理中」

5. **截圖 + 自己看**：
   ```js
   await item.scrollIntoViewIfNeeded().catch(()=>{});
   await page.screenshot({ path: '/opt/data/tmp/nh_xxx.png' });
   ```
   然後 **vision_analyze 截圖**確認視覺（破版/勾選狀態/百分比）— 不只信 DOM。最後清理測試 job：`DELETE FROM notehub_jobs WHERE title LIKE 'TEST-%'`。

## 踩過的坑

- **selector 錯**：checkbox 容器 `.nh-checks` 非 `.nh-artifacts`（v15 第一次跑 0 個 checkbox）
- **手機模式**：不用 devices 時桌面版 layout 不同，驗證失真 — 一定要 `devices['iPhone 13']`（含 deviceScaleFactor，只設 viewport 截圖會糊）
- **測試 job 要清理**：忘了 DELETE 會污染真實 job 列表（截圖給使用者看時會出現 TEST- 卡）
- **hamburger 觸發**：`openNotehubSidebar()` 在 header；reload 後 localStorage SETUP_MODE flag 可能自動彈配置表格 — 測試前清 localStorage 或確認預期狀態

## 可複製範本

- **正式模板**：`templates/verify_notehub_ui.js`（skill 內建，含 JOB_TITLE_FILTER / EXPECT_* 常數 — 複製改常數即可）
- 歷史實例：`/opt/data/tmp/verify_v15_merge_card.js`（合併卡片）、`verify_v16_progress.js`（進度 96%）— 當參考
