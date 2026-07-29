"""Instagram Reel extractor — downloads audio via yt-dlp + transcribes via Groq Whisper.

Instagram videos have no auto-captions, so this bypasses the standard subtitles
pipeline and goes straight to audio → speech-to-text.

Groq limit: ~10MB per file (413 Request Entity Too Large if exceeded).
IG Reels are typically 1-3 min / 2-4MB — usually safe.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from .base import BaseExtractor, ExtractResult


def _extract_reel_id(url: str) -> str | None:
    """Extract the shortcode from instagram.com/reel/SHORTCODE/ or /p/SHORTCODE/"""
    patterns = [
        r"(?:instagram\.com/)(?:reel|p)/([a-zA-Z0-9_-]+)",
        r"^([a-zA-Z0-9_-]+)$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _find_ytdlp() -> str:
    """Locate yt-dlp binary."""
    import shutil
    return shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"


def _get_instagram_metadata(url: str) -> dict:
    """Get title and description from Instagram via yt-dlp.

    Instagram's yt-dlp title is always "Video by username".
    The real topic is in the description's first non-empty line.
    """
    yt_dlp = _find_ytdlp()
    try:
        result = subprocess.run(
            [yt_dlp, "--print", "title,description", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().split("\n")
        title_line = lines[0] if lines else "Instagram Video"
        # Description starts from line 1; first paragraph is the real content
        desc_lines = [l.strip() for l in lines[1:] if l.strip()]
        # yt-dlp separates description lines. First non-empty is the caption/title
        real_title = desc_lines[0] if desc_lines else title_line
        # Clean up hashtags from title
        real_title = re.sub(r"\s*#[^\s#]+", "", real_title).strip()
        full_desc = "\n".join(desc_lines)
        return {"title": real_title, "description": full_desc, "raw_title": title_line}
    except Exception as e:
        print(f"[WARN] yt-dlp metadata failed: {e}", file=sys.stderr)
        return {"title": "Instagram Video", "description": ""}


def _download_audio(url: str, reel_id: str) -> str | None:
    """Download audio via yt-dlp. Returns path to downloaded file or None."""
    yt_dlp = _find_ytdlp()
    out_template = f"/tmp/audio/{reel_id}.%(ext)s"
    os.makedirs("/tmp/audio", exist_ok=True)

    cmd = [
        yt_dlp, "-x", "--audio-format", "m4a",
        "-o", out_template, url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[ERROR] yt-dlp audio download failed: {result.stderr.strip()}", file=sys.stderr)
        return None

    # Find the actual file
    for ext in ["m4a", "mp4", "webm"]:
        path = f"/tmp/audio/{reel_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


def _check_size_and_compress(path: str, max_bytes: int = 9 * 1024 * 1024) -> str:
    """Check file size against Groq limit. Compress to opus if too large."""
    size = os.path.getsize(path)
    if size < max_bytes:
        return path  # Fine as-is

    # Compress: m4a → opus at 32k (typically 14MB → ~4.5MB)
    opus_path = path.rsplit(".", 1)[0] + ".opus"
    print(f"[INFO] Audio {size/1024/1024:.1f}MB exceeds Groq limit, compressing...", file=sys.stderr)
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-c:a", "libopus", "-b:a", "32k", opus_path],
        capture_output=True, text=True, timeout=60,
    )
    if os.path.exists(opus_path):
        print(f"[INFO] Compressed: {os.path.getsize(opus_path)/1024/1024:.1f}MB", file=sys.stderr)
        return opus_path
    print(f"[WARN] Compression failed, using original file", file=sys.stderr)
    return path


def _transcribe_with_groq(audio_path: str) -> str | None:
    """Transcribe audio via Groq Whisper API. Returns transcript text."""
    # Get Groq API key from .env
    env_path = "/opt/data/.env"
    groq_key = None
    try:
        with open(env_path) as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped.startswith("GROQ_API_KEY="):
                    groq_key = line_stripped.split("=", 1)[1]
                    break
    except Exception as e:
        print(f"[ERROR] Cannot read {env_path}: {e}", file=sys.stderr)
        return None

    if not groq_key:
        print(f"[ERROR] GROQ_API_KEY not found in {env_path}", file=sys.stderr)
        return None

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        with open(audio_path, "rb") as f:
            # Determine filename extension for mime type
            ext = os.path.splitext(audio_path)[1] or ".m4a"
            result = client.audio.transcriptions.create(
                file=(f"audio{ext}", f),
                model="whisper-large-v3",
                language="zh",
                response_format="verbose_json",
            )
        text = result.text.strip()
        print(f"[OK] Groq Whisper: {len(text)} chars, {getattr(result, 'duration', '?')}s", file=sys.stderr)
        return text
    except Exception as e:
        print(f"[ERROR] Groq Whisper failed: {e}", file=sys.stderr)
        return None


class InstagramExtractor(BaseExtractor):
    """Extract audio transcript from Instagram Reels via yt-dlp + Groq Whisper."""

    INSTAGRAM_PATTERNS = [
        r"instagram\.com/(?:reel|p)/",
    ]

    def detect(self, input_path: str) -> bool:
        return any(re.search(p, input_path) for p in self.INSTAGRAM_PATTERNS)

    def extract(self, input_path: str) -> ExtractResult:
        reel_id = _extract_reel_id(input_path)
        if not reel_id:
            raise ValueError(f"Cannot extract reel ID from: {input_path}")

        # 1. Get metadata (title from description)
        meta = _get_instagram_metadata(input_path)
        title = meta.get("title", "Instagram Video")

        # 2. Download audio
        audio_path = _download_audio(input_path, reel_id)
        if not audio_path or not os.path.exists(audio_path):
            raise RuntimeError(f"Failed to download audio from Instagram reel {reel_id}")

        try:
            # 3. Check file size and compress if needed
            audio_path = _check_size_and_compress(audio_path)

            # 4. Transcribe with Groq Whisper
            text = _transcribe_with_groq(audio_path)
            if not text:
                raise RuntimeError(f"Groq Whisper transcription failed for reel {reel_id}")

            return ExtractResult(
                text=text,
                metadata={"title": title, "language": "zh", "reel_id": reel_id,
                          "description": meta.get("description", "")},
                source_type="instagram",
                source_id=reel_id,
            )
        finally:
            # Clean up downloaded audio (temp files)
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass

    def get_metadata(self, input_path: str) -> dict:
        meta = _get_instagram_metadata(input_path)
        reel_id = _extract_reel_id(input_path) or ""
        return {"title": meta.get("title", "Instagram Video"), "reel_id": reel_id}
