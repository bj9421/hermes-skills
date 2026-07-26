#!/usr/bin/env python3
"""
visual_gen.py — Generate a visual summary image from podcast scripts.

Creates a NotebookLM-style visual overview using Pillow.
"""

import os
import sys
import json
import textwrap
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------
def _get_llm_client():
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        env_path = "/opt/data/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NVIDIA_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not api_key:
        return None
    from openai import OpenAI
    base_url = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = os.environ.get("NVIDIA_ORGANIZE_MODEL", "deepseek-ai/deepseek-v4-flash")
    return OpenAI(base_url=base_url, api_key=api_key), model


# ---------------------------------------------------------------------------
# Extract visual summary data
# ---------------------------------------------------------------------------
def _extract_visual_data(script: str, title: str, lang: str = "zh") -> dict:
    """Extract structured data for visual summary."""
    client_info = _get_llm_client()
    if not client_info:
        return None
    client, model = client_info

    lang_hint = "使用繁體中文" if lang in ("zh", "zh-TW") else "Use English"

    prompt = f"""從口播腳本提取視覺摘要資料。{lang_hint}

輸出嚴格 JSON（不要 code fence）：
{{
  "title": "簡潔標題（8字以內）",
  "tagline": "一句話摘要",
  "topics": [
    {{"icon": "🩺", "label": "主題名（4字以內）", "detail": "一句話說明"}}
  ],
  "stats": [
    {{"value": "數字或關鍵詞", "label": "說明"}}
  ]
}}

規則：
- topics 4-6 個，每個 label ≤4字
- stats 2-3 個，選最驚人/重要的數據
- icon 用 emoji 表示主題
- 不要臆測

腳本：
{script[:5000]}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "只輸出 JSON，不加任何額外文字。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.3,
        )
        result = response.choices[0].message.content
        if result:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            return json.loads(result.strip())
    except Exception as e:
        print(f"[WARN] Visual data extraction failed: {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------
def _load_font(size: int, bold: bool = False):
    """Load a CJK-capable font, falling back gracefully."""
    font_paths = [
        # 芫荽 iansui (Taiwanese traditional Chinese, Klee One derived)
        "/opt/data/fonts/Iansui-Regular.ttf",
        # Noto Sans SC (clean, modern CJK)
        "/opt/data/fonts/NotoSansSC-Bold.ttf" if bold else "/opt/data/fonts/NotoSansSC-Regular.ttf",
        # WenQuanYi Zen Hei (fallback)
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # DejaVu (last resort, no CJK)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
# Color palette — warm sunset gradient feel (台灣日落暖色系)
_BG_DARK = (26, 26, 46)         # #1A1A2E
_BG_CARD = (45, 45, 68)         # #2D2D44
_ACCENT = (232, 77, 61)         # #E84D3D warm red
_ACCENT2 = (255, 165, 89)       # #FFA559 orange
_TEXT_W = (255, 255, 255)
_TEXT_L = (200, 200, 200)
_TEXT_DIM = (140, 140, 160)


def _rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.pieslice([x0, y0, x0 + 2*radius, y0 + 2*radius], 180, 270, fill=fill)
    draw.pieslice([x1 - 2*radius, y0, x1, y0 + 2*radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2*radius, x0 + 2*radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2*radius, y1 - 2*radius, x1, y1], 0, 90, fill=fill)


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = list(paragraph)
        current = ""
        for char in words:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Generate visual summary image
# ---------------------------------------------------------------------------
def generate_visual(script: str, title: str, lang: str = "zh", out_dir: str = ".") -> str | None:
    """Generate a visual summary image from a podcast script.
    
    Args:
        script: podcast script text
        title: video title
        lang: target language
        out_dir: output directory
    
    Returns:
        Path to the generated .png file, or None on failure.
    """
    print("[INFO] Extracting visual summary data...", file=sys.stderr)
    data = _extract_visual_data(script, title, lang)
    if not data:
        print("[WARN] Could not extract visual data", file=sys.stderr)
        data = {
            "title": title[:8],
            "tagline": "",
            "topics": [{"icon": "📝", "label": "口播", "detail": "請參閱腳本"}],
            "stats": [],
        }

    # Canvas settings (Full HD 16:9)
    W, H = 1920, 1080
    MARGIN = 60
    img = Image.new("RGB", (W, H), _BG_DARK)
    draw = ImageDraw.Draw(img)

    # Fonts (scaled for 1920x1080)
    font_title = _load_font(56, bold=True)
    font_tagline = _load_font(28)
    font_topic_label = _load_font(32, bold=True)
    font_topic_detail = _load_font(22)
    font_stat_value = _load_font(44, bold=True)
    font_stat_label = _load_font(20)
    font_icon = _load_font(48)

    y = MARGIN

    # --- Title area ---
    # Accent bar
    draw.rectangle([MARGIN, y, MARGIN + 6, y + 40], fill=_ACCENT)
    
    # Title text
    title_text = data.get("title", title)[:20]
    draw.text((MARGIN + 18, y), title_text, font=font_title, fill=_TEXT_W)
    y += 50

    # Tagline
    tagline = data.get("tagline", "")
    if tagline:
        draw.text((MARGIN + 18, y), tagline, font=font_tagline, fill=_TEXT_DIM)
        y += 30

    y += 15

    # --- Topics grid ---
    topics = data.get("topics", [])
    if topics:
        cols = min(len(topics), 3)
        rows = (len(topics) + cols - 1) // cols
        card_w = (W - MARGIN * 2 - (cols - 1) * 20) // cols
        card_h = 180
        
        for i, topic in enumerate(topics):
            row = i // cols
            col = i % cols
            cx = MARGIN + col * (card_w + 20)
            cy = y + row * (card_h + 20)
            
            # Card background
            _rounded_rect(draw, [cx, cy, cx + card_w, cy + card_h], 16, _BG_CARD)
            
            # Icon
            icon = topic.get("icon", "📌")
            draw.text((cx + 20, cy + 18), icon, font=font_icon, fill=_TEXT_W)
            
            # Label
            label = topic.get("label", "")[:8]
            draw.text((cx + 80, cy + 22), label, font=font_topic_label, fill=_TEXT_W)
            
            # Detail
            detail = topic.get("detail", "")[:50]
            detail_lines = _wrap_text(detail, font_topic_detail, card_w - 100, draw)
            for j, line in enumerate(detail_lines[:3]):
                draw.text((cx + 80, cy + 65 + j * 28), line, font=font_topic_detail, fill=_TEXT_L)
        
        y += rows * (card_h + 20) + 30

    # --- Stats bar ---
    stats = data.get("stats", [])
    if stats and y < H - 160:
        # Stats background
        _rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 140], 14, _BG_CARD)
        
        stat_w = (W - MARGIN * 2 - 40) // max(len(stats), 1)
        for i, stat in enumerate(stats[:3]):
            sx = MARGIN + 30 + i * stat_w
            sy = y + 18
            
            value = stat.get("value", "")[:12]
            draw.text((sx, sy), value, font=font_stat_value, fill=_ACCENT2)
            
            label = stat.get("label", "")[:25]
            draw.text((sx, sy + 55), label, font=font_stat_label, fill=_TEXT_DIM)
        
        y += 160

    # --- Footer ---
    draw.text((MARGIN, H - 40), "Generated by yt2md pipeline", font=font_stat_label, fill=_TEXT_DIM)

    # Save
    safe_title = title.replace("/", "_").replace("\\", "_")[:60]
    png_path = os.path.join(out_dir, f"{safe_title}_summary.png")
    img.save(png_path, "PNG", quality=95)
    os.chmod(png_path, 0o777)
    print(f"[OK] Visual summary saved: {png_path}", file=sys.stderr)
    return png_path
