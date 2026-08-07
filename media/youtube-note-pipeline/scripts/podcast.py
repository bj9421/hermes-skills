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
import re
import sys
import time
import asyncio
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_ORGANIZE_MODEL", "deepseek-ai/deepseek-v4-flash")

DEFAULT_VOICE_A = "zh-TW-HsiaoChenNeural"   # 曉萱（女聲主持人）
DEFAULT_VOICE_B = "zh-TW-YunJheNeural"     # 永康（男聲評論員）
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

角色：
- 你是主持人「曉萱」（女聲），用第一人稱與聽眾聊天

要求：
1. 用第一人稱口語化講述，像在跟聽眾聊天
2. 開頭自然自我介紹（「大家好，我是曉萱」），結尾要有總結
3. 保留原文的核心觀點和重要細節
4. 加入自然的過渡語句（「接下來我們來看...」「說到這個...」「有趣的是...」）
5. 去除贅字和口語重複，但保留自然的口語感
6. 語言：{lang_instruction}
7. 不要加逐字稿中的時間標記 [MM:SS]
8. 長度：自然完整，不硬性截斷
9. 🔴 必須使用完整的標點符號（句號。逗號，頓號、問號？感嘆號！）
10. 🔴 自然分段，每段 3-5 句，段之間空一行
11. 🔴 如果輸入是結構化 markdown（標題、條列），請轉換成流暢的口播腳本，不要直接複製原始格式
12. 🔴 全程以「我」自述，不要提到「主持人」「曉萱」以外的第三人稱稱呼自己
13. 🔴 完整涵蓋輸入內容的所有章節：共通主題、各來源獨特觀點、差異與衝突、整體結論與行動建議，任何一章都不要遺漏
14. 🔴 保留重要數據、劑量、專有名詞與細節，不要過度濃縮；目標長度至少 4500 字以上（約 20-25 分鐘口播）

直接輸出腳本文字。

逐字稿：
"""


_DUAL_PROMPT = """你是一個專業的播客腳本編寫者。請將以下逐字稿轉換為雙主持人對談腳本。

角色（兩位主持人有名字，請用名字互相稱呼）：
- 曉萱（女聲主持人）：引導話題、提問、總結，開場和收尾由曉萱負責
- 永康（男聲評論員）：補充觀點、舉例、深入分析

格式規則：
- 每行以角色標記開頭：「A:」代表曉萱，「B:」代表永康（A: / B: 是解析用標記，不會被唸出來）
- 曉萱和永康交替發言，不要連續同一個角色說超過 3 次
- 🔴 對話內容中提及對方時，一律用名字稱呼（「曉萱，你怎麼看？」「永康補充說…」），絕對禁止使用「A」「B」「主持人」「評論員」等稱呼
- 對話要自然流暢，像真實的播客節目，像兩個熟識的朋友在聊天
- 永康的回應要有深度，不是簡單附和

要求：
1. 保留原文的核心觀點和重要細節
2. 去除贅字，但保留自然的口語感
3. 語言：{lang_instruction}
4. 不要加逐字稿中的時間標記 [MM:SS]
5. 長度：自然完整，不硬性截斷
6. 🔴 必須使用完整的標點符號（句號。逗號，頓號、問號？感嘆號！）
7. 🔴 自然分段，每段 3-5 句，段之間空一行
8. 🔴 如果輸入是結構化 markdown（標題、條列），請轉換成流暢的對話腳本，不要直接複製原始格式
9. 🔴 完整涵蓋輸入內容的所有章節：共通主題、各來源獨特觀點、差異與衝突、整體結論與行動建議，任何一章都不要遺漏
10. 🔴 保留重要數據、劑量、專有名詞與細節，不要過度濃縮；目標長度至少 4500 字以上（約 20-25 分鐘口播）

直接輸出腳本。

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

