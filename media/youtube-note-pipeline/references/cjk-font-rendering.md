# CJK Font Rendering in Pillow (visual_gen.py)

## Font Inventory (installed on RPi4 Docker)

| Font | Path | Style | Use For |
|------|------|-------|---------|
| 芫荽 iansui | `/opt/data/fonts/Iansui-Regular.ttf` | Warm kai-style, Taiwan Traditional Chinese | Primary CJK text (title, labels, detail, stats) |
| Noto Sans SC | `/opt/data/fonts/NotoSansSC-Bold.ttf` | Clean modern sans-serif | Fallback CJK text |
| WenQuanYi Zen Hei | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` | Functional, user considers ugly | Fallback CJK text |
| Noto Emoji | `/opt/data/fonts/NotoEmoji-Regular.ttf` | Monochrome white outlines | Emoji icons (🦷💧💔 etc.) |
| DejaVu Sans | `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` | Latin only | Last resort (no CJK) |

## Key Findings

### Pillow cannot mix fonts in one draw.text() call
Each `draw.text()` uses exactly one font. To render CJK text + emoji icons, use separate `draw.text()` calls with different fonts. This is how `visual_gen.py` handles it — icons get their own render pass with `NotoEmoji-Regular.ttf`.

### CJK fonts have no emoji glyphs
When using iansui or Noto Sans SC, emoji characters (🦷, 💧, 💔) render as tofu/replacement characters (empty squares or random symbols). **Always use a separate emoji font for icon rendering.**

### Only monochrome emoji works with Pillow
`NotoColorEmoji.ttf` uses CBDT/CBLC color format which Pillow cannot render. Use the monochrome variant only. Downloaded from Google Fonts CSS API (not GitHub releases — those have no standalone TTF).

### iansui font only has Regular weight
No bold variant exists. Pillow's `ImageFont.truetype()` always loads the same file. For "bold" effect with iansui, the font is already semi-bold weight (derived from Klee One SemiBold), so no artificial bolding is needed.

## Downloading Fonts in Docker (no root)

Cannot use `apt-get install` (no root). Use Python urllib:

```python
import urllib.request
# For GitHub releases (e.g. iansui):
url = 'https://github.com/ButTaiwan/iansui/releases/download/v1.020/iansui.zip'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/octet-stream'})
data = urllib.request.urlopen(req, timeout=30).read()

# For Google Fonts (e.g. Noto Emoji):
# 1. Get CSS from fonts.googleapis.com
# 2. Extract url() from @font-face
# 3. Download the TTF
```

### curl fails on GitHub
GitHub redirects `curl` downloads to HTML pages or returns tiny corrupt files. Always use Python `urllib.request` for GitHub asset downloads.

## Current Font Loading Order in _load_font()

```python
font_paths = [
    "/opt/data/fonts/Iansui-Regular.ttf",           # 1st choice: 芫荽
    "/opt/data/fonts/NotoSansSC-Bold.ttf",           # 2nd: Noto Sans SC
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", # 3rd: WenQuanYi
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", # last resort
]
```

## Emoji Rendering in visual_gen.py

```python
_EMOJI_FONT = "/opt/data/fonts/NotoEmoji-Regular.ttf"

# In card rendering loop:
icon = topic.get("icon", "📌")
emoji_font = ImageFont.truetype(_EMOJI_FONT, 48)
draw.text((cx + 24, cy + 18), icon, font=emoji_font, fill=_TEXT_W)
```

## PPTX (python-pptx) 中文字型（2026-08-06 調查）

- **坑**：`run.font.name = 'Noto Sans SC'` **只設 Latin 字型，中文字型不生效** — 必須額外設 East Asian 屬性：
  ```python
  from pptx.oxml.ns import qn
  rPr = run._r.get_or_add_rPr()
  ea = rPr.makeelement(qn('a:ea'), {'typeface': 'Noto Sans SC'})
  rPr.append(ea)
  ```
- 現況 ppt_gen.py 完全沒設 font.name → 中文字型 fallback 看開啟端（不可控）。
- **emoji 不需指定**：PPT run 指定 Noto Sans SC 後，emoji 字元由檢視端自動 fallback（Pi 已裝 NotoEmoji/NotoColorEmoji；手機/Win 有內建）。只有 Pillow 合成才需明確指定（本檔案前半段）。
- 決策：ppt_gen.py 設 Noto Sans SC（含 a:ea）。細節見 `ppt-prompt-resources.md` 的「中文字型設定」。

## Resolution and Scaling

Canvas: 1920×1080 (Full HD). Minimum font size: 36px. All text bold.

| Element | Size | Bold |
|---------|------|------|
| Title | 80px | Yes |
| Tagline | 42px | Yes |
| Card label | 48px | Yes |
| Card detail | 36px | Yes |
| Stat value | 72px | Yes |
| Stat label | 36px | Yes |
| Icon | 60px | N/A (emoji font) |

Card height: 260px. Card gap: 24px. Stats bar height: 200px. MARGIN: 60px.
