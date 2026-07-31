#!/usr/bin/env python3
"""
ppt_gen.py — Generate PowerPoint slides from podcast scripts.

Extracts key points via LLM and creates a professional presentation.
"""

import os
import sys
import json
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ---------------------------------------------------------------------------
# LLM Client (reuses NVIDIA API)
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
# Extract key points from script via LLM
# ---------------------------------------------------------------------------
def _extract_key_points(script: str, title: str, lang: str = "zh") -> dict:
    """Extract structured key points from podcast script.
    
    Returns dict with:
        - title: presentation title
        - subtitle: subtitle/tagline
        - points: list of {heading, bullets} dicts
        - summary: conclusion paragraph
    """
    # ⚠️ 2026-07-31 使用者指示：LLM 整理文檔一律用 Zen，不用 NVIDIA（NVIDIA 僅供 Whisper）
    try:
        from notehub.core.llm import call_zen
    except ImportError:
        call_zen = None
    if not call_zen:
        print("[WARN] call_zen unavailable — cannot extract key points", file=sys.stderr)
        return None

    lang_hint = "使用繁體中文" if lang in ("zh", "zh-TW") else "Use English"

    prompt = f"""從以下口播腳本中提取重點，產生簡報用的結構化資料。

{lang_hint}

輸出嚴格 JSON 格式（不要加 markdown code fence）：
{{
  "title": "簡報標題（簡潔有力）",
  "subtitle": "副標題或一句話摘要",
  "points": [
    {{
      "heading": "重點標題",
      "bullets": ["要點1", "要點2"]
    }}
  ],
  "summary": "結論段落（2-3句話）"
}}

規則：
- points 產出 4-6 個重點，每個重點 2-3 個 bullets
- bullets 每條不超過 30 字
- summary 總結核心 takeaway
- 不要臆測腳本沒提到的內容

口播腳本：
{script[:6000]}
"""
    try:
        result = call_zen(
            [
                {"role": "system", "content": "你是結構化資料提取專家，只輸出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        if result:
            # Clean up potential markdown code fence
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            return json.loads(result.strip())
    except Exception as e:
        print(f"[WARN] Key point extraction failed: {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
_DARK_BG = RGBColor(0x1A, 0x1A, 0x2E)       # Dark navy
_ACCENT = RGBColor(0xE8, 0x4D, 0x3D)         # Warm red
_TEXT_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_TEXT_LIGHT = RGBColor(0xCC, 0xCC, 0xCC)
_CARD_BG = RGBColor(0x2D, 0x2D, 0x44)        # Slightly lighter navy


# ---------------------------------------------------------------------------
# Build PPT
# ---------------------------------------------------------------------------
def _add_title_slide(prs: Presentation, data: dict):
    """Add a dark-themed title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout

    # Background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = _DARK_BG

    # Title
    left, top, width, height = Inches(0.8), Inches(2.2), Inches(8.4), Inches(1.5)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = data.get("title", "Presentation")
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = _TEXT_WHITE
    p.alignment = PP_ALIGN.CENTER

    # Subtitle
    left, top, width, height = Inches(1.5), Inches(3.8), Inches(7), Inches(1)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = data.get("subtitle", "")
    p.font.size = Pt(20)
    p.font.color.rgb = _TEXT_LIGHT
    p.alignment = PP_ALIGN.CENTER

    # Accent line
    left, top, width, height = Inches(3.5), Inches(3.5), Inches(3), Inches(0.05)
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE.RECTANGLE
        left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _ACCENT
    shape.line.fill.background()


def _add_content_slide(prs: Presentation, point: dict, index: int):
    """Add a content slide with heading and bullets."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = _DARK_BG

    # Number badge
    left, top, width, height = Inches(0.6), Inches(0.4), Inches(0.8), Inches(0.8)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = f"{index:02d}"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = _ACCENT
    p.alignment = PP_ALIGN.LEFT

    # Heading
    left, top, width, height = Inches(0.6), Inches(1.3), Inches(8.8), Inches(1)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = point.get("heading", "")
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = _TEXT_WHITE

    # Accent line under heading
    left, top, width, height = Inches(0.6), Inches(2.3), Inches(2), Inches(0.04)
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _ACCENT
    shape.line.fill.background()

    # Bullets
    bullets = point.get("bullets", [])
    left, top, width, height = Inches(0.8), Inches(2.7), Inches(8.4), Inches(4)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"▸  {bullet}"
        p.font.size = Pt(20)
        p.font.color.rgb = _TEXT_LIGHT
        p.space_after = Pt(14)


def _add_summary_slide(prs: Presentation, data: dict):
    """Add a summary/conclusion slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = _DARK_BG

    # "Key Takeaway" label
    left, top, width, height = Inches(0.8), Inches(1.5), Inches(8.4), Inches(0.6)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = "KEY TAKEAWAY"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = _ACCENT
    p.alignment = PP_ALIGN.CENTER

    # Accent line
    left, top, width, height = Inches(3.5), Inches(2.2), Inches(3), Inches(0.04)
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _ACCENT
    shape.line.fill.background()

    # Summary text
    left, top, width, height = Inches(1), Inches(2.6), Inches(8), Inches(3)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = data.get("summary", "")
    p.font.size = Pt(22)
    p.font.color.rgb = _TEXT_LIGHT
    p.alignment = PP_ALIGN.CENTER
    p.line_spacing = Pt(32)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_ppt(script: str, title: str, lang: str = "zh", out_dir: str = ".") -> str | None:
    """Generate a PowerPoint presentation from a podcast script.
    
    Args:
        script: podcast script text
        title: video title
        lang: target language
        out_dir: output directory
    
    Returns:
        Path to the generated .pptx file, or None on failure.
    """
    print("[INFO] Extracting key points for PPT...", file=sys.stderr)
    data = _extract_key_points(script, title, lang)
    if not data:
        print("[WARN] Could not extract key points, using fallback", file=sys.stderr)
        data = {
            "title": title,
            "subtitle": "",
            "points": [{"heading": "重點整理", "bullets": ["無法提取結構化重點"]}],
            "summary": "請參閱口播腳本了解完整內容。",
        }

    # Create presentation (widescreen 16:9)
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)

    # Build slides
    _add_title_slide(prs, data)
    for i, point in enumerate(data.get("points", []), 1):
        _add_content_slide(prs, point, i)
    _add_summary_slide(prs, data)

    # Save
    safe_title = title.replace("/", "_").replace("\\", "_")[:80]
    pptx_path = os.path.join(out_dir, f"{safe_title}.pptx")
    prs.save(pptx_path)
    os.chmod(pptx_path, 0o777)
    print(f"[OK] PPT saved: {pptx_path} ({len(prs.slides)} slides)", file=sys.stderr)
    return pptx_path
