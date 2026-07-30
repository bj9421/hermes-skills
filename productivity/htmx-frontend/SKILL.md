---
name: htmx-frontend
description: "HTMX 前端開發規範 — 零自訂 JS 原則，所有互動走 hx-* 屬性。適用於 Flask + HTMX + SQLite 架構的內部工具開發。"
version: 1.0.0
author: Hermes
tags: [htmx, frontend, flask, pwa]
---

# HTMX 前端開發規範

> 適用於內部工具（bookmark-manager、dashboard 等）的 Flask + HTMX 前端。

## 核心原則

### 零自訂 JS

所有使用者互動必須用 HTMX 屬性完成：

- ✅ `hx-post` / `hx-get` — 取代 `fetch()`
- ✅ `hx-trigger` — 取代 `onclick` / `oninput` / `addEventListener`
- ✅ `hx-target` + `hx-swap` — 取代 DOM 操作
- ✅ `hx-on::after-request` — 取代 Promise `.then()`
- ❌ 不要寫自訂 async function
- ❌ 不要用事件監聽器
- ❌ 不要用 `fetch()` 呼叫後端

**例外**：一個行內 `onclick` 控制顯示/隱藏（如 toggle form）可以接受。

### 規格對齊

動手前先問：「HTMX 有沒有原生方式處理這個？」而不是寫完 JS 再回頭改。

### 路徑原則

- 內部工具一律用 **絕對 `/` 前綴路徑**（`/api/bookmarks`、`/static/style.css`）
- 若需掛在 reverse proxy 子路徑下（如 `/bm/`），所有 `/` 前綴路徑需改成相對路徑
- **最佳實踐**：HTMX 應用掛 proxy root `/`，不要用子路徑

## 常見模式

### 表單提交

```html
<form hx-post="/api/bookmarks" hx-target="#bookmark-list" hx-swap="outerHTML"
      hx-on::after-request="this.closest('#add-form').style.display='none'">
    <input type="url" name="url" required
           hx-post="/api/bookmarks/fetch-meta-form" hx-trigger="change delay:500ms"
           hx-target="#meta-fields" hx-swap="innerHTML">
    <button type="submit">儲存</button>
</form>
```

### 延遲觸發自動抓取

```html
<input name="url"
       hx-post="/api/endpoint" hx-trigger="change delay:500ms"
       hx-target="#result" hx-swap="innerHTML">
```

### 後端雙模式（JSON + HTML）

同一個 endpoint 偵測 `HX-Request` header 回傳不同格式：

```python
@app.route('/api/bookmarks', methods=['POST'])
def add_bookmark():
    # ... 處理邏輯 ...
    if request.headers.get('HX-Request') == 'true':
        return render_template('_partial.html', data=data)
    return jsonify({'ok': True})
```

## 架構樣板

Flask + HTMX + SQLite：

```
app.py          — Flask routes + SQLite
templates/
  index.html    — 主頁（head 含 manifest + SW）
  _partial.html — HTMX 局部片段
static/
  style.css
  htmx.min.js   — 本機載入（支援 PWA 離線快取）
  manifest.json — PWA manifest
  sw.js         — Service Worker
  pwa/          — PWA icons
schema.sql
```

## PWA 整合

- manifest.json：icons 路徑用絕對 `/static/pwa/` 前綴
- Service Worker：註冊 `/sw.js`，設定 `Service-Worker-Allowed: /`
- SW 用 network-first 策略（離線用 cache fallback）
- HTMX 必須下載到 `static/`（不能 CDN，否則離線 SW 抓不到）

## 相關技能

- `bookmark-manager` — 實際應用此規範的專案
