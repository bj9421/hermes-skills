"""Unified pipeline — multi-source → LLM → output.

Usage:
    python -m notehub "YouTube URL" --podcast dual --ppt --visual --lang zh
    python -m notehub "https://example.com" --organize --visual
    python -m notehub "./document.pdf" --organize --ppt
    python -m notehub "./notes.txt" --podcast solo
"""

import os
import re
import sys
from datetime import date

from ..extractors.detector import detect_source
from .llm import call_llm, get_client

# --- Config ---
OBSIDIAN_BASE = "/opt/data/obsidian-vault"
PODCAST_SUBDIR = "口播"
TRANSLATE_MAX_TOKENS = 100

# --- Organize prompt ---
ORGANIZE_PROMPT = """你是一個專業的內容整理助手。請將以下內容整理成結構化筆記。

要求：
1. 【重點摘要】— 3-5 個核心要點（bullet points），用 **粗體** 標示關鍵詞
2. 【內容整理】— 根據主題分段，每段加 ## 標題，段落之間邏輯連貫
3. 【精簡文字】— 去除贅字、口語重複、語助詞，保留完整語意
4. 語言：與原文相同
5. 不要加你自己的評論或額外資訊，忠於原文內容

內容：
"""

# --- Helpers ---
def _sanitize_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s[:120]


def _translate_title(title: str, target_lang: str) -> str | None:
    """Translate title for directory naming."""
    from ..extractors.base import ExtractResult  # avoid circular

    lang_names = {
        "zh": "繁體中文", "zh-TW": "繁體中文", "zh-CN": "简体中文",
        "ja": "日本語", "ko": "한국어", "en": "English",
    }
    lang_name = lang_names.get(target_lang, target_lang)

    messages = [
        {"role": "system", "content": "你是翻譯專家。只翻譯標題，不加任何解釋。"},
        {"role": "user", "content": f"將以下標題翻譯成{lang_name}，直接輸出翻譯結果：\n\n{title}"},
    ]
    result = call_llm(messages, max_tokens=TRANSLATE_MAX_TOKENS, temperature=0.3)
    if result:
        return result.strip().strip('"').strip("'").strip("《》")
    return None


