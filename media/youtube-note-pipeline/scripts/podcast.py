#!/usr/bin/env python3
"""
podcast.py — Podcast production module for yt2md_pipeline.

Generates solo/dual-host podcast audio from YouTube transcripts.
Uses NVIDIA API for script generation, Edge TTS for voice synthesis,
pydub + ffmpeg for audio merging.

Usage (imported by yt2md_pipeline.py):
    from podcast import produce_podcast
    produce_podcast(transcript, title, url, lang, mode, voice_a, voice_b, out_dir)
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_ORGANIZE_MODEL", "deepseek-ai/deepseek-v4-flash")

DEFAULT_VOICE_A = "zh-TW-HsiaoChenNeural"   # 主持人（女）
DEFAULT_VOICE_B = "zh-TW-YunJheNeural"     # 評論員（男）
PODCAST_SUBDIR = "口播"


# ---------------------------------------------------------------------------
# LLM Client (reuses NVIDIA API from pipeline)
# ---------------------------------------------------------------------------
def _get_llm_client():
    api_key = NVIDIA_API_KEY
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
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


# ---------------------------------------------------------------------------
# Script Generation Prompts
# ---------------------------------------------------------------------------
_SOLO_PROMPT = """你是一個專業的播客腳本編寫者。請將以下逐字稿轉換為單人口播腳本。

要求：
1. 用第一人稱口語化講述，像在跟聽眾聊天
2. 保留原文的核心觀點和重要細節
3. 加入自然的過渡語句（「接下來我們來看...」「說到這個...」「有趣的是...」）
4. 去除贅字和口語重複，但保留自然的口語感
5. 開頭要有引言（介紹主題），結尾要有總結
6. 語言：{lang_instruction}
7. 不要加逐字稿中的時間標記 [MM:SS]
8. 長度：自然完整，不硬性截斷

直接輸出腳本文字，不要加標題或格式標記。每個段落之間空一行。

逐字稿：
"""


_DUAL_PROMPT = """你是一個專業的播客腳本編寫者。請將以下逐字稿轉換為雙主持人對談腳本。

角色：
- A（主持人）：引導話題、提問、總結
- B（評論員）：補充觀點、舉例、深入分析

格式規則：
- 每行以角色名開頭：「A:」或「B:」
- A 和 B 交替發言，不要連續同一個角色說超過 3 次
- A 負責開場和收尾
- 對話要自然流暢，像真實的播客節目
- B 的回應要有深度，不是簡單附和

要求：
1. 保留原文的核心觀點和重要細節
2. 去除贅字，但保留自然的口語感
3. 語言：{lang_instruction}
4. 不要加逐字稿中的時間標記 [MM:SS]
5. 長度：自然完整，不硬性截斷

直接輸出腳本，每行一個角色的台詞。段落之間空一行。

