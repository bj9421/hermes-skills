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
# LLM Client with retry + fallback models
# ---------------------------------------------------------------------------
# Fallback model chain: primary → alternatives (all NVIDIA-hosted)
_FALLBACK_MODELS = [
    "deepseek-ai/deepseek-v4-flash",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
]

def _call_llm_with_retry(client, prompt: str, max_retries: int = 3, base_delay: float = 5.0) -> str | None:
    """Call LLM with retry on 503/rate-limit, auto-switch to next model on persistent failure."""
    import time
    
    for model in _FALLBACK_MODELS:
        for attempt in range(max_retries):
            try:
                _rate_limit()
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
                    return result.strip()
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "503" in err_str or "ResourceExhausted" in err_str or "rate" in err_str.lower()
                if is_rate_limit and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"[WARN] {model} rate limited (attempt {attempt+1}/{max_retries}), retry in {delay:.0f}s...", file=sys.stderr)
                    time.sleep(delay)
                elif is_rate_limit:
                    print(f"[WARN] {model} still rate limited after {max_retries} retries, trying next model...", file=sys.stderr)
                    break  # move to next model
                else:
                    print(f"[WARN] LLM error on {model}: {e}", file=sys.stderr)
                    return None  # non-rate-limit error, don't retry
    return None


# ---------------------------------------------------------------------------
# Extract visual summary data
# ---------------------------------------------------------------------------
def _extract_visual_data(script: str, title: str, lang: str = "zh") -> dict:
    """Extract structured data for visual summary."""
    client_info = _get_llm_client()
    if not client_info:
        return None
    client, _ = client_info  # ignore default model, _call_llm_with_retry handles model selection

    lang_hint = "使用繁體中文" if lang in ("zh", "zh-TW") else "Use English"

    prompt = f"""從口播腳本提取視覺摘要資料。

⚠️ 重要：所有文字必須使用「繁體中文」（Traditional Chinese），禁止使用簡體中文。
例如：軟體（非软件）、程式（非程序）、遊戲（非游戏）、連結（非连接）。

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
    result = _call_llm_with_retry(client, prompt)
    if not result:
        print("[WARN] Visual data extraction failed: all models exhausted", file=sys.stderr)
        return None
    try:
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
        if result.endswith("```"):
            result = result.rsplit("```", 1)[0]
        return json.loads(result.strip())
    except Exception as e:
        print(f"[WARN] Visual data JSON parse failed: {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------
def _load_font(size: int, bold: bool = False):
    """Load a CJK-capable font, falling back gracefully.
    
    Priority: NotoSansSC (繁簡全覆蓋) > Iansui (繁體) > fallback.
    """
    font_paths = [
        # Noto Sans SC (simplified + traditional Chinese, best coverage)
        "/opt/data/fonts/NotoSansSC-Bold.ttf" if bold else "/opt/data/fonts/NotoSansSC-Regular.ttf",
        # 芫荽 iansui (Taiwanese traditional Chinese, Klee One derived)
        "/opt/data/fonts/Iansui-Regular.ttf",
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

# Emoji font path (monochrome, for icon rendering)
_EMOJI_FONT = "/opt/data/fonts/NotoEmoji-Regular.ttf"

# Rate limiter — minimum 2s between API calls (40 RPM free tier)
_last_api_call = 0.0
_API_INTERVAL = 2.0

def _rate_limit():
    global _last_api_call
    import time
    elapsed = time.time() - _last_api_call
    if elapsed < _API_INTERVAL:
        time.sleep(_API_INTERVAL - elapsed)
    _last_api_call = time.time()


# ---------------------------------------------------------------------------
# Agnes AI illustration generation
# ---------------------------------------------------------------------------
def _load_env_key(key: str) -> str:
    """Load an API key from env var, falling back to .env file."""
    val = os.environ.get(key, "")
    if val:
        return val
    env_path = "/opt/data/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _generate_agnes_illustration(script: str, title: str, lang: str = "zh", out_dir: str = ".") -> str | None:
    """Generate an AI illustration via Agnes Image 2.1 Flash.
    
    Returns path to the saved .png file, or None on failure.
    The illustration is saved alongside the Pillow card with suffix '_ai'.
    """
    import urllib.request
    import time as _time

    api_key = _load_env_key("AGNES_API_KEY")
    if not api_key:
        print("[WARN] AGNES_API_KEY not found, skipping AI illustration", file=sys.stderr)
        return None

    # Step 1: Use LLM to generate an image prompt from the script
    client_info = _get_llm_client()
    if not client_info:
        print("[WARN] LLM client unavailable for image prompt, skipping AI illustration", file=sys.stderr)
        return None
    client, _ = client_info

    lang_hint = "繁體中文" if lang in ("zh", "zh-TW") else "English"
    prompt_for_llm = f"""根據以下口播腳本，生成一段簡潔的英文圖片描述 prompt（用於 AI 圖片生成）。

