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
