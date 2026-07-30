---
name: hermes-web-apps
description: "構建 Hermes 管理的 Web App：Flask + HTMX（零自訂 JS）、PWA 支援、背景 enrich pipeline、Tailscale 部署。擷取自 bookmark-manager 專案的實戰經驗。"
version: 1.2.0
tags: [htmx, pwa, flask, tailscale, web-dev, telegram-bot]
---

# Hermes Web Apps — HTMX-first 開發準則

> 建立由 Hermes Agent 輔助管理的 Web 應用時，遵循以下模式。

## 核心原則：HTMX 優先，零自訂 JS

使用者明確要求 Web UI 功能**用 HTMX 實作**，禁止自訂 JS 函式。

### 可接受的 JS
- `onclick` 或 `hx-on` 單行屬性（顯示/隱藏切換）
- HTMX 本機載入（`/static/htmx.min.js`）
- 批次操作的 `fetch()` 呼叫（已知待改例外）

### HTMX 對照表

| 傳統 JS 寫法 | HTMX 替代方案 |
|-------------|--------------|
| `fetch('/api/x').then(updateDOM)` | `hx-post="/api/x" hx-target="#target" hx-swap="outerHTML"` |
| `input.addEventListener('input', debounce(fn))` | `hx-trigger="change delay:500ms" hx-target="#result"` |
| 手動建立 modal / dialog | 內聯 form + CSS 切換顯示，或用 `hx-swap="beforeend"` 插入 inline 表單 |
| `addEventListener('submit', e => { e.preventDefault(); ... })` | HTML form + `hx-post` 直接提交，後端回傳 HTML fragment |
| `location.reload()` 或手動 DOM 更新 | `hx-trigger="load"` / `hx-on::after-request` 觸發另一元件刷新 |

### 後端回傳原則

HTMX 端點（偵測到 `HX-Request` header）**回傳 HTML fragment** 而非 JSON：
- `hx-target` 指定的元素被 fragment 取代或附加
- 非 HTMX 請求仍可回傳 JSON（API 相容性）

```python
if request.headers.get('HX-Request') == 'true':
    return render_template('_partial.html', ...)
return jsonify({'ok': True})
```

## PWA 整合

### 必要檔案
- `static/manifest.json`：app 名稱、icons（192+512）、`display: standalone`、theme color
- `static/sw.js`：Service Worker，建議 network-first + cache fallback
- icons：用 Pillow 產生簡單圖示，放 `static/pwa/icon-{192,512}.png`

### Flask route
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

### HTML head
```html
<meta name="theme-color" content="#4f46e5">
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/pwa/icon-192.png">
```

### SW registration（放在 `</body>` 前）
```html
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js');
    });
}
</script>
```

## 背景 Enrich Pipeline

適用情境：Web UI 新增或 Telegram bot 收資料時不阻塞等 LLM，事後由 cron 補上。

### DB schema
```sql
ALTER TABLE table ADD COLUMN processed INTEGER DEFAULT 0;
-- 0=pending LLM, 1=done
```

### cron job（agent-driven）
- 掃 `processed=0` 的資料（每批 5 筆）
- 用 `curl -sL` 抓外部內容
- 若 title 為空先用 HTML `<title>` 補上
- LLM 產生摘要、標籤、補上缺少的欄位
- `UPDATE ... SET processed=1` 避免重複處理
- 抓不到內容或非 HTML：仍設 `processed=1`（避免死鎖）

```python
# 同步 tags 範例
for t in all_tags:
    conn.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
conn.execute('DELETE FROM tags WHERE name NOT IN (?)', current_tags)
```

### watchdog cron（no_agent=true）
純 script 檢查服務是否存活，死掉就重啟：

```python
def check_healthy():
    try:
        req = urllib.request.Request('http://localhost:5001/api/health')
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False
```

## Telegram Bot Bridge（stdlib-only 模式）

當需要一個**輕量獨立的 Telegram bot** 來收資料、不回 Hermes agent 時，用以下模式。

### 完整腳本範例

