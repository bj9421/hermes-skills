---
name: youtube-note-pipeline
description: "Full pipeline: YouTube video → subtitle/transcript → clean Markdown → Obsidian vault export. Three-stage auto-fallback: youtube-transcript-api (cleanest) → yt-dlp VTT → Whisper transcription. Optional --organize for LLM structuring, --podcast for solo/dual-host TTS audio, --ppt for PowerPoint slides, --visual for NotebookLM-style summary image. For note-taking, research, or creating durable knowledge from any YouTube video."
platforms: [linux]
compatibility:
  - yt-dlp
  - faster-whisper
  - ffmpeg
  - youtube-transcript-api
  - openai (for --organize, --podcast, --ppt, --visual via NVIDIA API)
  - edge-tts (for --podcast)
  - pydub (for --podcast audio merging)
  - python-pptx (for --ppt)
  - Pillow (for --visual)
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

# Podcast + PPT + Visual summary (all outputs in 口播/{title} [id]/)
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual --ppt --visual --lang zh
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

**Output:** `口播/{dir_title} [{video_id}]/{dir_title}_podcast.mp3` + `script.md` (Markdown with frontmatter, tags: `[podcast, 口播]`) in Obsidian vault. Directory name and MP3 filename use the **translated title** (`dir_title`) when `--lang` differs from source (e.g. English video → Chinese dir name). Directory includes video ID for uniqueness.

**Modes:**
- `solo` — Single narrator, natural monologue
- `dual` — Host A (asks) + Commentator B (answers), alternating dialogue

**Default voices:**
- A (host): `zh-TW-HsiaoChenNeural` (female)
- B (commentator): `zh-TW-YunJheNeural` (male)

**Language:** `--lang auto` (follow source) or `--lang zh` / `--lang en` (force target language).

**Dependencies:** `edge-tts`, `pydub`, `audioop-lts` (Python 3.13+).

**Script generation:** NVIDIA API LLM (`deepseek-ai/deepseek-v4-flash` default, env var `NVIDIA_ORGANIZE_MODEL` overrides), different prompt template. Includes `frequency_penalty=0.3`, `presence_penalty=0.2`, system prompt anti-repetition instruction, and `_dedup_script()` post-processing to catch degeneration loops.

**Output auto-chmod:** `script.md` and MP3 are `chmod 777` after creation for Syncthing sync.

### Podcast Pitfalls

1. **Edge TTS voice names changed**: Newer `edge-tts` versions require `Neural` suffix (e.g., `zh-TW-HsiaoChenNeural`, not `zh-TW-TingTing`). Check available voices with `edge_tts.list_voices()`.
2. **pydub is too slow for 100+ segments**: Each `AudioSegment.from_file()` re-decodes. Use ffmpeg concat demuxer instead (`ffmpeg -f concat -safe 0 -i list.txt -acodec libmp3lame out.mp3`). pydub kept as fallback only.
3. **ffmpeg concat requires same codec params**: All edge-tts MP3 segments share the same format by default, but if segments come from different sources, use `-acodec libmp3lame` (re-encode) instead of `-c copy`.
4. **Large videos produce 200+ segments**: LLM script generation is the fast part; TTS + merge dominates. 200 segments ≈ 3-4 min TTS + 10s merge (ffmpeg) vs 5+ min (pydub).
5. **LLM degeneration (repetition loops)**: Small models (especially `meta/llama-3.1-8b-instruct`) produce infinite repetition on Chinese text — same sentence repeated 100+ times, inflating script from ~4KB to 28KB+ and MP3 from ~5MB to 34MB+. Mitigations already built in: `frequency_penalty=0.3`, `presence_penalty=0.2`, system prompt anti-repetition instruction, `_dedup_script()` post-processing that truncates at 3rd repeat. If this still happens, the model is too weak — upgrade via `NVIDIA_ORGANIZE_MODEL` env var. Tested: `deepseek-ai/deepseek-v4-flash` (284B MoE) handles Chinese well with no degeneration.
6. **`uv run yt-dlp` fails in Docker**: The `_get_video_title()` function uses `shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"` directly instead of `uv run yt-dlp`, because `uv` can't discover Python installations in the Docker container (permission denied on `/root/.local/share/uv/python`). If title extraction fails, check that yt-dlp is installed in the venv.
7. **NVIDIA API 503 ResourceExhausted**: When running `--podcast dual --ppt --visual` together, all three modules call the same NVIDIA API endpoint sequentially. If the worker pool is already saturated (e.g. from a previous heavy run), later calls get `503: Worker local total request limit reached (48/48)`. The podcast module handles this gracefully (falls back to default data), but PPT/visual may produce sparse output. **Mitigation:** Run `--podcast` first, wait a few minutes, then add `--ppt --visual` in a second pass if 503 occurs.

## PPT Mode (`--ppt`) — PowerPoint Presentation

