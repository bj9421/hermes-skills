---
name: personal-bookmark-system
description: 自架書籤管理系統（Flask + HTMX + PWA + Telegram Bot + LLM 自動補齊）
trigger: 使用者提及 bookmark-manager、書籤管理、add2、URL收藏、bookmark-bot、@add2bm_bot
---

# Personal Bookmark System

Flask + HTMX 自架書籤管理系統，支援 PWA、Telegram bot 一鍵收藏、LLM 自動補摘要與標籤。

## 架構

```
Web UI (Flask+HTMX) ←→ bookmark-manager API ←→ bookmarks.db (SQLite)
                                         ↑
Telegram Bot (@add2bm_bot) → POST /api/bookmarks
                                    ↓
                    cron/enrich → OpenCode Zen LLM → 摘要+標籤
```

## Web UI (Flask + HTMX)

- **Port**: 5001
- **DB**: `/opt/data/projects/bookmark-manager/bookmarks.db`
- **主路由**: `/` (列表), `/stats` (統計), `/api/bookmarks` (CRUD)

### 卡片操作按鈕順序（_bookmark_list.html）

```
☆ 🤖 🔴/✅ 📋 ✏️ 🗑️
```

### Batch 操作（index.html）

選取後出現 batch bar，操作完成後呼叫 `refreshWithDelay()`（3 秒延遲）：

```js
function refreshWithDelay() {
    setTimeout(() => {
        htmx.trigger('#bookmark-list', 'load');
        htmx.trigger('#stats-card', 'load');
    }, 3000);
}
```

### 編輯功能

- `GET /api/bookmarks/<id>/edit-form` → 回傳 inline edit form (HTMX fragment)
- `PUT /api/bookmarks/<id>/update` → 更新 title/summary/tags
- 使用 `hx-get` 載入表單，`hx-put` 送出

### LLM 自動補齊（🤖 按鈕）

- `POST /api/bookmarks/<id>/enrich`
- 抓 title → 呼叫 OpenCode Zen API → 更新 summary + tags + processed=1
- 使用 `http.client`（非 urllib，因 OpenCode 會擋 urllib → 403）

## Telegram Bot (@add2bm_bot)

輕量 bot，零依賴（stdlib only）。

### 路徑

- 腳本: `/opt/data/.hermes/scripts/bookmark-bot.py`
- Token: `/opt/data/.bookmark-bot-token`
- Watchdog: `bookmark-bot-watchdog.py` (cron 每 5 分鐘)

### 坑

- **urllib.request 連 OpenCode Zen 會 403** → 改用 `http.client.HTTPSConnection`
- **Bot token 不能重複 polling** → 同 token 開多個 process 會 Conflict error
- **getUpdates offset 必須永遠前進** → 即使處理失敗也要 `update_id + 1`，避免無限循環

### 啟動

```bash
exec python3 /opt/data/.hermes/scripts/bookmark-bot.py "$(cat /opt/data/.bookmark-bot-token)"
```

## 標籤強制規範（normalize_source_tags）

來源強制統一，避免 LLM 隨意產生不同寫法：

```python
def normalize_source_tags(url, tags):
    if any(dom in url for dom in ['bilibili.com', 'b23.tv']):
        return 'bilibili'
    return tags
```

同步在三個地方：
1. `app.py` enrich endpoint
2. `bookmark-bot.py` LLM 處理後
3. cron enrich prompt

## LLM enrichment cron

- 每 10 分鐘掃 `processed=0` 的書籤
- 抓頁面 → LLM 摘要+標籤 → 更新 DB
- Bilibili 來源需強制設 tag = "bilibili"

## Tailscale Serve

```bash
tailscale serve --https=443 off
tailscale serve --bg --https=443 localhost:5001
```

## PWA

- `manifest.json`, `sw.js` 在 `static/`
- `Service-Worker-Allowed: /` header 必須設
- 子路徑部署時所有 URL 必須用相對路徑（無前綴 `/`）

## 重構/拆分前的強制工作流（使用者明確要求）

大型拆分（如把 app.py 拆成多模組）**動手前必須依序**：

1. **確認 git 開啟、工作區乾淨** — `git status --short`，確保可隨時 `git checkout HEAD` 回滾
2. **列出拆分計劃給使用者確認** — 目標結構、搬哪些函數、哪些檔案不動，等使用者點頭
3. **建立 checkpoint list（todo）** — 每步動作 + 驗證方式 + 通過標準；每完成一步 `git commit`（繁體中文訊息）
4. **確認後才開始改碼**；任何一步驗證失敗 → `git checkout` 回滾，不硬撐

graphify 掃描顯示 app.py 曾有 766 行 / 53 函數、cohesion 0.10（全專案最弱），圖譜建議拆成 `db.py` + `llm_enhance.py` + `routes_bookmarks.py` + `routes_tags.py`，app.py 瘦身成 blueprint 註冊 + startup（<50 行）。bookmark.py（cohesion 0.39）是良好範本。拆完用 curl 驗證所有端點無回歸。
