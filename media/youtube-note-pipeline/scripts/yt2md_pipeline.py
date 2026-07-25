#!/usr/bin/env python3
"""
yt2md_pipeline.py — YouTube video to Markdown converter.

Three pipelines (auto-fallback):
  1. youtube-transcript-api (cleanest, default)
  2. yt-dlp VTT subtitles
  3. yt-dlp + faster-whisper (videos without subtitles)

Usage:
    uv run python3 yt2md_pipeline.py "URL"                       # auto-detect
    uv run python3 yt2md_pipeline.py "URL" --whisper             # force Whisper
    uv run python3 yt2md_pipeline.py "URL" --model tiny          # custom Whisper model
    uv run python3 yt2md_pipeline.py "URL" -o out.md             # save to file
    uv run python3 yt2md_pipeline.py "URL" --obsidian            # save to Obsidian (YouTube/)
    uv run python3 yt2md_pipeline.py "URL" --obsidian 我的筆記/yt2md  # save to custom subfolder
"""

import sys
import os
import subprocess
import tempfile
import re
import shutil
import json
from pathlib import Path
from datetime import date


OBSIDIAN_BASE = "/opt/data/obsidian-vault"
DEFAULT_OBSIDIAN_SUBDIR = "YouTube"


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
    try:
        result = subprocess.run(
            ["uv", "run", "yt-dlp", "--print", "title", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    return "YouTube Video"


def _sanitize_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s[:120]  # keep it reasonable


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: yt2md_pipeline.py <URL> [-o out.md] [--whisper] [--model SIZE] [--obsidian]",
              file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    args = sys.argv[2:]
    output_path = None
    force_whisper = "--whisper" in args
    model_size = "small"
    save_to_obsidian = "--obsidian" in args
    obsidian_subdir = DEFAULT_OBSIDIAN_SUBDIR

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

    # Build final Markdown with frontmatter
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
    final_md = "\n".join(content_parts)

    # Determine output path
    if save_to_obsidian:
        obsidian_dir = os.path.join(OBSIDIAN_BASE, obsidian_subdir)
        os.makedirs(obsidian_dir, exist_ok=True)
        out_path = os.path.join(obsidian_dir, f"{_sanitize_filename(title)}.md")
        output_path = out_path
    elif output_path:
        # Ensure parent dir exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_md)
        line_count = final_md.count("\n") + 1
        print(f"[OK] Saved: {output_path}  ({line_count} lines, {source})", file=sys.stderr)
    else:
        sys.stdout.write(final_md)


if __name__ == "__main__":
    main()
