"""Unified pipeline — multi-source → LLM → output.

Usage:
    python -m notehub "YouTube URL" --podcast dual --ppt --visual --lang zh
    python -m notehub "https://example.com" --organize --visual
    python -m notehub "./document.pdf" --organize --ppt
    python -m notehub "./notes.txt" --podcast solo
"""

import glob
import os
import re
import sys
from datetime import date
from pathlib import Path

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

# --- Script reuse helpers (2026-08-06) ---
def _load_script_content(path: str) -> tuple[str | None, str]:
    """讀 script.md，剝離 frontmatter 與開頭標題裝飾，回傳 (title, 口播正文)。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    title = None
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            m = re.search(r"^source:\s*(.+)$", parts[1], re.M)
            if m:
                title = m.group(1).strip()
            text = parts[2]
    lines = text.strip().splitlines()
    while lines and (lines[0].startswith("#") or lines[0].startswith(">") or not lines[0].strip()):
        lines.pop(0)
    return title, "\n".join(lines).strip()


def _find_existing_script(source: str) -> tuple[str | None, str, Path] | None:
    """找同 source 是否已有產出的口播腳本（重送不同輸出時重用，省下載/轉寫/LLM）。

    目前只處理 YouTube（實際痛點：yt-dlp 暫態失敗會整支 job 掛掉）。
    回傳 (title, script_content, out_dir) 或 None。
    """
    m = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        source,
    )
    if not m:
        return None
    video_id = m.group(1)
    # ⚠️ [video_id] 的 [] 是 glob 字元集語法 → 必須 escape，否則會誤匹配
    pattern = f"*{glob.escape(f'[{video_id}]')}*"
    matches = sorted(Path(OBSIDIAN_BASE, PODCAST_SUBDIR).glob(pattern + "/script.md"))
    if not matches:
        return None
    script_path = matches[0]
    title, content = _load_script_content(str(script_path))
    if not content:
        return None
    return title, content, script_path.parent


# --- Helpers ---
def _sanitize_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s[:120]


PROTECTED_TERMS = {
    "Hermes Agent": None,  # 品牌名不翻譯
    "NoteHub": None,
    "Quicksilver": None,
    "Judgment": None,
    "Gateway": None,
}

def _translate_title(title: str, target_lang: str) -> str | None:
    """Translate title for directory naming."""
    from ..extractors.base import ExtractResult  # avoid circular

    lang_names = {
        "zh": "繁體中文", "zh-TW": "繁體中文", "zh-CN": "簡體中文",
        "ja": "日本語", "ko": "한국어", "en": "English",
    }
    lang_name = lang_names.get(target_lang, target_lang)

    # 保護不應翻譯的專有名詞
    protected_placeholders = {}
    working_title = title
    for i, (term, _) in enumerate(PROTECTED_TERMS.items()):
        placeholder = f"__PROTECTED_{i}__"
        protected_placeholders[placeholder] = term
        working_title = working_title.replace(term, placeholder)

    messages = [
        {"role": "system", "content": "你是翻譯專家。只翻譯標題，不加任何解釋。"},
        {"role": "user", "content": f"將以下標題翻譯成{lang_name}，直接輸出翻譯結果：\n\n{working_title}"},
    ]
    result = call_llm(messages, max_tokens=TRANSLATE_MAX_TOKENS, temperature=0.3)
    if result:
        translated = result.strip().strip('"').strip("'").strip("《》")
        # 把佔位符還原回英文
        for placeholder, original in protected_placeholders.items():
            translated = translated.replace(placeholder, original)
        return translated
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


def _convert_to_traditional(dir_path: str):
    """Convert all markdown files in dir_path from Simplified to Traditional Chinese (Taiwan)."""
    try:
        import opencc
        converter = opencc.OpenCC('s2twp')
        for fname in os.listdir(dir_path):
            if fname.endswith('.md'):
                fpath = os.path.join(dir_path, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    text = f.read()
                converted = converter.convert(text)
                # Fix opencc over-conversions
                converted = converted.replace('指令碼', '腳本')
                converted = converted.replace('全域性', '全局')
                converted = converted.replace('演演算法', '演算法')
                if converted != text:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(converted)
                    print(f"[INFO] Converted to TC: {fname}", file=sys.stderr)
    except ImportError:
        print("[WARN] opencc not installed, skipping TC conversion", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] TC conversion failed: {e}", file=sys.stderr)


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


def _generate_outputs(source: str, title: str, content_for_gen: str, out_dir: str,
                      podcast: str | None, ppt: bool, visual: bool,
                      lang: str, voice_a: str | None, voice_b: str | None,
                      ppt_scheme: str = "dark", length: str = "long"):
    """步驟 7-9：產出（口播/PPT/圖卡）+ 繁中轉換 + chmod。正常流程與 script 重用共用。"""
    script_path = None
    podcast_out_dir = None
    ppt_out = None
    vis_out = None

    # Podcast — directly use podcast.py's produce_podcast (shared, no wrapper)
    if podcast:
        try:
            _scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from podcast import produce_podcast
            mp3_path = produce_podcast(
                transcript=content_for_gen,
                title=title,
                url=source,
                lang=lang,
                mode=podcast,
                voice_a=voice_a or "zh-TW-HsiaoChenNeural",
                voice_b=voice_b or "zh-TW-YunJheNeural",
                out_dir=out_dir,
                video_id=None,
                length=length,
            )
            if mp3_path:
                podcast_out_dir = os.path.dirname(mp3_path)
                script_path = os.path.join(podcast_out_dir, "script.md")
                print(f"[INFO] Podcast generated: {mp3_path}", file=sys.stderr)
            else:
                print("[ERROR] Podcast generation returned None", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Podcast failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    # PPT
    if ppt:
        try:
            from ..generators.ppt import generate_ppt
            # ⚠️ 2026-08-06：必須用 keyword — generate_ppt(script, title, lang, out_dir)
            # 舊 code 傳 positional 第三參數 → out_dir 被當 lang → PPT 存到 cwd！
            ppt_out = generate_ppt(content_for_gen, title, lang=lang, out_dir=out_dir, scheme=ppt_scheme)
            print(f"[INFO] PPT generated: {ppt_out}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] PPT failed: {e}", file=sys.stderr)

    # Visual
    if visual:
        try:
            from ..generators.visual import generate_visual
            # ⚠️ 同 PPT：必須用 keyword（generate_visual(script, title, lang, out_dir)）
            vis_out = generate_visual(content_for_gen, title, lang=lang, out_dir=out_dir)
            print(f"[INFO] Visual generated: {vis_out}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Visual failed: {e}", file=sys.stderr)

    # 8. Convert to Traditional Chinese for zh/zh-TW outputs
    if lang and lang.startswith("zh"):
        _convert_to_traditional(out_dir)

    # 9. chmod all outputs
    import subprocess
    for p in [out_dir, podcast_out_dir, ppt_out, vis_out]:
        if p and os.path.exists(p):
            subprocess.run(["chmod", "-R", "777", p], capture_output=True)

    return ppt_out, vis_out


def run_pipeline(source: str, organize: bool = False,
                 podcast: str = None, ppt: bool = False, visual: bool = False,
                 lang: str = "auto", voice_a: str = None, voice_b: str = None,
                 ppt_scheme: str = "dark", length: str = "long"):
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
        ppt_scheme: PPT color scheme (dark/blue/green/light)
    """
    today = date.today().strftime("%Y-%m-%d")

    # 0. 🔴 2026-08-06 script 重用：同影片已有 script.md → 跳過下載/轉寫/LLM，
    #    直接吃現成口播腳本產出（PPT/圖卡/口播）。避免 yt-dlp 暫態失敗整支 job 掛掉
    #    並省下大量時間與 API 額度。
    existing = _find_existing_script(source)
    if existing:
        reuse_title, script_content, reuse_dir = existing
        title = reuse_title or "Untitled"
        out_dir = str(reuse_dir)
        print(f"[INFO] ⚡ 重用既有口播腳本: {os.path.basename(out_dir)} — 跳過下載/轉寫/LLM", file=sys.stderr)
        print(f"[INFO] Script reused: {title} ({len(script_content)} chars)", file=sys.stderr)
        _generate_outputs(source, title, script_content, out_dir,
                          podcast=podcast, ppt=ppt, visual=visual,
                          lang=lang, voice_a=voice_a, voice_b=voice_b,
                          ppt_scheme=ppt_scheme, length=length)
        print(f"\n✅ Pipeline complete! Output: {out_dir}", file=sys.stderr)
        return out_dir

    # 1. Detect source type and extract
    extractor = detect_source(source)
    print(f"[INFO] Source type: {extractor.__class__.__name__}", file=sys.stderr)
    result = extractor.extract(source)

    title = result.metadata.get("title", "Untitled")
    source_id = result.source_id
    print(f"[INFO] Extracted: {title} ({len(result.text)} chars)", file=sys.stderr)

    # 2. Translate title for directory naming
    # ⚠️ 2026-07-31 使用者指示：口播腳本用免費模型（OpenCode Zen），翻譯也走 Zen
    dir_title = title
    if lang and lang not in ("auto", "en") and title:
        translated = _translate_title(title, lang)
        if translated:
            dir_title = translated
            print(f"[INFO] Translated title: {dir_title}", file=sys.stderr)

    # 3. Create output directory — 2026-08-07 統一放在口播資料夾
    safe_dir_title = _sanitize_filename(dir_title)
    out_dir = os.path.join(OBSIDIAN_BASE, PODCAST_SUBDIR, f"{safe_dir_title} [{source_id}]")
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

    # 7. Generate outputs（共用函數：podcast/ppt/visual + 繁中 + chmod）
    content_for_gen = organized or result.text
    _generate_outputs(source, title, content_for_gen, out_dir,
                      podcast=podcast, ppt=ppt, visual=visual,
                      lang=lang, voice_a=voice_a, voice_b=voice_b,
                      ppt_scheme=ppt_scheme, length=length)

    print(f"\n✅ Pipeline complete! Output: {out_dir}", file=sys.stderr)
    return out_dir
