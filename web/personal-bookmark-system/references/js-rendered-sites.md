# JS-Rendered Sites — Bilibili / 小紅書 Enrich 處理

## 問題背景

Bilibili 和小紅書都是 SPA，需要 JavaScript 渲染。普通 curl 無法抓取內容，會導致 LLM 生成「無法提供摘要」的 AI 幻覺。

## 解決方案

在 `llm_enhance.py` 新增 `should_enrich()` 檢查：

```python
def should_enrich(url: str) -> bool:
    if 'bilibili.com' in url or 'b23.tv' in url:
        return False
    if 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return False
    return True
```

在 `normalize_source_tags()` 新增小紅書：

```python
if any(dom in url for dom in ['xiaohongshu.com', 'xhslink.com']):
    return '小紅書'
```

## API 行為

- `POST /api/bookmarks` → Bilibili/小紅書只設 source tag，無摘要
- `POST /api/bookmarks/<id>/enrich` → 回傳 `{ok: true, skipped: true, reason: 'JS-rendered site'}`

## Git Commits

- `da383b9` — fix: skip enrich for Bilibili + Xiaohongshu
- `3b4e380` — fix: enrich endpoint returns {skipped: true}
- `c8abd23` — fix: add Xiaohongshu tag normalization