# Rate limiter — minimum 2s between API calls (40 RPM free tier = 1.5s baseline, 2s for safety margin)
import time as _rate_time
_last_api_call = 0.0
_API_INTERVAL = 2.0

def _rate_limit():
    global _last_api_call
    elapsed = _rate_time.time() - _last_api_call
    if elapsed < _API_INTERVAL:
        _rate_time.sleep(_API_INTERVAL - elapsed)
    _last_api_call = _rate_time.time()


def _translate_title(title: str, target_lang: str) -> str | None:
    """Translate a video title to the target language via LLM (with retry + fallback)."""
    import time
    
    # ⚠️ 2026-08-07 修正：改用 call_llm（Zen→AGNES→Groq fallback 鏈），
    # 原本只用 call_zen — Zen 429 時標題翻譯直接失敗（同 _generate_script 問題）。
    try:
        from notehub.core.llm import call_llm
    except ImportError:
        call_llm = None
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    if call_llm:
        result = call_llm(
            [{"role": "system", "content": "你是翻譯專家。只翻譯標題，不加任何解釋、引號或額外文字。"},
             {"role": "user", "content": f"將以下標題翻譯成{lang_name}，直接輸出翻譯結果：\n\n{title}"}],
            max_tokens=0,
            temperature=0.3)
        if result:
            return result.strip().strip('"').strip("'").strip("《》")
        # ⚠️ 2026-07-31 使用者指示：LLM 一律不用 NVIDIA（NVIDIA 僅供 Whisper）
        print("[WARN] Title translate failed (all LLM providers) — 依使用者指示不 fallback NVIDIA，回傳 None", file=sys.stderr)
        return None
    return None


# ---------------------------------------------------------------------------
# Script Generation
# ---------------------------------------------------------------------------
def _generate_script(transcript: str, title: str, mode: str, target_lang: str) -> str | None:
    """Generate podcast script via LLM (Zen→AGNES→Groq fallback chain).

    Args:
        transcript: raw transcript text
        title: video title for context
        mode: 'solo' or 'dual'
        target_lang: target language code or 'auto'
    Returns:
        script text or None on failure
    """
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

    # ⚠️ 2026-08-07 修正：改用 call_llm（Zen→AGNES→Groq fallback 鏈），
    # 原本只用 call_zen — Zen 429 就直接降級成 raw transcript（無分段無標點）。
    # max_tokens=0（不帶）— deepseek-v4-flash 是 reasoning 模型，設 max_tokens
    # 會被思考過程吃光 → content 空（同 ppt_gen.py / visual_gen.py 做法）。
    try:
        from notehub.core.llm import call_llm
    except ImportError:
        call_llm = None
    if call_llm:
        print(f"[INFO] Generating {mode} podcast script via Zen→AGNES→Groq (call_llm)...", file=sys.stderr)
        result = call_llm(
            [{"role": "system", "content": "你是專業的播客腳本編寫者，擅長將逐字稿轉化為自然流暢的口播腳本。嚴格禁止重複相同或相似的段落，每個論點只講一次。"},
             {"role": "user", "content": prompt}],
            max_tokens=0,
            temperature=0.7)
        if result:
            return _dedup_script(result.strip())
        # ⚠️ 2026-07-31 使用者指示：LLM 一律不用 NVIDIA（NVIDIA 僅供 Whisper）
        print("[WARN] Script generation failed (all LLM providers) — 依使用者指示不 fallback NVIDIA，回傳 None", file=sys.stderr)
        return None
    return None

# ---------------------------------------------------------------------------
# TTS via Edge TTS
# ---------------------------------------------------------------------------
_tts_last_call = 0.0  # global timestamp for rate limiting


