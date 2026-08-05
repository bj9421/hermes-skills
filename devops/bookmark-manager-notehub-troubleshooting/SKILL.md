---
name: bookmark-manager-notehub-troubleshooting
description: 快速診斷 bookmark-manager NoteHub 問題：清佇列、檢查狀態、測試合成 API
---

# 🔍 快速診斷 bookmark-manager NoteHub 問題

## 檢查當前狀態
```bash
# 查 API 狀態
curl -s http://localhost:5001/api/notehub/jobs | python3 -m json.tool

# 查 DB 狀態
sqlite3 /opt/data/projects/bookmark-manager/bookmarks.db "SELECT id, status, kind, title FROM notehub_jobs ORDER BY id DESC LIMIT 5;"
```

## 清佇列
```bash
# 清 queued（處理中）
curl -s -X POST http://localhost:5001/api/notehub/jobs/clear -H "Content-Type: application/json" -d '{"scope":"queued"}'

# 清 done
curl -s -X POST http://localhost:5001/api/notehub/jobs/clear -H "Content-Type: application/json" -d '{"scope":"done"}'

# 清 failed
curl -s -X POST http://localhost:5001/api/notehub/jobs/clear -H "Content-Type: application/json" -d '{"scope":"failed"}'
```

## 常見問題

### 清佇列按鈕無效
- **原因**：只有 `queued` 才顯示「清佇列」按鈕，`done` 在「完成工作」頁籤
- **解決**：2026-08-06 修正：工作佇列頁籤也顯示「清已完成」按鈕

### 合成 job 不執行
- **檢查**：`/api/notehub/jobs` 看 pending count 是否 > 0
- **重啟 worker**：`kill <worker_pid>`，再重新啟動 bookmark-manager server

### CLI 測試合成
```bash
cd /opt/data/skills/media/youtube-note-pipeline/scripts
PATH=/opt/data/.venv/bin:$PATH python -m notehub --synthesize "https://example.com/1" "https://example.com/2" --lang zh
```

## 測試清單
- [ ] 117 tests 全綠
- [ ] 端到端測試通過（job #32）
- [ ] 清佇列按鈕功能正常