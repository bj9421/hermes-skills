---
name: youtube-note-pipeline
description: "Full pipeline: YouTube video → subtitle/transcript → clean Markdown → Obsidian vault export. Three-stage auto-fallback: youtube-transcript-api (cleanest) → yt-dlp VTT → Whisper transcription. Optional --organize for LLM structuring, --podcast for solo/dual-host TTS audio. For note-taking, research, or creating durable knowledge from any YouTube video."
platforms: [linux]
compatibility:
  - yt-dlp
  - faster-whisper
  - ffmpeg
  - youtube-transcript-api
  - openai (for --organize via NVIDIA API)
  - edge-tts (for --podcast)
  - pydub (for --podcast audio merging)
related_skills: [youtube-content, obsidian]
---

# YouTube Note Pipeline

## When to use

Use when the user shares a YouTube URL and wants to save the content as a permanent note — for translation, note-taking, or research. Covers the complete pipeline: extract → convert → save to Obsidian vault.

This skill complements `youtube-content` (transcript → summary/thread/blog) by adding automated transcription, multi-pipeline fallback, and Obsidian persistence.

## Setup (all done — ready to use)

```bash
# Dependencies already installed:
# yt-dlp, youtube-transcript-api, faster-whisper, ffmpeg, markitdown, openai
```

> `openai` SDK required for `--organize` (NVIDIA API). Install: `uv pip install openai`

## Pipeline Overview (3-stage auto-fallback)

```
YouTube URL
  |
  +-- 1. youtube-transcript-api (cleanest) ----> timestamped Markdown
  |      (preferred: zh-TW → zh-Hans → en)
  |
  +-- 2. yt-dlp VTT subtitles (fallback) -----> cleaned text
  |      (auto-generated captions)
  |
  +-- 3. yt-dlp + Whisper (last resort) -------> transcribed audio
  |
  v
  Markdown with [MM:SS] timestamps + YAML frontmatter
  |
  v
  /opt/data/obsidian-vault/{subfolder}/<title>.md
  (default: YouTube/; customize with --obsidian "path/to/subfolder")

**Vault root:** `/opt/data/obsidian-vault/` — no intermediate `Holographic/` layer.
```

**Pipeline priority:** `transcript-api` > `VTT` > `Whisper`. First to produce output wins.

**Language priority:** zh-TW → zh-Hant → zh-Hans → en → (auto-detect)

**Timestamps:** always preserved as `[MM:SS]` / `[HH:MM:SS]` markers. Do not strip, reformat, or remove them unless the user explicitly says otherwise.

## Helper script: `SKILL_DIR/scripts/yt2md_pipeline.py`

```bash
# Auto-detect (recommended) — tries transcript-api → VTT → Whisper
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL"

# One-step to Obsidian vault (default: YouTube/ subfolder)
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --obsidian

# Save to custom Obsidian subfolder
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --obsidian "我的筆記/yt2md"

# Force Whisper transcription
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --whisper --model tiny

# Save to specific file
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" -o ~/note.md

# Organize mode — LLM-powered structured notes (two files: organized + raw)
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --organize --obsidian "我的筆記/yt2md"
```

### Output format (Markdown with frontmatter)

```markdown
---
created: 2026-07-07
source: https://youtube.com/watch?v=...
title: Video Title
language: en
pipeline: transcript-api
tags: [youtube, transcript]
---

# Video Title

> https://youtube.com/watch?v=...

[0:18] First line of transcript
[0:22] Second line with timestamp
...
```

## Whisper Model Selection (RPi 4 CPU)

| Model  | RAM    | Speed   | Use case                    |
|--------|--------|---------|-----------------------------|
| tiny   | 200 MB | Fastest | Quick test / short clips    |
| small  | 1 GB   | Fast    | Default                     |
| medium | 3 GB   | Medium  | Long videos                 |
| large  | 6 GB   | Slow    | Max accuracy (tight on RPi) |

Default: `--model small`. For long sessions or low RAM: `--model tiny`.

## Translation

When the user wants Chinese content from any language video:

1. **Fetch** transcript with timestamps via `--obsidian`
2. **Translate** each timestamp block, preserving `[MM:SS]` markers
3. **Format** as bilingual per block:
   - Source line (original)
   - Chinese translation line
4. **Chunk** if transcript >50K chars: split into ~40K blocks with 2K overlap, translate each, merge

## Organize Mode (`--organize`) — Post-Processing via LLM

> ✅ **Implemented** — `--organize` flag uses NVIDIA API LLM to turn raw transcripts into structured notes.

Adds a post-processing step that uses an LLM to turn raw transcripts into structured notes.

```bash
# Organize mode — produces two files
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --organize --obsidian "我的筆記/yt2md"

# Organize without raw backup
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --organize --no-raw
```

**Output:**
- `<title>.md` — organized note (summary + sections + condensed text)
- `<title>_raw.md` — original raw transcript (backup)

**LLM:** NVIDIA API (`integrate.api.nvidia.com/v1`), env var `NVIDIA_API_KEY`.
Without API key → falls back to raw transcript only (no error).

**Key design decisions:**
- Always saves raw transcript as backup (two-file output)
- Chunking for transcripts >25K chars (25K chunks, 1K overlap, configurable via `LLM_MAX_CHARS`)
- Language-aware: prompt instructs LLM to match source language
- Error-tolerant: API failure → saves raw transcript anyway

See `references/organize-architecture.md` for full design (prompt template, chunking strategy, error handling).

## Error Handling

- **No subs and no audio**: video is private/deleted — tell the user
- **Whisper OOM**: retry with `--model tiny` or segment audio into shorter clips
- **ffmpeg missing**: `sudo apt install ffmpeg`
- **yt-dlp sign-in wall**: try `--extractor-args "youtube:skip=webpage"` or cookie import
- **Long transcript**: chunk before translation; 2K overlap between chunks
- **Dependency missing**: `uv pip install <package>` and retry

## Podcast Mode (`--podcast`) — TTS Audio Generation

> ✅ **Implemented** — `--podcast` flag generates solo or dual-host podcast audio from transcripts.

```bash
# Dual-host podcast (default)
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual

# Solo podcast
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast solo

# Chinese podcast from English video
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual --lang zh

# Custom voices
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual --voice-a zh-TW-HsiaoYuNeural --voice-b zh-TW-YunJheNeural
```

**Output:** `口播/{title}/{title}_podcast.mp3` + `script.txt` in Obsidian vault.

**Modes:**
- `solo` — Single narrator, natural monologue
- `dual` — Host A (asks) + Commentator B (answers), alternating dialogue

**Default voices:**
- A (host): `zh-TW-HsiaoChenNeural` (female)
- B (commentator): `zh-TW-YunJheNeural` (male)

**Language:** `--lang auto` (follow source) or `--lang zh` / `--lang en` (force target language).

**Dependencies:** `edge-tts`, `pydub`, `audioop-lts` (Python 3.13+).

**Script generation:** NVIDIA API LLM (same as `--organize`), different prompt template.

## See Also

- `references/pipeline-architecture.md` — detailed pipeline architecture, `--obsidian` subfolder usage, VTT garbled-text caveats, and API migration notes.
- `references/organize-architecture.md` — LLM post-processing design: NVIDIA API integration, prompt template, chunking strategy, error handling.
- `references/translation-and-troubleshooting.md` — bilingual translation format, language fallback chain, common yt-dlp fixes, Whisper on RPi tips.