逐字稿：
"""


# ---------------------------------------------------------------------------
# Deduplication — detect and trim degenerate repetition loops
# ---------------------------------------------------------------------------
def _dedup_script(text: str) -> str:
    """Remove degenerate repetition loops from LLM output.
    
    Detects when the same line (or very similar line) repeats 3+ times in a row
    and truncates at the first repeat.
    """
    lines = text.split("\n")
    if len(lines) < 10:
        return text
    
    # Track consecutive near-duplicates
    seen = {}  # normalized_line -> count
    cutoff = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Normalize: remove leading role prefix (A: / B:) for comparison
        normalized = stripped
        for prefix in ("A:", "B:", "A：", "B："):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break
        if normalized in seen:
            seen[normalized] += 1
            if seen[normalized] >= 3 and cutoff is None:
                cutoff = i - 2  # keep up to 2 instances
                break
        else:
            seen[normalized] = 1
            # Reset counts for other lines (only track consecutive)
            if len(seen) > 1:
                # If we see a new unique line, reset — we only care about
                # rapid-fire repetition of the SAME thing
                prev_keys = [k for k in seen if k != normalized]
                for pk in prev_keys:
                    if seen[pk] < 3:
                        del seen[pk]
    
    if cutoff is not None:
        trimmed = "\n".join(lines[:cutoff])
        orig_lines = len(lines)
        kept = cutoff
        print(f"[INFO] Dedup: trimmed repetition at line {cutoff} ({kept}/{orig_lines} lines kept)", file=sys.stderr)
        return trimmed
    return text


# ---------------------------------------------------------------------------
# Title Translation — translate title for directory naming
# ---------------------------------------------------------------------------
_LANG_NAMES = {
    "zh": "繁體中文", "zh-TW": "繁體中文", "zh-CN": "简体中文",
    "ja": "日本語", "ko": "한국어", "en": "English",
    "es": "Español", "fr": "Français", "de": "Deutsch", "pt": "Português",
}

def _translate_title(title: str, target_lang: str) -> str | None:
    """Translate a video title to the target language via LLM (fast, short call)."""
    client = _get_llm_client()
    if not client:
        return None
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": f"你是翻譯專家。只翻譯標題，不加任何解釋、引號或額外文字。"},
                {"role": "user", "content": f"將以下英文標題翻譯成{lang_name}，直接輸出翻譯結果：\n\n{title}"},
            ],
            max_tokens=100,
            temperature=0.3,
        )
        result = response.choices[0].message.content
        if result:
            return result.strip().strip('"').strip("'").strip("《》")
    except Exception as e:
        print(f"[WARN] Title translation failed: {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Script Generation
# ---------------------------------------------------------------------------
def _generate_script(transcript: str, title: str, mode: str, target_lang: str) -> str | None:
    """Generate podcast script via NVIDIA LLM.

    Args:
        transcript: raw transcript text
        title: video title for context
        mode: 'solo' or 'dual'
        target_lang: target language code or 'auto'
    Returns:
        script text or None on failure
    """
    client = _get_llm_client()
    if not client:
        print("[WARN] No NVIDIA API key — cannot generate podcast script", file=sys.stderr)
        return None

    # Language instruction
    if target_lang == "auto":
        lang_instruction = "跟隨逐字稿的語言"
    elif target_lang == "zh":
        lang_instruction = "使用繁體中文"
    elif target_lang == "en":
        lang_instruction = "Use English"
    else:
        lang_instruction = f"使用 {target_lang}"

    template = _DUAL_PROMPT if mode == "dual" else _SOLO_PROMPT
    prompt = template.format(lang_instruction=lang_instruction) + transcript

    print(f"[INFO] Generating {mode} podcast script via LLM ({NVIDIA_MODEL})...", file=sys.stderr)
    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": "你是專業的播客腳本編寫者，擅長將逐字稿轉化為自然流暢的口播腳本。嚴格禁止重複相同或相似的段落，每個論點只講一次。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.7,
            frequency_penalty=0.3,
            presence_penalty=0.2,
        )
        result = response.choices[0].message.content
        if result:
            return _dedup_script(result.strip())
        print("[WARN] LLM returned empty script", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[WARN] LLM script generation failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# TTS via Edge TTS
# ---------------------------------------------------------------------------
async def _tts_one(text: str, voice: str, out_path: str):
    """Generate TTS audio for a single text segment."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def _tts_segment(text: str, voice: str, out_path: str):
    """Synchronous wrapper for TTS generation."""
    asyncio.run(_tts_one(text, voice, out_path))


def _parse_dual_script(script: str) -> list[tuple[str, str]]:
    """Parse dual-host script into list of (role, text) tuples.

    Input format:
        A: 一些文字
        B: 回應文字
        A: 繼續提問

    Returns:
        [("A", "一些文字"), ("B", "回應文字"), ...]
    """
    import re
    segments = []
    current_role = None
    current_lines = []

    for line in script.split("\n"):
        line = line.strip()
        if not line:
            if current_role and current_lines:
                segments.append((current_role, " ".join(current_lines)))
                current_lines = []
            continue

        # Match "A:" or "B:" at start of line
        m = re.match(r'^([AB])[:：]\s*(.*)', line)
        if m:
            if current_role and current_lines:
                segments.append((current_role, " ".join(current_lines)))
            current_role = m.group(1)
            current_lines = [m.group(2)] if m.group(2) else []
        else:
            # Continuation of previous speaker
            if current_role:
                current_lines.append(line)
            else:
                # No role marker yet — treat as A (host intro)
                current_role = "A"
                current_lines = [line]

    if current_role and current_lines:
        segments.append((current_role, " ".join(current_lines)))

    return segments


def _parse_solo_script(script: str) -> list[str]:
    """Parse solo script into paragraphs (non-empty lines)."""
    paragraphs = []
    current = []
    for line in script.split("\n"):
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


# ---------------------------------------------------------------------------
# Audio Merging
# ---------------------------------------------------------------------------
def _merge_audio(segment_files: list[str], output_path: str):
    """Merge audio segments into a single MP3 using ffmpeg concat demuxer.

    Much faster than pydub for large numbers of segments.
    """
    import subprocess

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_list = f.name
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    try:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-acodec", "libmp3lame", "-b:a", "192k", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[WARN] ffmpeg concat failed: {result.stderr[-200:]}", file=sys.stderr)
            # Fallback to pydub
            _merge_audio_pydub(segment_files, output_path)
        else:
            print(f"[INFO] Merged {len(segment_files)} segments → {output_path}", file=sys.stderr)
    finally:
        os.unlink(concat_list)


