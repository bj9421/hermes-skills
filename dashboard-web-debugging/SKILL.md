---
name: dashboard-web-debugging
description: "Debug web dashboard issues: API endpoints, JS errors, CORS, fetch patterns, Canvas/D3 rendering, and Flask frontend-backend integration."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, dashboard, web, flask, javascript, canvas, d3]
---

# Dashboard Web Debugging

## Overview

Debug web dashboards where a Flask/Python backend serves a static HTML/JS frontend. Covers API issues, JavaScript errors, Canvas/D3 rendering bugs, and frontend-backend data flow problems.

## Common Pitfalls

### 1. fetchWithTimeout Returns Parsed JSON, Not Response Object

When a custom `fetchWithTimeout` helper resolves with `.json()`, the return value is a **parsed JSON object**, not a `Response` object.

```javascript
// WRONG — .ok and .json() don't exist on JSON objects
if (res.ok) { const data = await res.json(); ... }

// CORRECT — check the JSON structure directly
if (res && res.success) { const data = res.data; ... }
```

**Symptoms:** `undefined` appearing in UI, silent failures, entire sections blank.
**Debug:** `console.log(typeof res, res)` — if it's `"object"` but has no `.ok` / `.status`, it's already parsed JSON.

### 2. Canvas API Compatibility

Older browsers (especially mobile Safari) don't support newer Canvas methods:

```javascript
// roundRect is 2021+, may not be available on older browsers
ctx.roundRect(...); // CRASH

// Safe pattern: try-catch fallback
try {
  ctx.roundRect(x, y, w, h, r);
} catch(e) {
  ctx.rect(x, y, w, h);
}
```

**Always check browser compatibility** before using newer Canvas APIs. Test on mobile Safari specifically.

### 3. API Route Not Registered

Flask returns 404 for valid endpoints when routes are defined but not registered:

```python
# Defined in screener_api.py but never called in app.py
from screening.screener_api import register_screener_routes
register_screener_routes(app)  # ← Must call this!
```

**Debug:** `curl http://localhost:5000/endpoint` — if 404, check route registration.

### 4. Missing Null Safety

Frontend crashes when API returns unexpected structure:

```javascript
// WRONG — no null check
stratRes.strategies.forEach(s => { ... });  // CRASH if stratRes is null

// CORRECT — guard against null
if (stratRes && stratRes.strategies) {
  stratRes.strategies.forEach(s => { ... });
}
```

### 5. Health Endpoint Returns Empty Body

A health check that only returns `{"status": "healthy"}` gives frontend no data to display. Always include structured `error_monitor` or equivalent:

```python
# Good health endpoint
return jsonify({
    "status": "healthy",
    "timestamp": datetime.now().isoformat(),
    "error_monitor": {
        "total_errors": 0,
        "alerts_triggered": 0,
        "latest_data_date": latest,
        "latest_data_rows": rows
    }
})
```

### 6. Date Formatting in Frontend

`toLocaleString('zh-TW')` uses 12-hour format by default. For 24-hour:

```javascript
// 12-hour (default)
new Date(ts).toLocaleString('zh-TW')  // "下午11:34:10"

// 24-hour
new Date(ts).toLocaleString('zh-TW', {
  hour: '2-digit', minute: '2-digit', second: '2-digit',
  hour12: false
})  // "23:34:10"
```

## Debugging Workflow

### Step 0: jsdom ≠ 真實瀏覽器（HTMX/reload 競態必用 Playwright）

jsdom **不執行外部 `<script src="...">`**（如 htmx.min.js）→ `htmx:afterSwap` 等事件永遠不觸發 → reload 競態測不出。**jsdom 通過 ≠ 已驗證**，尤其頁面含 HTMX / 第三方 script 時。

涉及 **reload / 非同步載入 / DOM 元素順序 / Service Worker** 的 bug，用 Playwright headless Chromium 當重現工具：

```bash
# RPi4/Docker 安裝配方（PLAYWRIGHT_BROWSERS_PATH 必須指到可寫目錄）
cd /opt/data/tmp && npm init -y && npm install playwright
PLAYWRIGHT_BROWSERS_PATH=/opt/data/tmp/pw-browsers npx playwright install chromium
# executablePath 不是 chrome-headless-shell！正確：
#   /opt/data/tmp/pw-browsers/chromium_headless_shell-1234/chrome-linux/headless_shell
```

