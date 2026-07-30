---
name: bookmark-manager
description: "Bookmark Manager — 收到 `add2 <url>` 指令時，自動抓取網頁內容、LLM 摘要+分類標籤、存入 SQLite 收藏庫、回覆摘要卡。支援一般網頁、YouTube、IG、Bilibili、Google Maps。"
version: 1.0.0
author: Hermes
tags: [bookmark, bookmark-manager, add2,收藏]
---

# Bookmark Manager — `add2` 觸發流程

> 當使用者說 `add2 <url>` 時，執行以下流程。

## 觸發條件

使用者訊息以 `add2` 開頭，後面接著一個 URL。

```
add2 https://github.com/...
add2 https://maps.app.goo.gl/...
add2 https://youtube.com/...
```

## 執行步驟

### 1. 解析 URL

- 從訊息中提取 URL（第一個 http/https 連結）
- 判斷來源類型（webpage / location / youtube / instagram / bilibili）
  - Google Maps: `maps.google.`, `google.com/maps`, `goo.gl/maps`, `maps.app.goo.gl`
  - YouTube: `youtube.com`, `youtu.be`
  - Instagram: `instagram.com`
  - Bilibili: `bilibili.com`, `b23.tv`

### 2. 抓取內容

用 `anysearch extract` 或 `web_extract` 抓取頁面內容。

- 一般網頁：提取 title + 正文
- Google Maps 短網址：先用 `curl -sI -L` 解析最終 URL，從 URL path 提取地點名稱，再用 anysearch 搜尋補充資訊

### 3. LLM 摘要 + 標籤

根據抓到的內容，用當前 LLM 產生：
- **摘要**：100-200 字中文摘要
- **標籤**：3-5 個相關標籤（逗號分隔，如 `"AI,開源,工具,Hermes"`）

### 4. 存入 DB

用 bookmark-manager API 存入：

```bash
cd /opt/data/projects/bookmark-manager
HOME=/opt/data .venv/bin/python3 bookmark.py <url> \
  --title "..." \
  --summary "..." \
  --tags "tag1,tag2,tag3"
```

或直接 POST 到 `http://localhost:5001/api/bookmarks`。

### 5. 回覆摘要卡

格式：

```
📎 已收藏

標題：xxx
🏷️ #tag1 #tag2 #tag3
📝 摘要內容...
🌐 https://原始連結
```

### 6. 特殊處理

- **YouTube/IG/Bilibili**：bookmark 完成後多問一句「要順便送 notehub 處理嗎？」
- **Google Maps 地點**：自動標記為 `📍` 地點類型

## 注意事項

- Google Maps goo.gl 短網址需要先解析（`curl -sI -L`）才能拿到真實地點名稱
- `bookmark.py` script 在 `/opt/data/projects/bookmark-manager/bookmark.py`
- Web UI 在 `http://dietpi4:5001`
- Watchdog cron 每 5 分鐘檢查 server 狀態（無 Agent）