```python
#!/usr/bin/env python3
import urllib.request, json, re, logging, sys, time

TG_URL = 'https://api.telegram.org/bot'

def http_post(url, data, timeout=15):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def tg_call(token, method, **kwargs):
    url = f'{TG_URL}{token}/{method}'
    r = http_post(url, kwargs)
    return r.get('result', []) if r and r.get('ok') else []

def main():
    token = sys.argv[1]
    offset = 0
    while True:
        updates = tg_call(token, 'getUpdates',
            offset=offset, timeout=20,
            allowed_updates=['message', 'channel_post'])
        for update in updates:
            # process here
            offset = update['update_id'] + 1  # ALWAYS advance even on failure
        time.sleep(1)
```

### 生存檢查（watchdog）
- 用 `getMe` 或服務的 health endpoint 檢查
- watchdog 本身用 `no_agent=true` cron 定期檢查

### Pitfalls
- **Docker 環境沒有 requests**：stdlib urllib 才是可靠的
- **offset 不動 → 無限循環**：即使處理失敗也要 `offset = update['update_id'] + 1`
- **poll timeout**：`getUpdates` 的 timeout 參數（如 20s）必須低於 urllib 的 socket timeout（如 25s），否則 socket timeout 會提早打斷 long poll
- **1 token = 1 bot**：跟 Hermes gateway 用不同 token，避免 polling 衝突
- **OpenCode Zen API 403**：從 stdlib urllib 呼叫免 key endpoint 會回 403，改用 `http.client`（`HTTPSConnection`）即可繞過。原因不明但 `curl` 和 `http.client` 都正常，唯獨 `urllib.request.urlopen` 被擋。
- **http.client 用法**：`http.client.HTTPSConnection(host, timeout=N)` → `conn.request('POST', path, body, headers)` → `conn.getresponse()`。注意要設 `ensure_ascii=False` 處理中文。此方式也用於 Telegram bot 的即時 LLM 處理。
- **`import urllib.error` 必加**：`except urllib.error.HTTPError` 需要 `import urllib.error`，否則會 raise `AttributeError` 被 generic `except` 吞掉，HTTP 錯誤永遠進不了正確分支
- **Conflict: terminated by other getUpdates request**：同 token 兩個 long polling 同時跑會衝突。啟動新 bot 前先 `pkill -f <bot-script>` 殺乾淨。背景 process 即使 exit 也可能留下 session，需確認無殘留
- **sendMessage 回傳值解析**：`tg_call('sendMessage', ...)` 回傳 `[{...}]`，取 `result[0]['message_id']` 才能拿到已發送訊息的 ID 用於後續 `deleteMessage`
- **fetch_title 用 urllib 不要用 requests**：stdlib 版用 `urllib.request.Request(url, headers={'User-Agent': ...})`，timeout 設短（10s），失敗回空字串即可

## Tailscale Serve 部署

```bash
# 掛在 root（HTTPS 自動）
tailscale serve --bg --https 443 localhost:5001

# 其他 service 掛不同 port
tailscale serve --bg --https 8443 localhost:9119
```

- PWA 必須透過 HTTPS 才能註冊 Service Worker → Tailscale Serve 自動提供
- 瀏覽器 `https://dietpi4.taile76ad.ts.net/` 存取

## Pitfalls

- **不要用子路徑掛 PWA**：PWA manifest/SW 路徑會亂掉，除非全部改用相對路徑
- **HTMX form-urlencoded vs JSON**：HTMX 表單送 `form-urlencoded`，後端要用 `request.form` 也能接；API 請求仍可用 JSON
- **SW scope**：SW 放在 `/sw.js` 預設 scope `/`，設 `Service-Worker-Allowed: /` 確保能攔截全站
- **編輯功能 inline**：不要在卡片外開 modal，用 `hx-swap="beforeend"` 在卡片底部插入編輯表單。編輯送出後回傳 fragment 刷新列表。
- **enrich 失敗不要卡死**：設 `processed=1` 不管成功與否，使用者可在 Web UI 手動編輯修正
- **一鍵 enrich 端點**：每張卡片可獨立按 🤖 觸發 LLM 補齊。端點 `POST /api/bookmarks/<id>/enrich` 抓標題 → LLM 摘要+標籤 → 更新 DB → 回傳刷新列表。卡片上 ✏️ 編輯和 🤖 enrich 按鈕並列：`☆  🤖  🔴  📋  ✏️  🗑️`

## 相關檔案

- `references/bookmark-api.md` — Bookmark Manager API 文件
- `references/bookmark-bot.md` — @add2bm_bot Telegram bot 技術細節（啟動/停止/除錯）
