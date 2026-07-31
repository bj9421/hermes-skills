#!/usr/bin/env python3
"""
yt2md_pipeline.py — YouTube video to Markdown converter.

Three pipelines (auto-fallback):
  1. youtube-transcript-api (cleanest, default)
  2. yt-dlp VTT subtitles
  3. yt-dlp + faster-whisper (videos without subtitles)

Optional: --organize  Post-process transcript via LLM into structured notes.
Optional: --podcast   Generate podcast audio (solo/dual) from transcript.
          --ppt      Generate PowerPoint presentation from transcript.
          --visual   Generate visual summary image (NotebookLM-style).

Usage:
    uv run python3 yt2md_pipeline.py "URL"                       # auto-detect
    uv run python3 yt2md_pipeline.py "URL" --whisper             # force Whisper
    uv run python3 yt2md_pipeline.py "URL" --model tiny          # custom Whisper model
    uv run python3 yt2md_pipeline.py "URL" -o out.md             # save to file
    uv run python3 yt2md_pipeline.py "URL" --obsidian            # save to Obsidian (YouTube/)
    uv run python3 yt2md_pipeline.py "URL" --obsidian 我的筆記/yt2md  # save to custom subfolder
    uv run python3 yt2md_pipeline.py "URL" --organize            # LLM-organized notes
    uv run python3 yt2md_pipeline.py "URL" --organize --obsidian "我的筆記/yt2md"
    uv run python3 yt2md_pipeline.py "URL" --organize --no-raw   # skip raw backup file
    uv run python3 yt2md_pipeline.py "URL" --podcast dual        # dual-host podcast
    uv run python3 yt2md_pipeline.py "URL" --podcast solo        # solo podcast
    uv run python3 yt2md_pipeline.py "URL" --podcast dual --lang zh  # Chinese podcast from English video
    uv run python3 yt2md_pipeline.py "URL" --ppt --visual        # PPT + visual summary
    uv run python3 yt2md_pipeline.py "URL" --podcast dual --ppt --visual --lang zh  # all outputs
"""

import sys
import os

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
import subprocess
import tempfile
import re
import shutil
import json
from pathlib import Path
from datetime import date


OBSIDIAN_BASE = "/opt/data/obsidian-vault"
DEFAULT_OBSIDIAN_SUBDIR = "YouTube"
PODCAST_SUBDIR = "口播"

# LLM config — reads from environment (set in .env or shell)
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_ORGANIZE_MODEL", "deepseek-ai/deepseek-v4-flash")
LLM_MAX_CHARS = 25000   # chunk threshold
LLM_OVERLAP_CHARS = 1000