def _chunk_text(text: str, max_chars: int = 25000, overlap: int = 1000) -> list[str]:
    """Split long text into chunks for LLM processing."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def _organize_content(text: str, title: str = "") -> str | None:
    """Organize raw text via LLM into structured notes."""
    chunks = _chunk_text(text)
    total = len(chunks)
    print(f"[INFO] Organizing {total} chunk{'s' if total > 1 else ''} via LLM...", file=sys.stderr)

    parts = []
    for i, chunk in enumerate(chunks):
        prompt = ORGANIZE_PROMPT + chunk
        if total > 1:
            if i == 0:
                prompt += "\n\n（這是多段處理的第 1 段，後續還有。）"
            elif i == total - 1:
                prompt += "\n\n（這是最後一段。請在整理完本段後，附上整部內容的【重點摘要】。）"

        messages = [
            {"role": "system", "content": "你是專業的內容整理助手。"},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages, max_tokens=4096, temperature=0.3)
        if result:
            parts.append(result)
        else:
            print(f"[WARN] LLM returned empty for chunk {i+1}", file=sys.stderr)
            parts.append(chunk)

    return "\n\n---\n\n".join(parts)


def run_pipeline(source: str, organize: bool = False,
                 podcast: str = None, ppt: bool = False, visual: bool = False,
                 lang: str = "auto", voice_a: str = None, voice_b: str = None):
    """Run the unified pipeline.

    Args:
        source: Input path (YouTube URL, web URL, PDF path, text file path)
        organize: Run LLM organizer on extracted content
        podcast: None, "solo", or "dual"
        ppt: Generate PowerPoint
        visual: Generate visual summary image
        lang: Target language for translation ("auto", "zh", "en", etc.)
        voice_a: TTS voice for host A
        voice_b: TTS voice for host B
    """
    today = date.today().strftime("%Y-%m-%d")

    # 1. Detect source type and extract
    extractor = detect_source(source)
    print(f"[INFO] Source type: {extractor.__class__.__name__}", file=sys.stderr)
    result = extractor.extract(source)

    title = result.metadata.get("title", "Untitled")
    source_id = result.source_id
    print(f"[INFO] Extracted: {title} ({len(result.text)} chars)", file=sys.stderr)

    # 2. Translate title for directory naming
    dir_title = title
    if lang and lang not in ("auto", "en") and title:
        translated = _translate_title(title, lang)
        if translated:
            dir_title = translated
            print(f"[INFO] Translated title: {dir_title}", file=sys.stderr)

    # 3. Create output directory
    safe_dir_title = _sanitize_filename(dir_title)
    if result.source_type == "youtube":
        out_dir = os.path.join(OBSIDIAN_BASE, PODCAST_SUBDIR, f"{safe_dir_title} [{source_id}]")
    else:
        out_dir = os.path.join(OBSIDIAN_BASE, "notes", f"{safe_dir_title} [{source_id}]")
    os.makedirs(out_dir, exist_ok=True)

    # 4. Save raw transcript
    raw_path = os.path.join(out_dir, f"{safe_dir_title}_raw.md")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(f"---\ncreated: {today}\nsource: {source}\ntitle: {title}\nsource_type: {result.source_type}\ntags: [{result.source_type}, transcript]\n---\n\n# {title}\n\n{result.text}")
    os.chmod(raw_path, 0o777)
    print(f"[INFO] Raw saved: {raw_path}", file=sys.stderr)

    # 5. Organize via LLM (if requested)
    organized = None
    if organize:
        organized = _organize_content(result.text, title)
        if organized:
            note_path = os.path.join(out_dir, f"{safe_dir_title}_notes.md")
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(f"---\ncreated: {today}\nsource: {source}\ntitle: {title}\nsource_type: {result.source_type}\ntype: organized\ntags: [{result.source_type}, notes]\n---\n\n# {title}\n\n{organized}")
            os.chmod(note_path, 0o777)
            print(f"[INFO] Notes saved: {note_path}", file=sys.stderr)

    # 6. Save to SQLite
    try:
        from ..db.models import NoteDB
        db = NoteDB()
        db.add_note(
            title=title,
            source_type=result.source_type,
            source_id=source_id,
            content=organized or result.text,
            raw_content=result.text,
            tags=[result.source_type],
            dir_path=out_dir,
            source_url=source,
        )
        print(f"[INFO] Indexed to SQLite", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] SQLite indexing failed: {e}", file=sys.stderr)

    # 7. Generate outputs
    content_for_gen = organized or result.text
    script_path = None
    podcast_out_dir = None
    ppt_out = None
    vis_out = None

    # Podcast
    if podcast:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from ..generators.podcast import produce_podcast
            script_path, podcast_out_dir = produce_podcast(
                content_for_gen, title, source_id, podcast, lang,
                out_dir, voice_a, voice_b
            )
            print(f"[INFO] Podcast generated: {podcast_out_dir}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Podcast failed: {e}", file=sys.stderr)

    # PPT
    if ppt:
        try:
            from ..generators.ppt import generate_ppt
            ppt_out = generate_ppt(content_for_gen, title, out_dir)
            print(f"[INFO] PPT generated: {ppt_out}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] PPT failed: {e}", file=sys.stderr)

    # Visual
    if visual:
        try:
            from ..generators.visual import generate_visual
            vis_out = generate_visual(content_for_gen, title, out_dir)
            print(f"[INFO] Visual generated: {vis_out}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Visual failed: {e}", file=sys.stderr)

    # 8. chmod all outputs
    import subprocess
    for p in [out_dir, podcast_out_dir, ppt_out, vis_out]:
        if p and os.path.exists(p):
            subprocess.run(["chmod", "-R", "777", p], capture_output=True)

    print(f"\n✅ Pipeline complete! Output: {out_dir}", file=sys.stderr)
    return out_dir
