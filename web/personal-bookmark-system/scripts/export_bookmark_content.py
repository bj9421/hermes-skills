#!/usr/bin/env python3
"""匯出書籤內容摘要為 markdown，供 graphify 掃描內容知識圖譜。

2026-08-05 新增：graphify 原本只掃 bookmark-manager 程式碼（AST）。
使用者要求也掃描「書籤內容摘要 + notehub 產出文字檔」→ 建立內容圖譜。

輸出：/opt/data/projects/bookmark-content-graph/
  bookmarks/     每筆書籤一檔（id-標題.md：標題+摘要+標籤+URL）
  notehub/       notehub 產出的 raw.md / script.md 副本

匯出內容不含敏感資料（無 xsec_token、無登入資訊）。
"""
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

DB = Path('/opt/data/projects/bookmark-manager/bookmarks.db')
OUT = Path('/opt/data/projects/bookmark-content-graph')
NOTEHUB_NOTES = Path('/opt/data/obsidian-vault/notes')
NOTEHUB_PODCAST = Path('/opt/data/obsidian-vault/口播')

def safe_name(s: str) -> str:
    """檔名安全化：去特殊字元，保留中文/英文/數字/-_。"""
    s = re.sub(r'[^\w\u4e00-\u9fff-]+', '-', s.strip())
    return s[:60].strip('-') or 'untitled'

def export_bookmarks():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, url, summary, tags, created_at, duration FROM bookmarks ORDER BY id"
    ).fetchall()
    conn.close()

    bm_dir = OUT / 'bookmarks'
    bm_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        title = row['title'] or '(無標題)'
        content = f"""# {title}

- **URL**: {row['url']}
- **標籤**: {row['tags'] or '(無)'}
- **收藏日期**: {row['created_at'] or ''}
- **時長**: {row['duration']} 秒

## 摘要

{row['summary'] or '(尚未補齊摘要)'}
"""
        fname = f"{row['id']:03d}-{safe_name(title)}.md"
        (bm_dir / fname).write_text(content, encoding='utf-8')
    return len(rows)

def copy_notehub():
    """複製 notehub 產出的文字檔（raw.md / script.md）副本。

    🔴 檔名可能含完整影片標題（超長）→ 直接 copy2 會 OSError: [Errno 36]
    File name too long。修法：用父目錄 hash 後 12 字元 + 原始檔名最後 30 字
    組合成 {hash}-{stem}.md，seen set 防重名。
    """
    nh_dir = OUT / 'notehub'
    nh_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    seen = set()
    for src_dir in (NOTEHUB_NOTES, NOTEHUB_PODCAST):
        if not src_dir.exists():
            continue
        for f in src_dir.rglob('*.md'):
            # 只複製 raw/script（逐字稿 + 整理稿），不複製其他
            if '_raw.md' in f.name or 'script.md' in f.name:
                parent_hash = f.parent.name[-12:]  # 影片 id hash 後 12 字元
                stem = f.stem[-30:]  # 檔名最後 30 字（含 .md 前的部分）
                dst_name = f"{parent_hash}-{stem}.md"
                # 避免重名衝突
                n = 1
                while dst_name in seen:
                    dst_name = f"{parent_hash}-{n}-{stem}.md"
                    n += 1
                seen.add(dst_name)
                shutil.copy2(f, nh_dir / dst_name)
                count += 1
    return count

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 清空舊匯出（避免 graphify 掃到過期檔案）
    for sub in (OUT / 'bookmarks', OUT / 'notehub'):
        if sub.exists():
            shutil.rmtree(sub)
    n_bm = export_bookmarks()
    n_nh = copy_notehub()
    print(f'匯出完成: bookmarks {n_bm} 筆, notehub 文字檔 {n_nh} 個 → {OUT}')

if __name__ == '__main__':
    main()
