"""YouTube source extractor — pulls transcripts from YouTube videos.

Three extraction strategies (auto-fallback):
  1. youtube-transcript-api (cleanest, default)
  2. yt-dlp VTT subtitles
  3. yt-dlp + faster-whisper (videos without subtitles)
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from .base import BaseExtractor, ExtractResult


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


def _fetch_via_api(video_id: str) -> tuple[str | None, str | None]:
    """Try youtube-transcript-api (v1.x). Returns (text, lang) or (None, None)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        transcript = None
        detected_lang = "unknown"
        lang_priority = ["zh-TW", "zh-Hant", "zh-Hans", "en"]
        for lang in lang_priority:
            try:
                result = api.fetch(video_id, languages=[lang])
                transcript = [{"text": seg.text, "start": seg.start} for seg in result]
                detected_lang = lang
                break
            except Exception:
                continue

        if not transcript:
            try:
                result = api.fetch(video_id)
                transcript = [{"text": seg.text, "start": seg.start} for seg in result]
                detected_lang = "auto-detected"
            except Exception:
                return None, None

        if not transcript:
            return None, None

        lines = [seg["text"].strip() for seg in transcript]
        return "\n\n".join(lines), detected_lang

    except Exception as e:
        print(f"[WARN] youtube-transcript-api failed: {e}", file=sys.stderr)
        return None, None


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


def _fetch_via_vtt(yt_dlp_path: str, url: str, temp_dir: str) -> str | None:
    """Download VTT subtitles via yt-dlp."""
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


def _get_video_title(url: str) -> str:
    """Get video title via yt-dlp."""
    yt_dlp = _find_ytdlp()
    try:
        result = subprocess.run(
            [yt_dlp, "--print", "title", "--no-warnings", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    vid = _extract_video_id(url)
    return f"Video {vid}" if vid else "YouTube Video"


def _find_ytdlp() -> str:
    """Locate yt-dlp binary."""
    import shutil
    return shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"


class YouTubeExtractor(BaseExtractor):
    """Extract transcripts from YouTube videos."""

    YOUTUBE_PATTERNS = [
        r"youtube\.com/watch",
        r"youtu\.be/",
        r"youtube\.com/embed/",
    ]

    def detect(self, input_path: str) -> bool:
        return any(re.search(p, input_path) for p in self.YOUTUBE_PATTERNS)

    def extract(self, input_path: str) -> ExtractResult:
        video_id = _extract_video_id(input_path)
        if not video_id:
            raise ValueError(f"Cannot extract video ID from: {input_path}")

        title = _get_video_title(input_path)

        # Strategy 1: youtube-transcript-api
        text, lang = _fetch_via_api(video_id)
        if text:
            return ExtractResult(
                text=text,
                metadata={"title": title, "language": lang, "video_id": video_id},
                source_type="youtube",
                source_id=video_id,
            )

        # Strategy 2: yt-dlp VTT
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            yt_dlp = _find_ytdlp()
            text = _fetch_via_vtt(yt_dlp, input_path, tmp)
            if text:
                return ExtractResult(
                    text=text,
                    metadata={"title": title, "language": "vtt", "video_id": video_id},
                    source_type="youtube",
                    source_id=video_id,
                )

        raise RuntimeError(f"Failed to extract transcript for video {video_id}")

    def get_metadata(self, input_path: str) -> dict:
        video_id = _extract_video_id(input_path) or ""
        title = _get_video_title(input_path)
        return {"title": title, "video_id": video_id}
