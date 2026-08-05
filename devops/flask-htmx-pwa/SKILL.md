---
name: flask-htmx-pwa
description: "Flask + HTMX + PWA + Tailscale Serve 一體化部署：HTMX-first 零 JS 原則、PWA manifest/SW/icons 建置、Tailscale Serve path routing 設定。適合任何需要手機可裝、區域網內 HTTPS 的輕量 Web 服務。"
version: 1.0.0
author: Hermes
tags: [flask, htmx, pwa, tailscale, web]
---

# Flask + HTMX + PWA 部署模式

> 在 Hermes 環境（Docker container on RPi4）中，建立一個可從 Tailscale tailnet 內 HTTPS 存取、可安裝為手機 PWA 的輕量 Web 服務。

---

## 🔴 核心原則：HTMX-first，零自訂 JS

Web UI 所有互動必須走 HTMX。禁用 `fetch()` / `XMLHttpRequest` / 自訂 async 函式。

唯一可接受的 JS：inline `onclick` 控制顯示/隱藏（一行 HTML 屬性）。

### 實作檢查清單

- [ ] 表單提交 → `hx-post` + `hx-target` + `hx-swap`
- [ ] 自動觸發 → `hx-trigger="change delay:500ms"`
- [ ] 局部更新 → `hx-target="#element"` + `hx-swap="innerHTML"`
- [ ] 表單編碼 → 後端接受 `request.form.to_dict()` 備援（HTMX 送 form-urlencoded）

---

## PWA 建置步驟

### 1. 產生圖示

```python
# scripts/gen_icons.py
from PIL import Image, ImageDraw
# 產生 192x192 + 512x512 透明背景圓角矩形圖示
```

### 2. 加入必要檔案

```
static/manifest.json    → {name, short_name, start_url, display:"standalone", icons}
static/sw.js            → Service Worker（network-first + cache fallback）
static/htmx.min.js      → 本機載入（離線快取用）
static/pwa/icon-192.png → PWA 圖示
static/pwa/icon-512.png → PWA 圖示
```

### 3. HTML 修改

```html
<!-- <head> 內 -->
<meta name="theme-color" content="#4f46e5">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/pwa/icon-192.png">
<script src="/static/htmx.min.js"></script>  <!-- 非 CDN -->

<!-- </body> 前 -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js');
    });
}
</script>
```

### 4. Flask 路由

```python
@app.route('/manifest.json')
def pwa_manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def pwa_sw():
    resp = app.send_static_file('sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'  # root scope 才可攔截頁面
    return resp
```

---

## Production Server（waitress）與 access log

Flask dev server 不適合長期運行（debug reloader 改檔即重啟、單執行緒排隊）。改用 waitress：

```python
from waitress import serve
serve(app, host='0.0.0.0', port=5001, threads=8)
```

🔴 **waitress 不打 access log**（werkzeug dev server 會印、waitress 不會）→ 升級後手機請求全部無記錄，使用者報「某時間點頁面掛掉」時無法查證。需自加：

```python
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', filename='/tmp/app.log')

@app.after_request
def log_access(response):
    logging.getLogger('access').info('%s %s %s', request.remote_addr, request.method, request.path)
    return response
```

## PWA 快取更新紀律（2026-08-02 + 2026-08-05 實戰教訓）

sw.js 用 network-first + cache fallback：**server 資料已修好、手機仍顯示舊內容 = PWA 快取，不是 server 掛掉**。

診斷：`curl http://localhost:PORT/ | grep <新內容>` 對比使用者截圖 — server 新、手機舊 → 快取問題。

修法：bump `sw.js` 的 `const CACHE = 'bookmark-manager-v1'` → `'bookmark-manager-v2'`，手機下次載入新 sw.js 自動清舊快取。任何 UI 內容/樣式改版都應 bump 版本，否則使用者會一直看到舊畫面並回報「掛掉了」。

### 🔴 service worker「先舊後新」陷阱（2026-08-05）

bump CACHE 版本後，手機**不會立刻顯示新版** — service worker 更新是兩段式：
1. 第 1 次載入頁面：瀏覽器抓到新 sw.js 並**安裝**，但畫面仍由**舊 sw** 服務（回舊快取）
2. 第 2 次載入頁面：新 sw 才**接管**（activate + clients.claim），顯示新版

所以引導使用者「**重新整理頁面 2 次**」是標準動作；還不行才請使用者清除網站資料。bump 一次 CACHE 版本就夠（activate 內 `caches.keys().filter(k => k !== CACHE)` 會清掉所有舊版）。

### ✅ 頁尾版本號 — 快取診斷標竿（2026-08-05）

在頁尾放 `<footer class="app-footer" id="app-version">bookmark-manager <b>v4</b> · 版面描述</footer>`，版本號與 sw.js CACHE 同步。使用者回報「還是舊畫面」時，先問頁尾顯示什麼版本 → 立即判斷是快取沒更新還是 server 沒重啟，不用猜。CSS：小字、置中、`color: var(--muted)`、border-top，不搶版面。

---

## Flask+SQLite 測試 pattern（2026-08-03 實戰）

Flask app 上 pytest 前先處理三件事（否則測試卡真實網路/LLM、或 database locked）：

1. **每測試獨立臨時 DB**：`tempfile.mkdtemp()` → 覆寫 `db.DB_PATH`（import app **前**）→ `db.init_db()` → yield app → cleanup（unlink db/-wal/-shm）。完整範本見 `templates/conftest_flask_sqlite.py`
2. **autouse fixture monkeypatch 所有外部副作用**：`fetch_title`/`llm_enhance`/`extract_favicon` 回傳空、背景 worker（`_ensure_worker`）no-op — worker thread 會佔住臨時 DB → **database locked**
3. 測 route 用 `app.test_client()`；測 HTMX 分支帶 `headers={'HX-Request': 'true'}`

🔴 **HTMX 端點回傳陷阱**：任何可能被 HTMX `hx-post` + `hx-target` 呼叫的端點，必須依 `request.headers.get('HX-Request') == 'true'` 分流 — HTMX 回 HTML fragment（回 JSON 會把 JSON 字串塞進 swap 目標），API/bot 才回 JSON。bookmark-manager 的 enrich、add_bookmark duplicate 都踩過此坑。

---

## Tailscale Serve 設定

在 RPi **host** 上執行（Docker 容器內無 tailscale CLI）：

```bash
# 單一服務（root path）
tailscale serve --bg --https 443 http://localhost:5001

# 多服務 path routing（--set-path 語法）
tailscale serve --https=443 off                                    # 先清空
tailscale serve --bg --https=443 --set-path=/ localhost:5001       # 主要服務
tailscale serve --bg --https=443 --set-path=/dashboard localhost:9119  # 第二服務
```

### 規則
- SSL 由 Tailscale 終止，後端必須用 `http://` 非 `https://`
- `--set-path=/xxx` 將服務掛在子路徑下
- `.ts.net` 域名僅在 tailnet 內可解析（需安裝 Tailscale client）
- 手機安裝 Tailscale 後可用 `https://machine-name.xxx.ts.net/` 存取
