# Phase 5 多來源合成（NotebookLM 式）實測記錄

## 測試結果（2026-08-06）

### CLI `--synthesize` 參數解析 bug
- **現象**：`python -m notehub --synthesize url1 url2 --lang zh` 會把 `zh` 當成 source URL
- **根因**：原始實作只過濾 `--` 開頭，不跳過 flag 的值
- **修復**：改用 iterative scan with `skip_next` flag
- **驗證**：`args=['--synthesize','url1','url2','--lang','zh']` → `sources=['url1','url2']`

### 端到端實測（Job #32）
- **來源**：GitHub HA-POWERS + 上展芋圓莊 + Graphify YouTube
- **輸出**：
  - synthesis_report.md (3634 bytes) ✅
  - script.md (4004 bytes) ✅
  - podcast.mp3 (6MB) ✅
- **執行時間**：~5 分鐘（含 3 次 LLM fallback：Zen 429 → AGNES → Groq）
- **報告內容**：共通主題、各來源獨特觀點、差異與衝突、整體結論

### 重要觀察
1. 合成報告的 frontmatter `sources:` 欄位正確（不含 `zh`）
2. 報告標題無 `zh` 字眼
3. STDERR 無「來源處理失敗 zh」