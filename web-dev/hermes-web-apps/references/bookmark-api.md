# Bookmark Manager API Reference

Base: `http://localhost:5001` / `https://dietpi4.taile76ad.ts.net/`

## Bookmarks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/bookmarks?tag=X` | HTMX fragment: bookmark list (filter by tag) |
| `GET` | `/stats` | HTMX fragment: stats + tag cloud |
| `POST` | `/api/bookmarks` | Add bookmark (JSON or form-urlencoded) |
| `PUT` | `/api/bookmarks/<id>/update` | Update title/summary/tags |
| `DELETE` | `/api/bookmarks/<id>` | Delete bookmark |
| `POST` | `/api/bookmarks/<id>/star` | Toggle star |
| `POST` | `/api/bookmarks/<id>/read` | Toggle read status |
| `POST` | `/api/bookmarks/fetch-meta` | JSON: fetch page title from URL |
| `POST` | `/api/bookmarks/fetch-meta-form` | HTMX: returns <input> form with auto-filled title |

## Batch

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/bookmarks/batch` | Batch delete / add-tag / remove-tag / star / read / export / copy-summary / send-notehub |

## Tags

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tags` | Tag management page (standalone) |
| `POST` | `/api/tags` | Rename tag |
| `DELETE` | `/api/tags/<name>` | Delete tag from all bookmarks |
| `POST` | `/api/tags/merge` | Merge source tag into target tag |

## PWA

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/manifest.json` | PWA manifest |
| `GET` | `/sw.js` | Service Worker |

## DB Schema

```sql
bookmarks: id, url, title, summary, tags, source, item_type,
           coordinates, favicon_url, starred, read_status,
           processed, created_at
tags: id, name
```

- `item_type`: `'link'` (webpage) or `'location'` (Google Maps)
- `source`: `'webpage'`, `'location'`, `'youtube'`, `'instagram'`, `'bilibili'`
- `processed`: `0` (pending enrichment) / `1` (done)

## 注意

- 所有 HTMX 請求回傳 HTML fragment
- 非 HTMX 請求回傳 JSON
- enrich cron 每 10 分鐘掃 `processed=0` 補摘要+標籤+標題