規則：
- 輸出純英文，不加引號、不加多餘文字
- 描述風格：cinematic, detailed, vibrant colors
- 50-80 字
- 抓住腳本的核心主題和視覺意象

腳本前 3000 字：
{script[:3000]}
"""
    print("[INFO] Generating Agnes illustration prompt...", file=sys.stderr)
    image_prompt = _call_llm_with_retry(client, prompt_for_llm)
    if not image_prompt:
        print("[WARN] Failed to generate image prompt, skipping AI illustration", file=sys.stderr)
        return None

    # Clean up any markdown or extra whitespace
    image_prompt = image_prompt.strip().strip('"').strip("'").strip("`")
    if image_prompt.startswith("```"):
        image_prompt = image_prompt.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    print(f"[INFO] Image prompt: {image_prompt[:100]}...", file=sys.stderr)

    # Step 2: Call Agnes API
    import json as _json
    payload = _json.dumps({
        "model": "agnes-image-2.1-flash",
        "prompt": image_prompt,
        "size": "1K",
        "ratio": "16:9",
        "extra_body": {
            "response_format": "url"
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://apihub.agnes-ai.com/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print("[INFO] Calling Agnes image API (may take 30-120s)...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = _json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[WARN] Agnes API error: {e}", file=sys.stderr)
        return None

    # Step 3: Extract URL and download
    image_url = None
    if isinstance(result.get("data"), list) and result["data"]:
        image_url = result["data"][0].get("url")
    if not image_url:
        print("[WARN] No image URL in Agnes response", file=sys.stderr)
        return None

    safe_title = title.replace("/", "_").replace("\\", "_")[:60]
    png_path = os.path.join(out_dir, f"{safe_title}_ai.png")

    print(f"[INFO] Downloading AI illustration from Agnes...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(image_url, png_path)
        os.chmod(png_path, 0o777)
        print(f"[OK] AI illustration saved: {png_path}", file=sys.stderr)
        return png_path
    except Exception as e:
        print(f"[WARN] Failed to download AI illustration: {e}", file=sys.stderr)
        return None


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
    """Generate visual summary images from a podcast script.
    
    Produces two outputs:
    1. AI illustration via Agnes Image 2.1 Flash (saved as *_ai.png)
    2. Pillow summary card (saved as *_summary.png)
    
    Args:
        script: podcast script text
        title: video title
        lang: target language
        out_dir: output directory
    
    Returns:
        Path to the Pillow summary .png file, or None on failure.
    """
    # --- AI illustration (Agnes) — runs in parallel conceptually, but sequential here ---
    agnes_path = _generate_agnes_illustration(script, title, lang, out_dir)
    
    # --- Pillow summary card ---
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

    # Fonts (大字版 — 全加粗、最小 36px、適合長輩閱讀)
    font_title = _load_font(80, bold=True)
    font_tagline = _load_font(42, bold=True)
    font_topic_label = _load_font(48, bold=True)
    font_topic_detail = _load_font(36, bold=True)
    font_stat_value = _load_font(72, bold=True)
    font_stat_label = _load_font(36, bold=True)
    font_icon = _load_font(60)

    y = MARGIN

    # --- Title area ---
    # Accent bar (match title height)
    bar_h = 80
    draw.rectangle([MARGIN, y, MARGIN + 6, y + bar_h], fill=_ACCENT)
    
    # Title text
    title_text = data.get("title", title)[:20]
    draw.text((MARGIN + 18, y), title_text, font=font_title, fill=_TEXT_W, stroke_width=2, stroke_fill=_TEXT_W)
    y += 100

    # Tagline
    tagline = data.get("tagline", "")
    if tagline:
        draw.text((MARGIN + 18, y), tagline, font=font_tagline, fill=_TEXT_DIM, stroke_width=1, stroke_fill=_TEXT_DIM)
        y += 50

    y += 25

    # --- Topics grid ---
    topics = data.get("topics", [])
    if topics:
        cols = min(len(topics), 3)
        rows = (len(topics) + cols - 1) // cols
        card_w = (W - MARGIN * 2 - (cols - 1) * 24) // cols
        card_h = 260
        
        for i, topic in enumerate(topics):
            row = i // cols
            col = i % cols
            cx = MARGIN + col * (card_w + 24)
            cy = y + row * (card_h + 24)
            
            # Card background
            _rounded_rect(draw, [cx, cy, cx + card_w, cy + card_h], 18, _BG_CARD)
            
            # Icon (emoji rendered with Noto Emoji font)
            icon = topic.get("icon", "📌")
            try:
                emoji_font = ImageFont.truetype(_EMOJI_FONT, 48)
            except:
                emoji_font = font_icon
            draw.text((cx + 24, cy + 18), icon, font=emoji_font, fill=_TEXT_W)
            
            # Label
            label = topic.get("label", "")[:8]
            draw.text((cx + 90, cy + 28), label, font=font_topic_label, fill=_TEXT_W, stroke_width=2, stroke_fill=_TEXT_W)
            
            # Detail
            detail = topic.get("detail", "")[:50]
            detail_lines = _wrap_text(detail, font_topic_detail, card_w - 110, draw)
            for j, line in enumerate(detail_lines[:3]):
                draw.text((cx + 90, cy + 100 + j * 42), line, font=font_topic_detail, fill=_TEXT_L, stroke_width=1, stroke_fill=_TEXT_L)
        
        y += rows * (card_h + 24) + 36

    # --- Stats bar ---
    stats = data.get("stats", [])
    if stats and y < H - 180:
        # Stats background
        _rounded_rect(draw, [MARGIN, y, W - MARGIN, y + 200], 16, _BG_CARD)
        
        stat_w = (W - MARGIN * 2 - 50) // max(len(stats), 1)
        for i, stat in enumerate(stats[:3]):
            sx = MARGIN + 40 + i * stat_w
            sy = y + 25
            
            value = stat.get("value", "")[:12]
            draw.text((sx, sy), value, font=font_stat_value, fill=_ACCENT2, stroke_width=2, stroke_fill=_ACCENT2)
            
            label = stat.get("label", "")[:25]
            draw.text((sx, sy + 80), label, font=font_stat_label, fill=_TEXT_DIM, stroke_width=1, stroke_fill=_TEXT_DIM)
        
        y += 220

    # --- Footer ---
    draw.text((MARGIN, H - 44), "Generated by yt2md pipeline", font=font_stat_label, fill=_TEXT_DIM)

    # Save
    safe_title = title.replace("/", "_").replace("\\", "_")[:60]
    png_path = os.path.join(out_dir, f"{safe_title}_summary.png")
    img.save(png_path, "PNG", quality=95)
    os.chmod(png_path, 0o777)
    print(f"[OK] Visual summary card saved: {png_path}", file=sys.stderr)
    if agnes_path:
        print(f"[OK] AI illustration saved: {agnes_path}", file=sys.stderr)
    else:
        print("[INFO] AI illustration was not generated (skipped or failed)", file=sys.stderr)
    return png_path
