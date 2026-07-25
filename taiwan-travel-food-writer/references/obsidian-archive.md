# 網頁資料歸檔至 Obsidian — 轉換工作流

將網頁抓取資料（HTML、RSS）轉換為 Obsidian Markdown 筆記並歸檔。

## 前置

```bash
uv pip install html2text
# 若 pip 不可用，用 uv（Hermes Docker 環境）：
XDG_CACHE_HOME=/opt/data/.cache uv pip install html2text
```

## HTML → Markdown 轉換

```python
import html2text

h = html2text.HTML2Text()
h.ignore_links = False
h.ignore_images = False
h.body_width = 0        # 不自動換行

with open("input.html", encoding="utf-8", errors="replace") as f:
    md = h.handle(f.read())

with open("output.md", "w") as out:
    out.write(md)
```

## RSS/Atom Feed → Markdown 表格

```python
from xml.etree import ElementTree as ET

tree = ET.parse("feed.xml")
root = tree.getroot()
ns = {"atom": "http://www.w3.org/2005/Atom"}

entries = []
for entry in root.findall(".//atom:entry", ns):
    title = entry.find("atom:title", ns)
    link = entry.find("atom:link", ns)
    published = entry.find("atom:published", ns)
    entries.append({
        "title": title.text if title is not None else "",
        "url": link.attrib.get("href", "") if link is not None else "",
        "date": published.text[:10] if published is not None else ""
    })

# 輸出 Markdown 表格
md = "| # | 日期 | 標題 |\n|---|------|------|\n"
for i, e in enumerate(entries, 1):
    md += f"| {i} | {e['date']} | [{e['title']}]({e['url']}) |\n"
```

## Obsidian 歸檔結構

```
obsidian-vault/[主題]/
├── 文章標題.md          # 筆記本體
├── 分析報告.md
└── images/
    └── 配圖.png         # 圖片統一放子資料夾
```

## 圖片嵌入語法

| 位置 | 語法 |
|------|------|
| 同資料夾 | `![[圖片.png]]` |
| 子資料夾 | `![[images/圖片.png]]` |
| 上層資料夾 | `![[../其他資料夾/圖片.png]]` |

## 權限問題（Docker 環境）

Obsidian vault 通常由 uid 1000 擁有，但 Hermes Docker 容器以 uid 10000 (hermes) 執行。
寫入後若手機端看不到圖片：

```bash
chmod -R 777 /opt/data/obsidian-vault/[主題]/
```

這放開全部權限，手機 Obsidian 即可讀取。