def _merge_audio_pydub(segment_files: list[str], output_path: str):
    """Fallback: merge using pydub (slower but more compatible)."""
    from pydub import AudioSegment
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=600)
    for i, f in enumerate(segment_files):
        seg = AudioSegment.from_file(f)
        if i > 0:
            combined += silence
        combined += seg
    combined.export(output_path, format="mp3", bitrate="192k")
    print(f"[INFO] Merged {len(segment_files)} segments (pydub) → {output_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def produce_podcast(
    transcript: str,
    title: str,
    url: str,
    lang: str = "auto",
    mode: str = "dual",
    voice_a: str = DEFAULT_VOICE_A,
    voice_b: str = DEFAULT_VOICE_B,
    out_dir: str | None = None,
    video_id: str = "",
) -> str | None:
    """Produce a podcast from a transcript.

    Args:
        transcript: raw transcript text
        title: video title
        url: video URL
        lang: target language ('auto', 'zh', 'en', etc.)
        mode: 'solo' or 'dual'
        voice_a: voice for host / solo speaker
        voice_b: voice for co-host (dual mode only)
        out_dir: output directory (default: OBSIDIAN_BASE/口播/{title} [{video_id}]/)
        video_id: YouTube video ID for unique directory naming

    Returns:
        Path to the generated MP3, or None on failure.
    """
    # Step 0: Translate title for directory naming when target lang differs
    dir_title = title
    if lang and lang not in ("auto", "en") and title:
        translated = _translate_title(title, lang)
        if translated:
            dir_title = translated

    # Resolve output directory
    if not out_dir:
        obsidian_base = "/opt/data/obsidian-vault"
        safe_title = _sanitize(dir_title)
        if video_id:
            folder_name = f"{safe_title} [{video_id}]"
        else:
            folder_name = safe_title
        out_dir = os.path.join(obsidian_base, PODCAST_SUBDIR, folder_name)
    os.makedirs(out_dir, exist_ok=True)

    # Step 1: Generate script
    script = _generate_script(transcript, title, mode, lang)
    if not script:
        print("[ERROR] Failed to generate podcast script", file=sys.stderr)
        return None

    # Save script for reference (as Markdown note)
    script_path = os.path.join(out_dir, "script.md")
    script_md = f"""---
created: {__import__('datetime').date.today().isoformat()}
source: {title}
type: podcast-script
mode: {mode}
language: {lang}
tags: [podcast, 口播]
---

# {title} — 口播腳本

> 模式: {"雙主持人" if mode == "dual" else "單人口播"} | 語言: {lang}

{script}
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_md)
    os.chmod(script_path, 0o777)
    print(f"[OK] Script saved: {script_path}", file=sys.stderr)

    # Step 2: Generate TTS segments
    with tempfile.TemporaryDirectory(prefix="podcast_tts_") as tmpdir:
        segment_files = []

        if mode == "solo":
            paragraphs = _parse_solo_script(script)
            print(f"[INFO] Generating {len(paragraphs)} TTS segments (solo, voice={voice_a})...", file=sys.stderr)
            for i, para in enumerate(paragraphs):
                if not para.strip():
                    continue
                seg_path = os.path.join(tmpdir, f"seg_{i:04d}.mp3")
                try:
                    _tts_segment(para, voice_a, seg_path)
                    segment_files.append(seg_path)
                    if (i + 1) % 10 == 0:
                        print(f"  [{i+1}/{len(paragraphs)}] done", file=sys.stderr)
                except Exception as e:
                    print(f"  [WARN] Segment {i} failed: {e}", file=sys.stderr)

        elif mode == "dual":
            parsed = _parse_dual_script(script)
            print(f"[INFO] Generating {len(parsed)} TTS segments (dual)...", file=sys.stderr)
            for i, (role, text) in enumerate(parsed):
                if not text.strip():
                    continue
                voice = voice_a if role == "A" else voice_b
                seg_path = os.path.join(tmpdir, f"seg_{i:04d}.mp3")
                try:
                    _tts_segment(text, voice, seg_path)
                    segment_files.append(seg_path)
                    if (i + 1) % 10 == 0:
                        print(f"  [{i+1}/{len(parsed)}] done", file=sys.stderr)
                except Exception as e:
                    print(f"  [WARN] Segment {i} ({role}) failed: {e}", file=sys.stderr)

        if not segment_files:
            print("[ERROR] No TTS segments generated", file=sys.stderr)
            return None

        # Step 3: Merge
        safe_title = _sanitize(dir_title)
        mp3_path = os.path.join(out_dir, f"{safe_title}_podcast.mp3")
        _merge_audio(segment_files, mp3_path)
        os.chmod(mp3_path, 0o777)
        os.chmod(out_dir, 0o777)

        print(f"[OK] Podcast saved: {mp3_path}", file=sys.stderr)
    return mp3_path


def _sanitize(s: str) -> str:
    """Sanitize string for use as filename."""
    import re
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s[:120]