> ✅ **Implemented** — `--ppt` flag generates a professional PowerPoint from the transcript.

```bash
# PPT only
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --ppt

# PPT + podcast + visual (all outputs in same directory)
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual --ppt --visual --lang zh
```

**Output:** `{dir_title}.pptx` (dark-themed, 16:9 widescreen, 8 slides: title + key points + summary).

**How it works:**
1. LLM extracts structured key points from transcript (4-6 topics, 2-3 bullets each, stats, summary)
2. `ppt_gen.py` renders dark navy slides with accent colors, number badges, and bullet lists
3. Uses `deepseek-ai/deepseek-v4-flash` for extraction (same model as podcast/organize)

**Dependencies:** `python-pptx` (install: `uv pip install python-pptx`)

## Visual Summary Mode (`--visual`) — NotebookLM-style Image

> ✅ **Implemented** — `--visual` flag generates a visual overview image.

```bash
# Visual summary only
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --visual --lang zh
```

**Output:** `{dir_title}_summary.png` (1200×675, dark theme, card-based layout with icons, topics, and stats).

**How it works:**
1. LLM extracts visual data (title, tagline, topics with icons, key stats)
2. `visual_gen.py` renders a Pillow image with rounded-rect cards, CJK font support, warm accent colors
3. Uses `deepseek-ai/deepseek-v4-flash` for extraction

**Dependencies:** `Pillow` (already installed)

### Visual Pitfalls

1. **CJK font quality matters — user rejects ugly fonts**: Font priority in `visual_gen.py` `_load_font()`:
   1. **芫荽 iansui** (`/opt/data/fonts/Iansui-Regular.ttf`) — warm kai-style, Taiwan traditional Chinese, user's current preference
   2. **Noto Sans SC** (`/opt/data/fonts/NotoSansSC-Bold.ttf`) — clean modern sans-serif
   3. **WenQuanYi Zen Hei** (`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`) — functional but ugly
   4. **DejaVu** — last resort, no CJK support

   **Installing fonts in Docker** (no root for apt): Download from GitHub releases using Python urllib (NOT curl — curl gets blocked/redirected by GitHub and produces tiny corrupt files):
   ```python
   import urllib.request
   req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/octet-stream'})
   data = urllib.request.urlopen(req, timeout=30).read()
   with open('font.ttf', 'wb') as f: f.write(data)
   ```
   For iansui: get release URL via `https://api.github.com/repos/ButTaiwan/iansui/releases/latest`, extract `assets[].browser_download_url`, then download with urllib. Only one TTF in the zip (`Iansui-Regular.ttf`).

2. **NVIDIA API 503 ResourceExhausted — worker-level, transient**: The limit is `Worker local total request limit reached (N/48)` — **worker-level, NOT per-model**. ALL models share the same 48-request worker pool. Error is transient: recovers in 2-10 minutes without intervention. When running `--podcast dual --ppt --visual` together, all three modules hit the same endpoint sequentially, so the third call often hits the limit. **Mitigation:** (a) Wait 5 min and retry just the failed step, (b) Run podcast first, then PPT+visual in a second pass. The visual module falls back to sparse default data on 503 (title + "口播 / 請參閱腳本"), so re-running it later overwrites with full content.

## Title Translation

When `--lang` differs from the source language (e.g. `--lang zh` on an English video):
- **`dir_title`** = LLM-translated title (used for directory name + MP3/PPT/visual filenames)
- **`title`** = original English title (used in frontmatter `source` field + transcript content)

Translation uses a fast LLM call (`max_tokens=100`, `temperature=0.3`) via `_translate_title()` in `podcast.py`. Falls back to original title on failure.

### Title Translation Pitfall

**Must pass `dir_title` (not `title`) to all output modules**: `generate_ppt()`, `generate_visual()`, and `produce_podcast()` all receive `dir_title` as their title parameter. If you accidentally pass the English `title`, the output filenames will be English inside a Chinese directory name — inconsistent and confusing. The pipeline computes `dir_title` early (via `_translate_title()`) and threads it through all module calls.

## Final chmod Sweep

All outputs in the podcast directory get `chmod -R 777` after generation, ensuring Syncthing compatibility across devices (Docker hermes user vs phone uid 1000).

## See Also

- `references/pipeline-architecture.md` — detailed pipeline architecture, `--obsidian` subfolder usage, VTT garbled-text caveats, and API migration notes.
- `references/organize-architecture.md` — LLM post-processing design: NVIDIA API integration, prompt template, chunking strategy, error handling.
- `references/podcast-architecture.md` — podcast mode flow, prompt templates, Edge TTS voice names, audio merge strategy, Python 3.13 compatibility.
- `references/translation-and-troubleshooting.md` — bilingual translation format, language fallback chain, common yt-dlp fixes, Whisper on RPi tips.