# ---------------------------------------------------------------------------
# Pipeline 1: youtube-transcript-api (cleanest)
# ---------------------------------------------------------------------------
def fetch_via_api(url: str) -> tuple[str | None, str | None]:
    """Try youtube-transcript-api (v1.x). Returns (text, lang) or (None, None)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        video_id = _extract_video_id(url)
        if not video_id:
            return None, None

        api = YouTubeTranscriptApi()

        # Try with language priority
        transcript = None
        detected_lang = "unknown"
        lang_priority = ["zh-TW", "zh-Hant", "zh-Hans", "en"]
        for lang in lang_priority:
            try:
                result = api.fetch(video_id, languages=[lang])
                transcript = [
                    {"text": seg.text, "start": seg.start}
                    for seg in result
                ]
                detected_lang = lang
                break
            except Exception:
                continue

        if not transcript:
            try:
                result = api.fetch(video_id)
                transcript = [
                    {"text": seg.text, "start": seg.start}
                    for seg in result
                ]
                detected_lang = "auto-detected"
            except Exception:
                return None, None

        if not transcript:
            return None, None

        lines = []
        for seg in transcript:
            lines.append(seg['text'].strip())

        return "\n\n".join(lines), detected_lang

    except Exception as e:
        print(f"[WARN] youtube-transcript-api failed: {e}", file=sys.stderr)
        return None, None


# ---------------------------------------------------------------------------
# Pipeline 2: yt-dlp VTT
# ---------------------------------------------------------------------------
def fetch_via_vtt(yt_dlp_path, url, temp_dir) -> str | None:
    """Download VTT subtitles via yt-dlp. Returns clean text or None."""
    cmd = [
        yt_dlp_path, "--write-subs", "--write-auto-subs",
        "--sub-lang", "any", "--sub-format", "vtt",
        "--skip-download",
        "--output", os.path.join(temp_dir, "%(title)s [%(id)s].%(ext)s"),
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    vtt_files = list(Path(temp_dir).glob("*.vtt"))
    if not vtt_files:
        for lang in ["zh-TW", "zh-Hant", "zh-Hans", "en", "ja"]:
            cmd2 = [
                yt_dlp_path, "--write-auto-subs",
                "--sub-lang", lang, "--sub-format", "vtt",
                "--skip-download",
                "--output", os.path.join(temp_dir, "%(title)s [%(id)s].%(ext)s"),
                url,
            ]
            subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
            vtt_files = list(Path(temp_dir).glob("*.vtt"))
            if vtt_files:
                break

    if not vtt_files:
        return None
    return _vtt_to_text(str(vtt_files[0]))


def _vtt_to_text(vtt_path: str) -> str:
    """Extract clean continuous text from VTT, joining split lines."""
    lines = []
    current = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("WEBVTT"):
                continue
            if "-->" in line:
                if current:
                    lines.append(" ".join(current))
                    current = []
                continue
            if line.startswith("Kind:") or line.startswith("Language:"):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            if line:
                current.append(line)
    if current:
        lines.append(" ".join(current))
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline 3: Whisper (fallback)
# ---------------------------------------------------------------------------
_WHISPER_MODEL = None

def _get_whisper(model_size: str = "small"):
    global _WHISPER_MODEL
    if _WHISPER_MODEL and _WHISPER_MODEL[0] == model_size:
        return _WHISPER_MODEL[1]
    from faster_whisper import WhisperModel
    print(f"[INFO] Loading Whisper '{model_size}' (CPU int8)...", file=sys.stderr)
    _WHISPER_MODEL = (model_size, WhisperModel(model_size, device="cpu", compute_type="int8"))
    return _WHISPER_MODEL[1]


def _transcribe(audio_path: str, model_size: str = "small") -> str:
    model = _get_whisper(model_size)
    print(f"[INFO] Transcribing {audio_path} ...", file=sys.stderr)
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    lang = getattr(info, "language", "unknown")
    print(f"[INFO] Detected language: {lang}", file=sys.stderr)
    lines = []
    for seg in segments:
        lines.append(seg.text.strip())
    return "\n\n".join(lines)


def _download_audio(yt_dlp_path, url, temp_dir) -> Path | None:
    out = os.path.join(temp_dir, "audio.%(ext)s")
    cmd = [yt_dlp_path, "-x", "--audio-format", "wav", "--audio-quality", "0", "--output", out, url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    wavs = list(Path(temp_dir).glob("*.wav"))
    if wavs:
        return wavs[0]
    for ext in ["m4a", "mp3", "opus", "webm"]:
        f = Path(temp_dir) / f"audio.{ext}"
        if f.exists():
            return f
    return None


# ---------------------------------------------------------------------------
# LLM Organize (--organize)
# ---------------------------------------------------------------------------
_ORGANIZE_PROMPT = """你是一個專業的內容整理助手。請將以下 YouTube 影片逐字稿整理成結構化筆記。

要求：
1. 【重點摘要】— 3-5 個核心要點（bullet points），用 **粗體** 標示關鍵詞
2. 【內容整理】— 根據主題分段，每段加 ## 標題，段落之間邏輯連貫
3. 【精簡文字】— 去除贅字、口語重複、語助詞（嗯、啊、那個、就是說），保留完整語意
4. 【時間標記】— 在每個主要段落開頭保留 [MM:SS] 或 [HH:MM:SS] 時間戳（來自原文）
5. 語言：與原文相同（中文影片用中文回覆，英文影片用英文回覆）
6. 不要加你自己的評論或額外資訊，忠於原文內容

