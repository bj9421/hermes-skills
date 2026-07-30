# PWA 完整設定步驟（Flask + HTMX）

> 用於將 Flask + HTMX 內部工具變成可安裝的 PWA。

## 必要檔案

| 檔案 | 用途 | 位置 |
|------|------|------|
| `manifest.json` | App 名稱、圖示、顯示模式 | `static/manifest.json` |
| `sw.js` | Service Worker：離線快取 + 安裝行為 | `static/sw.js` |
| `icon-192.png` | PWA 必需圖示 | `static/pwa/icon-192.png` |
| `icon-512.png` | PWA 必需圖示 | `static/pwa/icon-512.png` |

## Flask 路由

```python
@app.route('/manifest.json')
def pwa_manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def pwa_sw():
    resp = app.send_static_file('sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp
```

## HTML head

```html
<meta name="theme-color" content="#4f46e5">
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/pwa/icon-192.png">
```

## Service Worker

Network-first 策略：正常時快取，離線時回退至快取。

```js
const CACHE = 'bookmark-manager-v1';
const PRECACHE_URLS = ['/', '/static/style.css', ...];

self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        const clone = response.clone();
        caches.open(CACHE).then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
```

## 圖示生成

用 Pillow 生成（範例：`scripts/gen_icons.py`）：

```python
from PIL import Image, ImageDraw

def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([...], radius=size*0.18, fill=(79,70,229))
    img.save(f'static/pwa/icon-{size}.png', 'PNG')
```

## 重要限制

- ⚠️ PWA 需要 HTTPS（Tailscale Serve 自動提供）
- ⚠️ Service Worker 只能在安全上下文註冊（HTTPS 或 localhost）
- ⚠️ manifest 和 SW 路徑必須用絕對 `/` 前綴（若掛 proxy root）
- ⚠️ HTMX 必須下載到 `static/htmx.min.js`，不能用 CDN（SW 無法快取跨域請求）

## Tailscale 整合

Tailscale Serve 自動提供 HTTPS 憑證，PWA 可直接安裝：

```bash
# host 端
tailscale serve --bg --https 443 http://localhost:5001
```

瀏覽器開 `https://dietpi4.taile76ad.ts.net/` → Safari「分享」→「加入主畫面」
