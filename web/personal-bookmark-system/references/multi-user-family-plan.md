# Multi-User / Family Mode Plan (2026-08-05 評估)

> 狀態：✅ 決策已定案（「各自獨立」），尚未開工。fact #587 已同步。
> 決策紀錄：Obsidian `/我的筆記/開發架構/專案決策紀錄/bookmark-manager-family.md`

## 核心結論

**可行，家庭版 3-5 天；完整多人版 1-2 週。差別在砍掉兩塊最貴的：**

| 功能 | 完整多人版 | 家庭版 |
|------|-----------|--------|
| Telegram bot | 每 user 一 bot process + watchdog 管理 | ❌ 砍掉 — 共用同一 bot（靠 chat_id 分人）|
| LLM key | provider 抽象 + 加密儲存 | ❌ 砍掉 — 共用 server 的 key |
| 資料隔離 | user_id | user_id（核心，不可省）|
| 網頁登入 | Flask-Login | ⚠️ 可簡化或靠 bot 綁定 |

## 🔑 關鍵洞察：1 bot = N chat_id（不違反「1 token = 1 bot」）

Telegram bot 天生多人共用 — 家人搜尋 bot 名稱按 Start 就能用，**不需要**每人建新 bot。

- 「1 token = 1 bot」限制指的是 **process 數**（同 token 不能開兩個 process 同時 polling → Conflict）
- **不是**限制使用者數 — 一個 process 收到所有 chat 的訊息，靠 `update.message.chat.id` 分辨是誰
- 現有 bookmark-bot.py 就是單 process 多 chat_id 架構（Xun chat_id 745279221 只是第一個使用者）
- 實作 = DB 記 `chat_id → user` 對應 + **白名單**（未登記 chat_id 回「你不在允許清單」，擋陌生人）

## 家庭版實作範圍（約 3-5 天）

1. **DB**：bookmarks/tags/notehub_jobs 加 `user_id` + users 表（migration，2-3 天核心）
2. **Bot**：認得 N 個 chat_id → 各自存各自空間（1 天）
3. **網頁**：登入後區分使用者；或家庭共享視圖（卡片標「👨 爸爸收藏」）

## 決策：A（各自獨立）vs B（共享庫）

使用者 2026-08-05 選 **A：各自獨立** — 每個家庭成員書籤完全隔離。
- B 方案（共享一個庫 + owner 欄位當標籤）更省（~2 天），但不符合隱私需求。

## 風險

- **IDOR 資料外洩**：所有 query 必須加 `WHERE user_id=?`，漏一個就是跨使用者讀取 — 全站最高風險點
- SQLite + waitress 8 threads + WAL + busy_timeout 已就緒，10 人內無需換 PostgreSQL
- 每 bot +26MB（若未來走完整版）；RPi4 8GB 扛 5-10 人綽綽有餘

## 對照研究（2026-08-05 anysearch）

同類軟體共同點：Linkwarden/Hoarder/Wallabag/Shiori/Linkding/Readeck 都**沒有**我們的 Telegram bot、來源標籤 30+ 平台、小紅書 DNS 繞過、NoteHub 口播、簡轉繁。可模仿缺口：內容全文存檔、bookmarklet 一鍵收藏、巢狀 collections、全文搜尋、EPUB/RSS 輸出。