診斷三招（比猜快一百倍）：
1. `page.on('pageerror', err => console.log(err.stack))` — 直接定位崩潰函數 + 行號
2. 攔截 `document.getElementById`（addInitScript，回傳 null 時印出 id + stack）— 鎖定哪個元素在何時不存在
3. 看 DOM 載入順序：htmx `hx-trigger="load"` 的 swap 可能早於 body 底部元素被 streaming parse → `getElementById` 回 null → `.innerHTML` 崩潰 → UI 元素「消失」

**常見競態修法**：存取 DOM 前檢查元素存在，不存在則等 `DOMContentLoaded` 再 retry（一次性 flag 防重複觸發）。

**工作流鐵律**：修完 code 自己跑真實瀏覽器實測、看到通過證據再回報 — 不讓使用者當白老鼠。同一個 bug 修 2 次以上沒好 → 停，提高驗證層級，不要在同一個猜測循環打轉。

### Step 1: Check Backend API First

```bash
curl http://localhost:5000/health
curl http://localhost:5000/api/heatmap
curl http://localhost:5000/screen/strategies
```

If API returns 404 or wrong data → fix backend first.

### Step 2: Check Browser Console

```javascript
// In browser DevTools console:
console.log(window.location.origin);  // Check API base
fetch('/health').then(r => r.json()).then(d => console.log(d));
```

Look for:
- `Uncaught TypeError: Cannot read properties of null`
- `undefined` in rendered UI
- CORS errors
- Network failures

### Step 3: Verify Frontend Data Binding

Check that frontend variables match backend JSON structure:
- `res.ok` → should be `res.success` (if fetch helper parses JSON)
- `res.data` → check nested keys match API response
- Array lengths → handle empty arrays gracefully

### Step 4: Test on Target Device

Mobile browsers differ from desktop:
- Canvas API support varies
- Touch events vs click events
- Screen size affects layout calculations
- Always test on the actual target device

## Tools Reference

| Tool | Purpose |
|------|---------|
| `curl` | Test API endpoints directly |
| `browser_console` | Check JS errors and logs |
| `browser_vision` | Visual verification of rendered UI |
| `read_file` | Inspect frontend JS/HTML |
| `search_files` | Find function definitions and API routes |

## Mobile Map UI Pitfalls

See `references/mobile-map-ui-lessons.md` for detailed case studies.

### Unicode Normalization
Database may store Chinese characters in traditional form (`臺北市`) while JS lookup keys use simplified (`台北市`). **Always add a normalization function** and apply it at the boundary.

### Marker-ID Binding
Store `marker.hotelId = hotel.id` when creating Leaflet markers. Never use `findIndex(() => true)` — it always returns 0.

### Mobile Marker Visibility
Circle markers need `radius >= 10`, `weight >= 2`, `fillOpacity >= 0.9` to be clickable on mobile screens.

### Responsive Layout Pattern
- Desktop: side-by-side (sidebar | map)
- Mobile: map-fullscreen + collapsible sidebar (slides up from bottom)
- Use `.collapsed` class toggled via media queries, not JS

### Location Detection: GPS + IP Fallback Pattern
When a web app needs user location, **always use a two-tier approach**:

1. **Tier 1: `navigator.geolocation`** (browser GPS API)
   - Works on HTTPS or `localhost` / `127.0.0.1`
   - **Does NOT work on arbitrary LAN IPs** (e.g., `192.168.x.x:5000`) — browsers block it
   - Requires user permission (prompts dialog)

2. **Tier 2: IP-based reverse geocoding** (fallback)
   - Call from **frontend** (not backend) — e.g., `fetch('http://ip-api.com/json/?lang=zh-TW')`
   - **Never call from Flask backend inside Docker** — container has no outbound internet to external APIs
   - Uses the client's real public IP, no permission needed
   - Returns city name; map to your app's city list

**Implementation pattern:**
```javascript
function getUserCity() {
    if (!navigator.geolocation) {
        useIpFallback();  // No GPS support at all
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => { /* use GPS coords */ },
        () => { useIpFallback(); },  // Auto fallback on any GPS failure
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
}
```

**Common GPS error codes:**
- `PERMISSION_DENIED` — user blocked location
- `POSITION_UNAVAILABLE` — GPS hardware/network unavailable
- `TIMEOUT` — took too long to locate

**UI feedback:** Button states: `📍 我的位置` → `⏳ 定位中...` → `📍 城市名` (green) or `📍 定位失敗` (red, auto-reset)
