# Session Reference: bookmark-manager PWA + HTMX 實作

> 2026-07-30 session。bookmark-manager @ port 5001 加入 PWA + HTMX 零 JS 表單 + Tailscale Serve 多路徑。

## 背景 Enrich 架構

- Web UI 新增 → processed=0 → cron `every 10m`（agent-driven）掃描未處理書籤
- 每筆用 curl 抓頁面 → LLM 摘要 + 標籤 → UPDATE DB + sync_tags
- 最多 5 筆/run，失敗的 summary 留空但 processed=1（避免重試）

## Key 實作細節

### POST /api/bookmarks 改為雙模式
```python
data = request.get_json(silent=True) or request.form.to_dict()
```
HTMX 送 form-urlencoded，需要 `request.form` 備援。

### HTMX 偵測回傳 HTML
```python
if request.headers.get('HX-Request') == 'true':
    return render_template('_bookmark_list.html', ...)
```

### Tailscale Serve 陷阱
- 第一次設了 `localhost:5001` → 掛在 `/`，無法再加第二個路徑
- 解法：`tailscale serve --https=443 off` 清掉，再用 `--set-path=/xxx` 逐個加
- 後端要用 `http://`（Tailscale 管 SSL）

### PWA SW Scope 陷阱
- `/static/sw.js` 的 scope 只到 `/static/`，無法攔截頁面請求
- 解法：Flask route 在 `/sw.js` 加 `Service-Worker-Allowed: /` header
