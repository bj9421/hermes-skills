# Bookmark Manager 規模極限與分頁設計（2026-08-02 實測）

## 實測數據（測試 DB，不碰真實資料）

用假書籤插入測試 DB + Flask test client 量「使用者實際感受到」的完整回應時間：

| 書籤數 | DB 大小 | SQL 主列表200 | SQL 全列表 | SQL 標籤篩選 | HTTP 首頁 | HTTP 標籤篩選 |
|--------|---------|--------------|------------|--------------|-----------|---------------|
| 1,000  | 552 KB  | 2.8 ms       | 14.6 ms    | 6.6 ms       | 0.6 s     | 0.14 s        |
| 10,000 | 4.5 MB  | 3.1 ms       | 151.6 ms   | 71.4 ms      | 5.1 s     | 1.6 s         |
| 50,000 | 22 MB   | 7.0 ms       | 795.0 ms   | 377.8 ms     | **28.2 s**| 8.5 s         |
| 100,000| 45 MB   | 8.2 ms       | 1554.9 ms  | 765.1 ms     | **57.0 s**| 18.7 s        |

## 關鍵結論

1. **SQLite 不是瓶頸**：100k 筆全列表 SQL 只要 1.5 秒。tag LIKE 篩選 100k 筆 765ms 也還能用。
2. **真正的瓶頸是 HTML 渲染 + 傳輸**：主頁渲染**全部**書籤（routes 的 `index()` / `bookmarks_partial()` 都沒有 LIMIT）。100k 筆 = 541MB HTML，經 Tailscale 傳手機再渲染 → 57 秒。
3. **實用範圍：10,000 筆內完全沒問題**（首頁 5 秒內）。**延遲臨界點約 5,000–10,000 筆**。50,000+ 直接卡死。
4. **個人使用情境**：每天存 10 筆 → 1 萬筆要 3 年、5 萬筆要 13 年。短期（1–2 年）完全不用擔心。
5. 惡性循環因素：前端每 30 秒自動刷新（`hx-get` reload）會重渲染整頁 → 規模大時每 30 秒卡一次。

## 未來分頁設計（已與使用者確認方向，未實作）

### 需求（使用者確認）：分頁時篩選條件必須一直套用
- 選 youtube 標籤 → 跳第 2/3 頁 → 必須還是 youtube 的結果。
- URL 形式：`/bookmarks?tag=youtube&page=2` — 分頁連結要把 `tag`（還有 search/starred/read/type）一起帶上。

### 設計原則
- 分頁大小：**50 筆/頁**（50 筆約 250KB HTML，手機秒開）。
- 每個分頁連結都是 `hx-get="/bookmarks?<所有現有篩選參數>&page=N"` — 跟現有標籤高亮同一套狀態保留機制（見 SKILL.md「標籤篩選」章節三件套）。
- 路由加 `page` 參數：`LIMIT 50 OFFSET (page-1)*50`。
- 邊界處理：`page` 超界夾回範圍（只有 3 頁按到 5 → 回第 3 頁）；刪除最後一筆後目前頁空了 → 往前退一頁。
- 切換標籤時 page 要 reset 回 1（新篩選從頭開始）。
- 30 秒自動刷新要保留目前 page + 篩選。

### 若標籤篩選也要優化（萬筆後才需要）
目前 `tags LIKE` 全表掃描（無 index 可用），100k 筆 765ms。可改 SQLite FTS5 或 bookmarks_tags 關聯表。不急，10k 內 LIKE 夠快。

## 量測方法（可重現）

1. 建測試 DB：`shutil.copy` 真實 DB 到 `/tmp`，`executemany` 插入假書籤（title ~50字、summary ~300字、tags 3-8 個、網域混合 youtube/github/medium/b23.tv/xhslink）。
2. SQL 層：直接 sqlite3 量 `ORDER BY created_at DESC LIMIT 200` / 全列表 / tag LIKE 篩選 / COUNT。
3. HTTP 層：用 Flask test client 打 `/` 和 `/bookmarks?tag=AI`（monkeypatch `db.get_db` 指向測試 DB），量完整回應時間 + 回應大小。
4. ⚠️ 測試 DB 用完立即刪除，確認真實 DB 筆數不變。
5. ⚠️ 測試腳本放專案目錄（HERMES_WRITE_SAFE_ROOT 限制 /tmp 外寫入），用完刪除。