逐字稿：
"""


def _get_llm_client():
    """Create OpenAI-compatible client pointing at NVIDIA API."""
    api_key = NVIDIA_API_KEY
    if not api_key:
        # Try reading from .env file
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
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def _chunk_transcript(text: str, max_chars: int = LLM_MAX_CHARS, overlap: int = LLM_OVERLAP_CHARS) -> list[str]:
    """Split transcript into chunks at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2  # +2 for \n\n
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            # Keep overlap: last paragraphs
            overlap_text = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) > overlap:
                    break
                overlap_text.insert(0, p)
                overlap_len += len(p) + 2
            current = overlap_text
            current_len = overlap_len
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _organize_via_llm(transcript: str, title: str = "") -> str | None:
    """Send transcript to LLM for organization. Returns organized markdown or None.

    ⚠️ 2026-07-31 使用者指示：LLM 整理文檔一律用 Zen，不用 NVIDIA（NVIDIA 僅供 Whisper）。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from notehub.core.llm import call_zen
    except ImportError:
        call_zen = None
    if not call_zen:
        print("[WARN] call_zen unavailable — skipping organize", file=sys.stderr)
        return None

    chunks = _chunk_transcript(transcript)
    total_chunks = len(chunks)
    print(f"[INFO] Organizing via Zen LLM ({total_chunks} chunk{'s' if total_chunks > 1 else ''})...", file=sys.stderr)

    organized_parts = []
    for i, chunk in enumerate(chunks):
        if total_chunks > 1:
            prefix = f"[Chunk {i+1}/{total_chunks}] "
            print(f"[INFO] {prefix}Processing...", file=sys.stderr)
        else:
            prefix = ""

        prompt = _ORGANIZE_PROMPT + chunk
        if total_chunks > 1 and i == 0:
            prompt += "\n\n（這是多段處理的第 1 段，後續還有。請先整理這段內容，最後一段再加總摘要。）"
        elif total_chunks > 1 and i == total_chunks - 1:
            prompt += "\n\n（這是最後一段。請在整理完本段後，附上整部影片的【重點摘要】。）"

        try:
            result = call_zen(
                [
                    {"role": "system", "content": "你是專業的內容整理助手，擅長將逐字稿轉化為結構化筆記。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4096,
                temperature=0.3,
            )
            if result:
                organized_parts.append(result.strip())
            else:
                print(f"[WARN] Zen returned empty for chunk {i+1}", file=sys.stderr)
                organized_parts.append(chunk)
        except Exception as e:
            print(f"[WARN] Zen organize chunk {i+1} failed: {e}", file=sys.stderr)
            organized_parts.append(chunk)

    return "\n\n---\n\n".join(organized_parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt_ts(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS."""
    total = int(seconds)
    h, m = divmod(total, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _get_video_title(url: str) -> str:
    """Try to get video title via yt-dlp."""
    yt_dlp = shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"
    try:
        result = subprocess.run(
            [yt_dlp, "--print", "title", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    # Fallback: use video ID instead of generic "YouTube Video"
    vid = _extract_video_id(url)
    return f"Video {vid}" if vid else "YouTube Video"


def _sanitize_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s[:120]  # keep it reasonable


def _build_raw_md(title: str, url: str, md: str, lang: str, source: str, today: str) -> str:
    """Build raw transcript markdown with frontmatter."""
    content_parts = [
        "---",
        f"created: {today}",
        f"source: {url}",
        f"title: {title}",
        f"language: {lang}",
        f"pipeline: {source}",
        "tags: [youtube, transcript]",
        "---",
        "",
        f"# {title}",
        "",
        f"> {url}",
        "",
        md,
    ]
    return "\n".join(content_parts)


def _build_organized_md(title: str, url: str, organized: str, lang: str, source: str, today: str) -> str:
    """Build organized note markdown with frontmatter."""
    content_parts = [
        "---",
        f"created: {today}",
        f"source: {url}",
        f"title: {title}",
        f"language: {lang}",
        f"pipeline: {source}",
        "type: organized",
        "tags: [youtube, notes]",
        "---",
        "",
        f"# {title}",
        "",
        f"> {url}",
        "",
        organized,
    ]
    return "\n".join(content_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: yt2md_pipeline.py <URL> [-o out.md] [--whisper] [--model SIZE] [--obsidian] [--organize] [--no-raw]",
              file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    args = sys.argv[2:]
    output_path = None
    force_whisper = "--whisper" in args
    model_size = "small"
    save_to_obsidian = "--obsidian" in args
    obsidian_subdir = DEFAULT_OBSIDIAN_SUBDIR
    do_organize = "--organize" in args
    keep_raw = "--no-raw" not in args  # default: keep raw

    # Podcast flags
    podcast_mode = None  # None, "solo", or "dual"
    voice_a = None
    voice_b = None
    target_lang = "auto"
    if "--podcast" in args:
        idx = args.index("--podcast")
        if idx + 1 < len(args) and args[idx + 1] in ("solo", "dual"):
            podcast_mode = args[idx + 1]
        else:
            podcast_mode = "dual"  # default to dual
    if "--voice-a" in args:
        idx = args.index("--voice-a")
        if idx + 1 < len(args):
            voice_a = args[idx + 1]
    if "--voice-b" in args:
        idx = args.index("--voice-b")
        if idx + 1 < len(args):
            voice_b = args[idx + 1]
    if "--lang" in args:
        idx = args.index("--lang")
        if idx + 1 < len(args):
            target_lang = args[idx + 1]

    # PPT and visual summary flags
    do_ppt = "--ppt" in args
    do_visual = "--visual" in args
    ppt_out = None
    vis_out = None

    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            model_size = args[idx + 1]
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 < len(args):
            output_path = args[idx + 1]
    if save_to_obsidian:
        # Check if --obsidian is followed by a subdirectory name
        idx = args.index("--obsidian")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            obsidian_subdir = args[idx + 1]

    # Get video metadata early
    title = _get_video_title(url)
    today = date.today().strftime("%Y-%m-%d")
    video_id = _extract_video_id(url) or ""
    safe_title = _sanitize_filename(title)

    # Translate title for directory naming when target lang differs
    dir_title = title
    if target_lang and target_lang not in ("auto", "en") and title:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from podcast import _translate_title
            translated = _translate_title(title, target_lang)
            if translated:
                dir_title = translated
                print(f"[INFO] Translated title: {dir_title}", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Title translation failed: {e}", file=sys.stderr)

    # Try pipelines in order
    md = None
    lang = "unknown"
    source = "unknown"

    if not force_whisper:
        # Pipeline 1: youtube-transcript-api
        print("[INFO] Trying youtube-transcript-api...", file=sys.stderr)
        text, lang = fetch_via_api(url)
        if text:
            md = text
            source = "transcript-api"

    if not md and not force_whisper:
        # Pipeline 2: yt-dlp VTT
        yt_dlp = shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"
        if not os.path.exists(yt_dlp):
            print("[WARN] yt-dlp not found, skipping VTT pipeline", file=sys.stderr)
        else:
            with tempfile.TemporaryDirectory(prefix="yt2md_vtt_") as tmpdir:
                print("[INFO] Trying yt-dlp VTT subtitles...", file=sys.stderr)
                text = fetch_via_vtt(yt_dlp, url, tmpdir)
                if text:
                    md = text
                    source = "vtt"

    if not md:
        # Pipeline 3: Whisper
        yt_dlp = shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"
        if not os.path.exists(yt_dlp):
            print("[ERROR] yt-dlp not found. Install: uv pip install yt-dlp", file=sys.stderr)
            sys.exit(1)

        with tempfile.TemporaryDirectory(prefix="yt2md_whisper_") as tmpdir:
            print("[INFO] No subtitles. Switching to Whisper transcription...", file=sys.stderr)
            audio = _download_audio(yt_dlp, url, tmpdir)
            if not audio:
                print("[ERROR] Cannot download audio for this video.", file=sys.stderr)
                sys.exit(1)
            size_mb = audio.stat().st_size / 1024 / 1024
            print(f"[INFO] Audio: {audio.name} ({size_mb:.1f} MB)", file=sys.stderr)
            md = _transcribe(str(audio), model_size=model_size)
            source = f"whisper-{model_size}"

    if not md:
        print("[ERROR] No content generated from any pipeline.", file=sys.stderr)
        sys.exit(1)

    # --podcast mode: produce podcast audio
    podcast_out_dir = None
    if podcast_mode:
        try:
            # Add sys.path for podcast module import
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from podcast import produce_podcast

            podcast_kwargs = {"lang": target_lang, "mode": podcast_mode}
            if voice_a:
                podcast_kwargs["voice_a"] = voice_a
            if voice_b:
                podcast_kwargs["voice_b"] = voice_b

            # Pre-compute output dir so podcast module doesn't double-translate
            safe_title_dir = _sanitize_filename(dir_title)
            vid_part = f" [{video_id}]" if video_id else ""
            podcast_out_dir = os.path.join(OBSIDIAN_BASE, PODCAST_SUBDIR, f"{safe_title_dir}{vid_part}")
            os.makedirs(podcast_out_dir, exist_ok=True)
            podcast_kwargs["out_dir"] = podcast_out_dir

            mp3_path = produce_podcast(md, title, url, video_id=video_id, **podcast_kwargs)
            if mp3_path:
                print(f"[OK] Podcast produced: {mp3_path}", file=sys.stderr)
            else:
                print("[WARN] Podcast production failed", file=sys.stderr)
        except ImportError as e:
            print(f"[ERROR] Podcast module not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Podcast production error: {e}", file=sys.stderr)

    # --ppt mode: generate PowerPoint presentation
    if do_ppt:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from ppt_gen import generate_ppt

            # Determine output directory for PPT
            if podcast_mode:
                ppt_out = podcast_out_dir
            elif save_to_obsidian:
                ppt_out = os.path.join(OBSIDIAN_BASE, obsidian_subdir)
            elif output_path:
                ppt_out = os.path.dirname(output_path) or "."
            else:
                ppt_out = None
            if ppt_out:
                os.makedirs(ppt_out, exist_ok=True)
                ppt_path = generate_ppt(md, dir_title, lang=target_lang, out_dir=ppt_out)
                if ppt_path:
                    print(f"[OK] PPT produced: {ppt_path}", file=sys.stderr)
        except ImportError as e:
            print(f"[ERROR] PPT module not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] PPT production error: {e}", file=sys.stderr)

    # --visual mode: generate visual summary image
    if do_visual:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from visual_gen import generate_visual

            # Determine output directory for visual
            if podcast_mode:
                vis_out = podcast_out_dir
            elif save_to_obsidian:
                vis_out = os.path.join(OBSIDIAN_BASE, obsidian_subdir)
            elif output_path:
                vis_out = os.path.dirname(output_path) or "."
            else:
                vis_out = None
            if vis_out:
                os.makedirs(vis_out, exist_ok=True)
                vis_path = generate_visual(md, dir_title, lang=target_lang, out_dir=vis_out)
                if vis_path:
                    print(f"[OK] Visual summary produced: {vis_path}", file=sys.stderr)
        except ImportError as e:
            print(f"[ERROR] Visual module not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Visual production error: {e}", file=sys.stderr)

    # Final chmod sweep for Syncthing compatibility
    chmod_target = podcast_out_dir
    if not chmod_target and do_ppt:
        chmod_target = ppt_out
    if not chmod_target and do_visual:
        chmod_target = vis_out
    if chmod_target:
        import subprocess as _sp
        _sp.run(["chmod", "-R", "777", chmod_target], capture_output=True)

    # Build raw markdown
    raw_md = _build_raw_md(title, url, md, lang, source, today)

    # Determine output directory
    if save_to_obsidian:
        obsidian_dir = os.path.join(OBSIDIAN_BASE, obsidian_subdir)
        os.makedirs(obsidian_dir, exist_ok=True)
        out_dir = obsidian_dir
    elif output_path:
        out_dir = os.path.dirname(output_path) or "."
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = None

    # Save raw transcript (unless --organize without --no-raw, or plain mode)
    if do_organize and keep_raw and out_dir:
        raw_path = os.path.join(out_dir, f"{safe_title}_raw.md")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(raw_md)
        print(f"[OK] Raw saved: {raw_path}", file=sys.stderr)
    elif not do_organize and out_dir:
        # Plain mode: save raw as the main file
        main_path = os.path.join(out_dir, f"{safe_title}.md")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(raw_md)
        line_count = raw_md.count("\n") + 1
        print(f"[OK] Saved: {main_path}  ({line_count} lines, {source})", file=sys.stderr)
        return
    elif not do_organize and not out_dir:
        sys.stdout.write(raw_md)
        return

    # --organize mode: run LLM
    if do_organize:
        organized = _organize_via_llm(md, title)
        if not organized:
            print("[WARN] LLM organize failed — saving raw only", file=sys.stderr)
            if out_dir:
                fallback_path = os.path.join(out_dir, f"{safe_title}.md")
                with open(fallback_path, "w", encoding="utf-8") as f:
                    f.write(raw_md)
                print(f"[OK] Fallback saved: {fallback_path}", file=sys.stderr)
            else:
                sys.stdout.write(raw_md)
            return

        organized_md = _build_organized_md(title, url, organized, lang, source, today)

        if out_dir:
            organized_path = os.path.join(out_dir, f"{safe_title}.md")
            with open(organized_path, "w", encoding="utf-8") as f:
                f.write(organized_md)
            line_count = organized_md.count("\n") + 1
            print(f"[OK] Organized saved: {organized_path}  ({line_count} lines, {source})", file=sys.stderr)
        else:
            sys.stdout.write(organized_md)


if __name__ == "__main__":
    main()
