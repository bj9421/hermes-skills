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
# JSON 容錯解析（2026-08-06 階段 1：LLM 輸出格式不穩，直接 json.loads 常失敗
# → fallback「無法提取」→ 簡報品質爛。強化解析，成功率高很多。）
# ---------------------------------------------------------------------------
def _parse_json_loose(text: str) -> dict | None:
    """容錯解析 LLM 輸出的 JSON：跳過前綴雜訊、找到第一個完整 JSON 物件。

    策略：
    1. strip + 找第一個 '{' 開始
    2. raw_decode 嘗試完整解析（可跳過尾部雜訊）
    3. 失敗 → 找最後一個 '}' 截斷再試（LLM 常在結尾附加說明文字）
    """
    if not text:
        return None
    import json as _json
    t = text.strip()
    start = t.find('{')
    if start == -1:
        return None
    t = t[start:]
    try:
        obj, _ = _json.JSONDecoder().raw_decode(t)
        return obj
    except _json.JSONDecodeError:
        end = t.rfind('}')
        if end == -1:
            return None
        try:
            return _json.loads(t[:end + 1])
        except _json.JSONDecodeError:
            return None


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
        # 🔴 2026-08-06：改用 call_llm（Zen→AGNES→Groq fallback 鏈）。
        # 原本 call_zen 無 fallback — Zen timeout 時直接變 3 slides 基本版。
        from notehub.core.llm import call_llm
    except ImportError:
        call_llm = None
    if not call_llm:
        print("[WARN] call_llm unavailable — cannot extract key points", file=sys.stderr)
        return None

    lang_hint = "使用繁體中文" if lang in ("zh", "zh-TW") else "Use English"

    # 🔴 2026-08-06 質量升級（階段 1）：
    # 採用 104 職場力「投影片大綱規劃模組」精神 + 2Slides 專業技巧 + one-idea-per-slide 原則。
    # 保留既有 JSON 結構（title/subtitle/points/summary）→ 渲染端零改動，質量規則大幅提升。
    prompt = f"""從以下口播腳本中提取重點，產生簡報用的結構化資料。

{lang_hint}

【角色】你是簡報架構師（Presentation Architect），擅長把長篇內容濃縮成有故事線、每頁一個核心訊息的專業簡報。

【內部思考流程】（只思考，不要輸出思考過程）
1. 找出整份內容的敘事弧線：Hook（吸睛開場）→ 問題/好奇 → 關鍵論點/證據 → 案例/數據 → 行動/總結
2. 每一頁只傳達「一個核心訊息」（one-idea-per-slide），不要塞多個概念
3. 標題採用 tagline 形式：動詞開頭或問句，具體不空泛

輸出嚴格 JSON 格式（不要加 markdown code fence）：
{{
  "title": "簡報標題（簡潔有力，10 字內最佳）",
  "subtitle": "副標題或一句話摘要（點出核心價值）",
  "points": [
    {{
      "heading": "重點標題（tagline 式，動詞/問句，≤10 字）",
      "bullets": ["要點1", "要點2"]
    }}
  ],
  "summary": "結論段落（2-3句話，含一個明確 takeaway 與行動建議）"
}}

規則：
- points 產出 5-7 個重點，依敘事弧線排列：第 1 個是 Hook（吸睛事實或問題），中間是論點與證據，最後 1 個是行動/總結
- 每個 heading 只代表一個核心訊息，彼此不重複
- bullets 每條不超過 15 字，要具體有畫面（用數字、名稱、對比），避免流水帳與形容詞堆疊
- summary 總結核心 takeaway，並給一句行動建議（「你可以…」「下一步…」）
- 不要臆測腳本沒提到的內容
- 🔴 重要：所有內容文字禁止使用 ASCII 雙引號（"），一律用中文引號「」或直接不用，避免破壞 JSON

口播腳本：
{script[:6000]}
"""
    try:
        result = call_llm(
            [
                {"role": "system", "content": "你是結構化資料提取專家，只輸出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            # 🔴 2026-08-06：max_tokens 設 0（不帶）— deepseek-v4-flash 是 reasoning
            # 模型，設 max_tokens 會被思考過程吃光 → content 空 → 回 None（同 podcast.py 做法）
            max_tokens=0,
            temperature=0.3,
        )
        if result:
            # 🔴 2026-08-06 階段 1：改用容錯解析（raw_decode + rfind fallback），
            #   取代原本只 strip code fence + json.loads（LLM 格式瑕疵就整段失敗）。
            data = _parse_json_loose(result)
            if data:
                # 🔴 2026-08-06 階段 1：部分 model 回 key_points 結構（title/description）
                #   → normalize 成渲染端吃的 points（heading/bullets）結構。
                if 'points' not in data and isinstance(data.get('key_points'), list):
                    data['points'] = []
                    for kp in data['key_points']:
                        bullets = []
                        if kp.get('description'):
                            bullets.append(kp['description'])
                        if kp.get('details') and isinstance(kp['details'], list):
                            bullets.extend(str(d) for d in kp['details'])
                        data['points'].append({'heading': kp.get('title', ''), 'bullets': bullets})
                return data
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

# 🔴 2026-08-06：繁中字型 — Noto Sans CJK TC（Google 官方繁中；內部 family name 是
# "Noto Sans CJK TC" 不是 "Noto Sans TC"）。備選思源黑體 Source Han Sans TC。
_FONT_NAME = "Noto Sans CJK TC"


def _apply_cjk_font(prs: Presentation, name: str = _FONT_NAME):
    """遍歷全部 slide 文字 run，設定 latin + East Asian 字型。

    ⚠️ python-pptx 的 run.font.name 只設 latin typeface，中文需要額外設 a:ea
    （East Asian）屬性才生效 — 否則 PowerPoint 用系統預設中文字型（不可控）。
    """
    from pptx.oxml.ns import qn
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.font.name = name  # latin
                    rPr = run._r.get_or_add_rPr()
                    ea = rPr.find(qn('a:ea'))
                    if ea is None:
                        ea = rPr.makeelement(qn('a:ea'), {})
                        rPr.append(ea)
                    ea.set('typeface', name)


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
    # 🔴 2026-08-06：繁中字型（Noto Sans CJK TC + a:ea 屬性）
    _apply_cjk_font(prs)
    pptx_path = os.path.join(out_dir, f"{safe_title}.pptx")
    prs.save(pptx_path)
    os.chmod(pptx_path, 0o777)
    print(f"[OK] PPT saved: {pptx_path} ({len(prs.slides)} slides)", file=sys.stderr)
    return pptx_path
