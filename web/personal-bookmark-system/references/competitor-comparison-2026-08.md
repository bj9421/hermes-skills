# Competitor Comparison — Bookmark Manager (2026-08-05)

> 與主流自架/雲端書籤軟體的完整比較 + 後續功能建議。來源：anysearch 研究（TabMark/selfh.st/openalternative/Reddit 等 2026-08-05）。
> 用途：規劃新功能時查「哪個同類軟體有、可模仿什麼」。

## 我們 vs 同類（功能對照）

| 功能 | 本專案 | Linkwarden | Hoarder(Karakeep) | Wallabag | Shiori | Linkding | Readeck |
|---|---|---|---|---|---|---|---|
| LLM 自動摘要/標籤 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Telegram bot 收藏 | ✅ 獨家 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 來源標籤 30+ 平台 | ✅ 獨家 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 小紅書 DNS 繞封鎖 | ✅ 獨家 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| NoteHub 口播佇列 | ✅ 獨家 | ❌ | 影片存檔(partial) | ❌ | ❌ | ❌ | 影片轉錄(partial) |
| 簡轉繁 | ✅ 獨家 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 死鏈檢查 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 巢狀 collections | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **內容全文存檔** | ❌ 🔴 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **全文搜尋(內文)** | ❌ 🔴 | ✅ | ✅(Meilisearch) | ✅ | ✅ | ❌(僅 title/desc) | ✅ |
| **瀏覽器 bookmarklet/擴充** | ❌ 🔴 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wayback 備份 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 高亮 highlights | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| EPUB 匯出 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| RSS feed 輸出 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| e-reader 整合(KOReader) | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| OCR | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 原生 mobile app | ❌(PWA) | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| RAM 用量 | ~101MB | ~350MB | 重(多容器) | 中 | ~18MB | 極輕 | 輕 |

## 每個軟體的定位（一句話）

- **Linkwarden** — 最完整的自架替代（collections + 截圖 + Wayback + 協作），AGPL + PostgreSQL，350MB
- **Hoarder/Karakeep** — AI 資料倉庫（自動標籤 + OCR + 原生 app），最像我們的 AI 路線
- **Wallabag** — 稍後閱讀之王（e-reader/RSS/EPUB 生態），無 AI
- **Shiori** — 輕量 Pocket clone，核心賣點 = 全文存檔 + reader mode
- **Linkding** — 極簡（單 docker run），bookmarklet + 擴充最齊
- **Readeck** — 輕量，高亮 + EPUB + 影片轉錄
- **Raindrop.io** — 雲端標竿：collections、Permanent Copy、高亮、公開分享頁、AI 標籤（付費）

## 🔴 我們的缺口（同類有我們沒有）— 依建議優先序

### P0（低成本高價值）
1. **bookmarklet 一鍵收藏** — 一行 JS 拖到瀏覽器書籤列 → `POST /api/bookmarks`。模仿 Linkding。半小時搞定，立刻解決「手機/桌機看到好文要收藏很麻煩」。
2. **內容全文存檔** — `trafilatura`/readability 提取正文 → 存 Obsidian 或專屬目錄。死鏈防護 + 未來全文搜尋/EPUB 的地基。模仿 Shiori/Wallabag/Linkwarden。

### P1（中成本高價值）
3. **全文搜尋** — 存檔後建 FTS5 第二張表（trigram 已驗證可行）。模仿 Shiori。
4. **巢狀 collections** — `bookmarks.parent_id` + UI 資料夾樹。模仿 Linkwarden/Raindrop。
5. **Wayback 自動備份** — 死鏈檢查發現 broken 時抓 archive.org snapshot 當 fallback。模仿 Linkwarden。

### P2（有場景再做）
6. **RSS 輸出** — `/api/bookmarks/feed?tag=x` atom feed。模仿 Wallabag。
7. **EPUB 匯出** — 標籤批量打包電子書，Kobo/Kindle 離線讀。模仿 Readeck/Wallabag。
8. **高亮** — summary 延伸成段落級註記。模仿 Readeck/Raindrop。

### P3（單人使用不需要）
- 多使用者/SSO（協作）、原生 iOS/Android app（PWA 已夠）、OCR（書籤多為連結非圖片）

## 2026 生態背景

- **Pocket 2025-07 關閉** → 自架書籤需求暴漲（「你沒自架就不擁有資料」教訓）
- Omnivore 被 ElevenLabs 收購 → 開源稍後閱讀社群轉向 Wallabag/Readeck
- Linkwarden GitHub 19k stars、最快成長；Wallabag 12.9k（13 年歷史更成熟）
- 三個主力自架（Linkding/Shiori/Linkwarden）**全部沒有原生 mobile app** — PWA 是通用解

## 既有評估（deployment-and-migration.md 補充）

記憶體比較：bemarked 5-10MB / Shiori ~18MB / neonlink <50MB / Linkwarden ~350MB / 本專案 ~101MB。
結論（2026-08-02）：不值得換架構 — 我們的客製化功能（小紅書 DoH、bilibili 真實標籤、bot 排隊、LLM 簡轉繁、notehub 佇列、HTMX PWA）替代品全沒有。