async def _tts_one(text: str, voice: str, out_path: str, max_retries: int = 3):
    """Generate TTS audio for a single text segment with retry."""
    global _tts_last_call
    import edge_tts

    for attempt in range(max_retries):
        # Rate limit: at least 2 seconds between calls
        elapsed = time.time() - _tts_last_call
        if elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)

        try:
            _tts_last_call = time.time()
            communicate = edge_tts.Communicate(text, voice, rate="+5%")
            await communicate.save(out_path)
            return  # success
        except Exception as e:
            wait = 3 * (2 ** attempt)  # 3s, 6s, 12s
            print(f"  [WARN] TTS attempt {attempt+1}/{max_retries} failed: {e} — retry in {wait}s",
                  file=sys.stderr)
            await asyncio.sleep(wait)

    raise RuntimeError(f"TTS failed after {max_retries} retries")


def _split_long_text(text: str, max_chars: int = 200) -> list[str]:
    """Split long text into shorter chunks at sentence boundaries."""
    import re
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    # Split at sentence endings
    for sentence in re.split(r'([。！？.!?])', text):
        if not sentence:
            continue
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current += sentence
    if current.strip():
        chunks.append(current.strip())

    # 🔴 2026-08-07 FIX: 過濾掉過短的 chunk（只含標點符號的無效片段）
    #   原因：re.split 在長文本切割時，當 current 接近 max_chars 時，
    #   剩下的 sentence 可能只有「。」或「.」等單一字元，edge_tts 會報錯
    #   "No audio was received"。過濾掉這些無效 chunk 避免 TTS 失敗。
    chunks = [c for c in chunks if len(c.strip()) >= 5]

    return chunks if chunks else [text]


def _tts_segment(text: str, voice: str, out_path: str):
    """Synchronous wrapper for TTS generation with retry and long-text splitting."""
    chunks = _split_long_text(text)
    if len(chunks) == 1:
        asyncio.run(_tts_one(chunks[0], voice, out_path))
    else:
        # Generate each chunk separately, then merge
        import tempfile
        from pydub import AudioSegment
        parts = []
        with tempfile.TemporaryDirectory(prefix="tts_split_") as tmpdir:
            for i, chunk in enumerate(chunks):
                part_path = os.path.join(tmpdir, f"part_{i}.mp3")
                asyncio.run(_tts_one(chunk, voice, part_path))
                parts.append(AudioSegment.from_mp3(part_path))
            combined = AudioSegment.empty()
            for p in parts:
                combined += p
            combined.export(out_path, format="mp3")


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

        # Match "A:" or "B:" at start of line (with or without colon)
        m = re.match(r'^([AB])[:：]?\s*(.*)', line)
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
    """Parse solo script into paragraphs (non-empty lines).

    🔴 2026-08-07 FIX: 過濾掉 markdown 分隔線（---/***）與過短段落（<5 字）。
    原因：LLM 偶爾在腳本中間插入「---」分隔線，被當成 TTS 段落後
    edge_tts 對過短輸入回傳 "No audio was received"（同 _split_long_text FIX）。
    """
    paragraphs = []
    current = []
    for line in script.split("\n"):
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            # 跳過 markdown 分隔線（---、***、___）
            if re.match(r'^[-*_]{3,}$', line):
                continue
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    # 🔴 2026-08-07 FIX: 過濾 <5 字的無效段落（edge_tts 會失敗）
    paragraphs = [p for p in paragraphs if len(p.strip()) >= 5]
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
    # ⚠️ 2026-07-31 使用者指示：口播腳本用免費模型（OpenCode Zen），LLM 翻譯也走 Zen
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
    # ⚠️ 2026-07-31 使用者指示：口播腳本用免費模型（OpenCode Zen）生成
    script = _generate_script(transcript, title, mode, lang)
    if not script:
        # Zen 與 NVIDIA 都失敗 → fallback：直接唸原文（TTS 本地產出保證）
        print("[WARN] Script generation failed — using raw transcript for TTS", file=sys.stderr)
        script = transcript

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

> 模式: {"雙主持人（曉萱＋永康）" if mode == "dual" else "單人口播（曉萱）"} | 語言: {lang}

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
