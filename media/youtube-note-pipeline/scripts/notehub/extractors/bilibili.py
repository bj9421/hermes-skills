"""Bilibili video extractor — downloads audio via yt-dlp + transcribes via Groq Whisper.

Bilibili requires login for subtitles, so we bypass the standard subtitles
pipeline and go straight to audio → speech-to-text (same as Instagram).

Groq limit: ~10MB per file (413 Request Entity Too Large if exceeded).
Bilibili videos can be longer (10-30 min), so compression may be needed.
"""

import os
import re
import subprocess
import sys

from .base import BaseExtractor, ExtractResult


def _extract_bvid(url: str) -> str | None:
    """Extract BV id from bilibili.com/video/BV... or b23.tv/..."""
    patterns = [
        r"(?:bilibili\.com/video/)(BV[a-zA-Z0-9]+)",
        r"(?:b23\.tv/)([a-zA-Z0-9]+)",
        r"^(BV[a-zA-Z0-9]+)$",
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


def _get_bilibili_metadata(url: str) -> dict:
    """Get title and description from Bilibili via yt-dlp.

    Bilibili's yt-dlp title is the actual video title (unlike Instagram).
    """
    yt_dlp = _find_ytdlp()
    try:
        result = subprocess.run(
            [yt_dlp, "--print", "title,description", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().split("\n")
        title = lines[0] if lines else "Bilibili Video"
        desc_lines = [l.strip() for l in lines[1:] if l.strip()]
        return {"title": title, "description": "\n".join(desc_lines)}
    except Exception as e:
        print(f"[WARN] yt-dlp metadata failed: {e}", file=sys.stderr)
        return {"title": "Bilibili Video", "description": ""}


def _download_audio(url: str, bvid: str) -> str | None:
    """Download audio via yt-dlp. Returns path to downloaded file or None."""
    yt_dlp = _find_ytdlp()
    out_template = f"/tmp/audio/{bvid}.%(ext)s"
    os.makedirs("/tmp/audio", exist_ok=True)

    cmd = [
        yt_dlp, "-x", "--audio-format", "m4a",
        "-o", out_template, url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[ERROR] yt-dlp audio download failed: {result.stderr.strip()}", file=sys.stderr)
        return None

    for ext in ["m4a", "mp4", "webm"]:
        path = f"/tmp/audio/{bvid}.{ext}"
        if os.path.exists(path):
            return path
    return None


def _check_size_and_compress(path: str, max_bytes: int = 9 * 1024 * 1024) -> str:
    """Check file size against Groq limit. Compress to opus if too large."""
    size = os.path.getsize(path)
    if size < max_bytes:
        return path

    opus_path = path.rsplit(".", 1)[0] + ".opus"
    print(f"[INFO] Audio {size/1024/1024:.1f}MB exceeds Groq limit, compressing...", file=sys.stderr)
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-c:a", "libopus", "-b:a", "32k", opus_path],
        capture_output=True, text=True, timeout=60,
    )
    if os.path.exists(opus_path):
        print(f"[INFO] Compressed: {os.path.getsize(opus_path)/1024/1024:.1f}MB", file=sys.stderr)
        return opus_path
    print(f"[WARN] Compression failed, using original", file=sys.stderr)
    return path


def _transcribe_with_groq(audio_path: str) -> str | None:
    """Transcribe audio via Groq Whisper API. Returns transcript text."""
    env_path = "/opt/data/.env"
    groq_key = None
    try:
        with open(env_path) as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("GROQ_API_KEY="):
                    groq_key = stripped.split("=", 1)[1]
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


class BilibiliExtractor(BaseExtractor):
    """Extract transcript from Bilibili videos via yt-dlp + Groq Whisper."""

    BILIBILI_PATTERNS = [
        r"bilibili\.com/video/",
        r"b23\.tv/",
    ]

    def detect(self, input_path: str) -> bool:
        return any(re.search(p, input_path) for p in self.BILIBILI_PATTERNS)

    def extract(self, input_path: str) -> ExtractResult:
        bvid = _extract_bvid(input_path)
        if not bvid:
            raise ValueError(f"Cannot extract BV id from: {input_path}")

        # 1. Get metadata
        meta = _get_bilibili_metadata(input_path)
        title = meta.get("title", "Bilibili Video")

        # 2. Download audio
        audio_path = _download_audio(input_path, bvid)
        if not audio_path or not os.path.exists(audio_path):
            raise RuntimeError(f"Failed to download audio from Bilibili video {bvid}")

        try:
            # 3. Check file size and compress if needed
            audio_path = _check_size_and_compress(audio_path)

            # 4. Transcribe with Groq Whisper
            text = _transcribe_with_groq(audio_path)
            if not text:
                raise RuntimeError(f"Groq Whisper transcription failed for {bvid}")

            return ExtractResult(
                text=text,
                metadata={"title": title, "language": "zh", "bvid": bvid,
                          "description": meta.get("description", "")},
                source_type="bilibili",
                source_id=bvid,
            )
        finally:
            # Clean up downloaded audio
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass

    def get_metadata(self, input_path: str) -> dict:
        meta = _get_bilibili_metadata(input_path)
        bvid = _extract_bvid(input_path) or ""
        return {"title": meta.get("title", "Bilibili Video"), "bvid": bvid}
