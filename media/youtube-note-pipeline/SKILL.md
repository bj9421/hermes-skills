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
  - Noto Emoji monochrome font (for --visual emoji icons, installed at /opt/data/fonts/NotoEmoji-Regular.ttf)
  - opencc (for auto SC→TC conversion on --lang zh)
related_skills: [youtube-content, obsidian]
---

# YouTube Note Pipeline

## When to use

Use when the user shares a YouTube URL and wants to save the content as a permanent note — for translation, note-taking, or research. Covers the complete pipeline: extract → convert → save to Obsidian vault.

This skill complements `youtube-content` (transcript → summary/thread/blog) by adding automated transcription, multi-pipeline fallback, and Obsidian persistence.

## NoteHub (New Multi-Source Entry Point)

> ✅ **As of 2026-07-29** — NoteHub supports **YouTube, Instagram, URLs, PDFs, and text files**. The `InstagramExtractor` auto-downloads audio + transcribes via Groq Whisper. All outputs auto-convert to Traditional Chinese when `--lang zh`. The old `yt2md_pipeline.py` still works for backward compatibility.

```bash
# New entry point (recommended)
python -m notehub "YouTube URL" --podcast dual --ppt --visual --lang zh
python -m notehub "https://example.com" --organize --visual
python -m notehub "./document.pdf" --organize --ppt
python -m notehub "./notes.txt" --podcast solo

# Search & manage
python -m notehub --search "AI"
python -m notehub --list
python -m notehub --stats
```

**Architecture:** `notehub/extractors/` (Strategy Pattern: youtube → instagram → url → pdf → text) → `notehub/core/pipeline.py` (incl. `_convert_to_traditional()` post-processing) → `notehub/db/models.py` (SQLite FTS5) → `notehub/generators/` (podcast/ppt/visual) → `notehub/mcp/server.py` (9 MCP tools for AI agents).

**New dependencies:** `pymupdf4llm` (PDF), `mcp` (MCP Server SDK), `opencc` (SC→TC conversion).

See `references/notehub-architecture.md` for full architecture details.

## Setup (all done — ready to use)

```bash
# Dependencies already installed:
# yt-dlp, youtube-transcript-api, faster-whisper, ffmpeg, markitdown, openai
# pymupdf4llm, mcp (for notehub)
```

> `openai` SDK required for `--organize` (NVIDIA API). Install: `uv pip install openai`

## Pipeline Overview

### NoteHub (3 extractor types)

```
YouTube URL
  │
  └─ YouTubeExtractor (2 strategies: transcript-api → yt-dlp VTT)
       │
       └─ Markdown + frontmatter → 口播/ (or notes/)

Instagram Reel URL
  │
  └─ InstagramExtractor (yt-dlp audio → Groq Whisper)
       │
       └─ Markdown + frontmatter → 口播/ (or notes/)

URL / PDF / text
  │
  └─ URLExtractor / PDFExtractor / TextExtractor
       │
       └─ Markdown + frontmatter → notes/
```

### Legacy yt2md_pipeline.py (3-stage fallback; YouTube only)

```
YouTube URL
  │
  +-- 1. youtube-transcript-api (cleanest)
  +-- 2. yt-dlp VTT subtitles (fallback)
  +-- 3. yt-dlp + Whisper (last resort)
  │
  v
  Markdown with [MM:SS] timestamps + YAML frontmatter
  │
  v
  /opt/data/obsidian-vault/{subfolder}/<title>.md
```

**Pipeline priority:** `transcript-api` > `VTT` > `Whisper/Groq`. First to produce output wins.

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
- **No subs but audio available**: route to Groq Whisper workflow (pitfall #13) instead of giving up
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

**Script generation:** NVIDIA API LLM (`deepseek-ai/deepseek-v4-flash` default, env var `NVIDIA_ORGANIZE_MODEL` overrides), different prompt template. Includes `frequency_penalty=0.3`, `presence_penalty=0.2`, system prompt anti-repetition instruction, and `_dedup_script()` post-processing to catch degeneration loops. **Has retry + fallback** (same model chain as other modules — see LLM Retry Pattern below).

**Output auto-chmod:** `script.md` and MP3 are `chmod 777` after creation for Syncthing sync.

### Podcast Pitfalls

1. **Edge TTS voice names changed**: Newer `edge-tts` versions require `Neural` suffix (e.g., `zh-TW-HsiaoChenNeural`, not `zh-TW-TingTing`). Check available voices with `edge_tts.list_voices()`.
2. **pydub is too slow for 100+ segments**: Each `AudioSegment.from_file()` re-decodes. Use ffmpeg concat demuxer instead (`ffmpeg -f concat -safe 0 -i list.txt -acodec libmp3lame out.mp3`). pydub kept as fallback only.
3. **ffmpeg concat requires same codec params**: All edge-tts MP3 segments share the same format by default, but if segments come from different sources, use `-acodec libmp3lame` (re-encode) instead of `-c copy`.
4. **Large videos produce 200+ segments**: LLM script generation is the fast part; TTS + merge dominates. 200 segments ≈ 3-4 min TTS + 10s merge (ffmpeg) vs 5+ min (pydub).
5. **LLM degeneration (repetition loops)**: Small models (especially `meta/llama-3.1-8b-instruct`) produce infinite repetition on Chinese text — same sentence repeated 100+ times, inflating script from ~4KB to 28KB+ and MP3 from ~5MB to 34MB+. Mitigations already built in: `frequency_penalty=0.3`, `presence_penalty=0.2`, system prompt anti-repetition instruction, `_dedup_script()` post-processing that truncates at 3rd repeat. If this still happens, the model is too weak — upgrade via `NVIDIA_ORGANIZE_MODEL` env var. Tested: `deepseek-ai/deepseek-v4-flash` (284B MoE) handles Chinese well with no degeneration.
6. **`uv run yt-dlp` fails in Docker**: The `_get_video_title()` function uses `shutil.which("yt-dlp") or "/opt/data/.venv/bin/yt-dlp"` directly instead of `uv run yt-dlp`, because `uv` can't discover Python installations in the Docker container (permission denied on `/root/.local/share/uv/python`). If title extraction fails, check that yt-dlp is installed in the venv.
7. **NVIDIA API 503 ResourceExhausted**: When running `--podcast dual --ppt --visual` together, all three modules call the same NVIDIA API endpoint sequentially. If the worker pool is already saturated (e.g. from a previous heavy run), later calls get `503: Worker local total request limit reached (48/48)`. The podcast module handles this gracefully (falls back to default data), but PPT/visual may produce sparse output. **Mitigation:** Run `--podcast` first, wait a few minutes, then add `--ppt --visual` in a second pass if 503 occurs.
8. **Edge-TTS intermittent `NoAudioReceived`**: Edge-TTS randomly fails with `NoAudioReceived` on longer text segments (>200 chars). Not a rate limit — appears to be a connection/timeout issue. **Fix:** Split script into paragraphs ≤200 chars each, `asyncio.sleep(2-3)` between segments, 3 retries per segment with backoff. Combine with pydub `AudioSegment.from_mp3()` + `+=` concatenation. Corrupted segments (0-byte or invalid MP3) should be skipped gracefully. **ALWAYS use `tempfile.TemporaryDirectory` for segment files** — do NOT save `_seg_*.mp3` to the output/obsidian directory. Only the final merged `_podcast.mp3` should be saved. User preference: "seg音檔不要存obsidian".
9. **Git snapshot before refactoring**: Always `git add -A && git commit -m "snapshot: pre-<feature>"` before multi-file refactoring. Without a commit, there is no rollback point if the refactor breaks something. This is a general workflow rule, not specific to this pipeline.
10. **NEVER delete/move user's completed work without confirmation**: On 2026-07-26, agent moved completed podcast folders (牙結石, 更年期後肌肉流失, Rick Astley) to archive/ thinking they were "test files". User was upset: "你把其他作好的刪除作什麼". **Rule:** Before moving or deleting any file/folder, confirm with user which are completed works vs test artifacts. When in doubt, ask first.

11. **Segment files should NOT be saved to obsidian vault**: User explicitly said "seg音檔不要存obsidian". Use `tempfile.TemporaryDirectory` for `_seg_*.mp3` files during TTS generation. Only the final merged `_podcast.mp3` and `script.md` should be saved to the output directory.

12. **notehub must use shared podcast.py, NOT its own prompt**: The notehub pipeline (`notehub/core/pipeline.py`) MUST import and call `podcast.py`'s `produce_podcast()` directly — never use a wrapper with a generic LLM prompt. Reason: `podcast.py`'s `_SOLO_PROMPT` / `_DUAL_PROMPT` are specifically designed for clean spoken-text output (no meta-commentary like "好的，沒問題！...", no `**` markdown markers, no stage directions). A generic prompt produces text with formatting that Edge-TTS reads literally as "asterisk asterisk". The correct import: `from podcast import produce_podcast` (from `notehub/core/pipeline.py`), NOT `from ..generators.podcast import produce_podcast`. Parameter order: `(transcript, title, url, lang, mode, voice_a, voice_b, out_dir, video_id)`. Return value is `mp3_path` (single string), not a tuple.

13. **Non-YouTube sources without captions (Bilibili, Vimeo, etc.)**: The `InstagramExtractor` handles Instagram natively (yt-dlp audio → Groq Whisper). For other non-YouTube platforms (Bilibili, Vimeo, etc.), the YouTubeExtractor won't match and the URLExtractor may fail to extract meaningful content. Use the manual Groq Whisper workflow:

    ```bash
    # Step 1: yt-dlp download audio (supports Bilibili, Vimeo, YouTube, 1000+ sites)
    yt-dlp -x --audio-format m4a -o "/tmp/audio/%(id)s.%(ext)s" "URL"

    # ⚠️ Groq 413 fix: Groq rejects files >~10MB with "Request Entity Too Large".
    # Convert to opus at 32k to shrink ~14MB m4a → ~4.5MB opus:
    ffmpeg -y -i /tmp/audio/<id>.m4a -c:a libopus -b:a 32k /tmp/audio/<id>.opus

    # Step 2: Groq Whisper transcribe (free, fast, supports Chinese)
    # GROQ_API_KEY must be set in /opt/data/.env
    python3 -c "
    from groq import Groq
    key = [l.strip().split('=', 1)[1] for l in open('/opt/data/.env').read().split(chr(10)) if l.strip().startswith('GROQ_API_KEY=')][0]
    client = Groq(api_key=key)
    with open('/tmp/audio/<id>.opus','rb') as f:
        r = client.audio.transcriptions.create(file=('audio.opus',f), model='whisper-large-v3', language='zh')
    with open('/tmp/<id>-transcript.md','w') as f: f.write(r.text)
    print(f'Transcribed: {len(r.text)} chars')
    "

    # Step 3: Run notehub on transcript
    python -m notehub /tmp/<id>-transcript.md --podcast solo --lang zh 台女
    ```

    **⚠️ Garbled directory name from text source — user will say "沒看到檔案":** When feeding a text file to notehub (instead of a YouTube URL), the output directory name is derived from the **filename**, not the actual video title. Example: `Lun Yydhpyy 抄本 [1187f09b51b4]/` instead of `AI Coding的最後一道牆 [luN-yydHpYY]/`. **This is the #1 cause of "找不到檔案" confusion.** The user sees the garbled name and cannot find their podcast. Always verify the title via `yt-dlp --print title "original_URL"` and rename the directory before reporting output to user. See **Post-Pipeline: Output Organization & Cleanup** above for the full rename workflow.

    **⚠️ Common mistake:** Do NOT manually scrape web content for video platforms — always use yt-dlp + Whisper. Manual scraping loses audio tone, timing, and nuance that Whisper captures. The user explicitly called this out: "所以step1-5也沒用groq whisper啊".

    **Setup:** `uv pip install groq` (tested with groq==1.6.0). **Groq API key:** `GROQ_API_KEY` in `/opt/data/.env`. Free tier, no credit card.

    **Verified output** (2026-07-26, Bilibili BV1Gv7V6BEjL, 12 min Chinese): yt-dlp downloaded 12.5MB m4a → Groq Whisper transcribed 4510 chars in ~10s → notehub generated 34-line script + 266s MP3 (1MB). Full pipeline under 5 minutes.

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

**Output:** `{dir_title}_summary.png` (1920×1080 Full HD, dark theme, card-based layout with icons, topics, and stats). Font sizes large for elderly readability — **minimum 36px, all bold**: title 80px, tagline 42px, card label 48px, card detail 36px, stat value 72px, stat label 36px, icon 60px. Card height 260px, card gap 24px, stats bar 200px. Canvas `MARGIN = 60`.

**How it works:**
1. LLM extracts visual data (title, tagline, topics with icons, key stats)
2. `visual_gen.py` renders a Pillow image with rounded-rect cards, CJK font support, warm accent colors
3. Uses `deepseek-ai/deepseek-v4-flash` for extraction

**Dependencies:** `Pillow` (already installed)

### Visual Pitfalls

1. **CJK font priority — NotoSansSC first for full coverage**: Font priority in `visual_gen.py` `_load_font()`:
   1. **Noto Sans SC** (`/opt/data/fonts/NotoSansSC-Bold.ttf`) —繁簡全覆蓋, clean modern sans-serif, **MUST be first** (iansui can't render Simplified Chinese)
   2. **芫荽 iansui** (`/opt/data/fonts/Iansui-Regular.ttf`) — warm kai-style, Traditional Chinese only, fallback
   3. **WenQuanYi Zen Hei** (`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`) — functional but ugly
   4. **DejaVu** — last resort, no CJK support
   
   **⚠️ LLM prompt must enforce Traditional Chinese**: Add to visual/podcast prompts: `⚠️ 重要：所有文字必須使用「繁體中文」（Traditional Chinese），禁止使用簡體中文。` Without this, DeepSeek defaults to Simplified Chinese even with `--lang zh`.

   **Emoji font** (loaded separately for icon rendering, NOT in `_load_font()`):
   - **Noto Emoji monochrome** (`/opt/data/fonts/NotoEmoji-Regular.ttf`) — renders emoji as white outlines on dark background

   **Installing fonts in Docker** (no root for apt): Download from GitHub releases using Python urllib (NOT curl — curl gets blocked/redirected by GitHub and produces tiny corrupt files):
   ```python
   import urllib.request
   req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/octet-stream'})
   data = urllib.request.urlopen(req, timeout=30).read()
   with open('font.ttf', 'wb') as f: f.write(data)
   ```
   For iansui: get release URL via `https://api.github.com/repos/ButTaiwan/iansui/releases/latest`, extract `assets[].browser_download_url`, then download with urllib. Only one TTF in the zip (`Iansui-Regular.ttf`). Save to `/opt/data/fonts/Iansui-Regular.ttf`.

3. **Emoji icons need separate font — iansui has no emoji glyphs**: When using CJK fonts like iansui, emoji characters (🦷💧💔) render as tofu/replacement characters. **Fix:** Load Noto Emoji monochrome (`/opt/data/fonts/NotoEmoji-Regular.ttf`) as a separate font and render icons in their own `draw.text()` call. Pillow cannot mix fonts in one call — each `draw.text()` uses one font. Install Noto Emoji from Google Fonts CSS API: `https://fonts.googleapis.com/css2?family=Noto+Emoji` → extract first `url()` → download with urllib. Only the monochrome variant works with Pillow (color emoji `NotoColorEmoji.ttf` uses CBDT/CBLC format unsupported by Pillow).

   **Noto Emoji installation steps:**
   ```python
   import urllib.request
   # 1. Get font URL from Google Fonts CSS
   req = urllib.request.Request("https://fonts.googleapis.com/css2?family=Noto+Emoji",
                                headers={"User-Agent": "Mozilla/5.0"})
   css = urllib.request.urlopen(req).read().decode()
   url = css.split("url(")[1].split(")")[0]
   # 2. Download monochrome TTF
   req2 = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
   data = urllib.request.urlopen(req2).read()
   with open("/opt/data/fonts/NotoEmoji-Regular.ttf", "wb") as f:
       f.write(data)
   ```
   File: ~880KB. Renders emoji as white outlines on dark background.

4. **Resolution must be 1920×1080 (Full HD)**: User rejected 1200×675 as "不夠清晰". Never downgrade resolution.

3. **NVIDIA API 503 ResourceExhausted — now handled by retry+fallback**: See **LLM Retry Pattern** section above for the standardized retry+fallback logic now built into all modules. When running `--podcast dual --ppt --visual` together, all three modules hit the same endpoint sequentially — retry logic handles transient 503s automatically. If ALL fallback models are exhausted, visual falls back to sparse default data. **Last resort:** Wait 5 min and re-run just `--visual`.

## Title Translation

When `--lang` differs from the source language (e.g. `--lang zh` on an English video):
- **`dir_title`** = LLM-translated title (used for directory name + MP3/PPT/visual filenames)
- **`title`** = original English title (used in frontmatter `source` field + transcript content)

Translation uses a fast LLM call (`max_tokens=100`, `temperature=0.3`) via `_translate_title()` in `podcast.py`. **Has retry + fallback** (same model chain — see LLM Retry Pattern below). Falls back to original title only after all models exhausted.

### Title Translation Pitfalls

1. **Must pass `dir_title` (not `title`) to all output modules**: `generate_ppt()`, `generate_visual()`, and `produce_podcast()` all receive `dir_title` as their title parameter. If you accidentally pass the English `title`, the output filenames will be English inside a Chinese directory name — inconsistent and confusing. The pipeline computes `dir_title` early (via `_translate_title()`) and threads it through all module calls.

2. **API timeout → English directory name fallback**: `_translate_title()` now has retry + fallback (3 models × 3 retries each). Translation only fails if ALL models in the chain are rate-limited simultaneously — rare. If it does fail, `dir_title` falls back to the original English title. **Workaround:** After pipeline completes, check if directory name is English. If so, manually rename with Python: `os.rename(old_dir, new_chinese_name)` + `chmod -R 777`.

## LLM Retry + Fallback Pattern (All Modules)

> ✅ **Standardized across all LLM call points** — `podcast.py` (translate + generate), `yt2md_pipeline.py` (organize per-chunk), `visual_gen.py` (visual data extraction).

### Rate Limiter (per-module, 2-second minimum)

Every API call site has a `_rate_limit()` function that enforces a **minimum 2-second gap** between consecutive NVIDIA API calls. This prevents burst-triggered 503s (the 40 RPM free tier = 1.5s/call; we use 2s for safety margin).

```python
# Each module defines this locally (no shared global):
_last_api_call = 0.0
_API_INTERVAL = 2.0

def _rate_limit():
    global _last_api_call
    elapsed = time.time() - _last_api_call
    if elapsed < _API_INTERVAL:
        time.sleep(_API_INTERVAL - elapsed)
    _last_api_call = time.time()
```

Called before every `client.chat.completions.create()`. A full pipeline run (~5 API calls) takes ~10-15 seconds of rate-limit wait, well within safe bounds.

See `references/nvidia-api-rate-limits.md` for NVIDIA's rate limit mechanism, cooldown behavior, and avoidance strategies.

### Fallback model chain (same in all modules):
1. `deepseek-ai/deepseek-v4-flash` (primary — 284B MoE, excellent Chinese)
2. `meta/llama-3.3-70b-instruct` (backup)
3. `nvidia/llama-3.1-nemotron-70b-instruct` (last resort)

**Retry behavior:**
- Per-model: 3 attempts with exponential backoff (base_delay × 2^attempt)
  - Script gen / visual: 5s → 10s → 20s
  - Title translate: 3s → 6s → 12s
  - Organize per-chunk: 3s → 6s → 12s
- Rate limit detection: `503` in error string OR `ResourceExhausted` OR `rate` (case-insensitive)
- Non-rate-limit errors: fail fast (no retry, return None)
- When a model exhausts retries: `break` to next model in chain
- When ALL models exhausted: print `[ERROR] ... all models exhausted`, return None (caller uses fallback behavior — default data for visual, raw transcript for organize, English title for translate)

**Key design decision:** Each module defines its own `_FALLBACK_MODELS` list locally (not shared global). This avoids import dependency between modules and allows independent tuning. All three currently use the same chain.

**NVIDIA API note:** The 503 `ResourceExhausted` error is **worker-level** (shared 48-request pool across ALL models), NOT per-model. All models share the same rate limit. The retry+fallback buys time (total wait ~63s per model × 3 models = ~3 min max), which is usually enough for the worker pool to recover.

## Auto Traditional Chinese Conversion

> ⚠️ **User preference (hard rule):** All Chinese output must be Traditional Chinese (Taiwan). Do not leave Simplified Chinese in any output file.

When `--lang zh` or `--lang zh-TW` is used, pipeline.py's `_convert_to_traditional()` runs as a post-processing step after all output generation. It uses `opencc` with `s2twp` config to convert all `.md` files in the output directory from Simplified Chinese → Traditional Chinese (Taiwan).

**Known opencc `s2twp` over-conversions (auto-fixed in `_convert_to_traditional()`):**
- `指令碼` → `腳本` (opencc converts "脚本" → "指令碼", but "腳本" is correct in Taiwan)
- `全域性` → `全局` (opencc converts "全局" → "全域性", but "全局" is standard in both)
- `演演算法` → `演算法` (opencc double-converts "算法" → "演算法" → "演演算法")

See `references/opencc-over-conversions.md` for details and fixes.

The Groq Whisper transcript (raw.md) is always Simplified Chinese; the LLM-generated script (script.md) depends on the model but DeepSeek often outputs Simplified Chinese too. This step ensures both are consistently Traditional Chinese.

**Bulk conversion (existing folders):** To scan and convert all files under any directory, use opencc directly:
```python
import opencc
converter = opencc.OpenCC("s2twp")
# Apply to each .md file, then fix over-conversions with .replace()
```

## Final chmod Sweep

All outputs in the podcast directory get `chmod -R 777` after generation, ensuring Syncthing compatibility across devices (Docker hermes user vs phone uid 1000).

## PPT-to-Video Conversion (Manual Workflow)

> ⚠️ **Not yet automated in NoteHub** — this is a manual workflow discovered on 2026-07-27. Use when the user wants to convert a PPT presentation + audio narration into an MP4 video.

### Pipeline

```
python-pptx (create slides)
  → Pillow (render slides to PNG frames, CJK font support)
  → Edge-TTS (generate narration audio)
  → ffmpeg (combine frames + audio → MP4)
```

### Step-by-step

```bash
# 1. Create PPT with python-pptx (16:9 widescreen)
# 2. Render each slide to 1920×1080 PNG using Pillow:
#    - Use NotoSansSC-Bold for CJK text (/opt/data/fonts/NotoSansSC-Bold.ttf)
#    - Use NotoEmoji-Regular for emoji icons (/opt/data/fonts/NotoEmoji-Regular.ttf)
#    - Manual word wrapping (Pillow has no auto-wrap)
#    - Each draw.text() call uses ONE font — cannot mix CJK + emoji in one call
# 3. Generate audio with Edge-TTS:
source /opt/data/.venv/bin/activate
python3 -c "
import edge_tts, asyncio
async def main():
    c = edge_tts.Communicate('narration text', 'zh-TW-HsiaoChenNeural')
    await c.save('narration.mp3')
asyncio.run(main())
"
# 4. Create per-slide clips (each frame displayed for audio_duration/N seconds):
ffmpeg -y -loop 1 -i frame_000.png -t 7.05 -c:v libx264 -pix_fmt yuv420p -r 30 clip_000.mp4
# 5. Concatenate clips + add audio:
ffmpeg -y -i clip_000.mp4 -i clip_001.mp4 -i clip_002.mp4 \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[outv]" -map "[outv]" video_only.mp4
ffmpeg -y -i video_only.mp4 -i narration.mp3 -c:v copy -c:a aac -shortest output.mp4
```

### CJK Rendering Pitfalls

1. **AI-generated images cannot render CJK text** — Any image from Agnes/NVIDIA/Gemini with Chinese characters in the prompt produces garbled squares. Always generate text-free illustrations, then overlay CJK text with Pillow.

2. **Emoji in CJK context shows squares** — Even with NotoSansSC, emoji characters (📍🗺️🏯) render as replacement characters (□). Use NotoEmoji-Regular.ttf loaded as a SEPARATE font for each emoji draw call.

3. **Text overflow / truncation** — Pillow has no automatic word wrapping. Must manually split text into lines that fit within `max_width` pixels. CJK characters are ~2x width of ASCII characters.

4. **Font size too small / too much whitespace** — Minimum recommended sizes for 1920×1080: title 100px+, body 48px+, list items 44px+. Fill the frame — don't leave large empty areas.

5. **LibreOffice not available in Docker** — Cannot use `libreoffice --headless --convert-to png` to render PPT slides. Must use Pillow to manually draw the content.

### Dependencies

```bash
# All already installed in the environment:
# python-pptx, Pillow, edge-tts, ffmpeg
# Verify:
python3 -c "import pptx; print('python-pptx OK')"
python3 -c "from PIL import Image; print('Pillow OK')"
ffmpeg -version | head -1
```

## See Also
## Voice Shortcuts (NoteHub CLI)

Voice aliases can be placed anywhere in args — no `--voice-*` flag needed:

```bash
python -m notehub source --podcast solo 台女
python -m notehub source --podcast dual 台女 台男
python -m notehub source --podcast solo 台男 --lang zh
```

| Alias | Voice ID | Language |
|-------|----------|----------|
| 台男 | zh-TW-YunJheNeural | 繁中男 |
| 台女 | zh-TW-HsiaoChenNeural | 繁中女 |
| 英男 | en-US-GuyNeural | 美式男 |
| 英女 | en-US-JennyNeural | 美式女 |
| 美男 | en-US-ChristopherNeural | 美式男（低沉） |
| 美女 | en-US-AriaNeural | 美式女（自然） |
| 日男 | ja-JP-KeitaNeural | 日文男 |
| 日女 | ja-JP-NanamiNeural | 日文女 |

Default voice (no alias specified): `zh-TW-HsiaoChenNeural` (台女).

Implementation: `notehub/__main__.py` scans `pipeline_args` for any value in `VOICE_ALIASES` dict. First match → `voice_a`. Full Edge-TTS voice names still work via `--voice-a`/`--voice-b`.

## Usage (NoteHub — recommended entry point)

```bash
# YouTube
python -m notehub "https://youtube.com/watch?v=xxx" --podcast dual --ppt --visual --lang zh 台女 台男

# Instagram Reel (auto-downloads audio + Groq Whisper + TC conversion)
python -m notehub "https://www.instagram.com/reel/xxx" --podcast solo --lang zh 台女

# Bilibili / non-YouTube video (manual Groq Whisper)
yt-dlp -x --audio-format m4a -o "audio/%(id)s.%(ext)s" "BILIBILI_URL"
# Then: python -m notehub transcript.md --podcast solo --ppt --visual 台女

# Web URL
python -m notehub "https://example.com" --organize --visual

# PDF / text file
python -m notehub ./doc.pdf --organize --ppt
python -m notehub ./notes.txt --podcast solo 台男

# Search & manage
python -m notehub --search "AI"
python -m notehub --list
python -m notehub --stats
```

## Post-Pipeline: Output Organization & Cleanup

notehub outputs podcast files to `/opt/data/obsidian-vault/口播/` for YouTube and Instagram sources, and to `/opt/data/obsidian-vault/notes/` for URL/PDF/text sources. After every pipeline run, verify the output:

1. **Check output directory**: 
   - YouTube & Instagram → `口播/{title} [{video_id}]/`
   - URL/PDF/text → `notes/{title} [{hash}]/`
2. **Report to user**: include the final path (`**路徑：** /opt/data/obsidian-vault/口播/...`)

> ⚠️ **Garbled title from text source (only):** When notehub processes a **text file** (Whisper transcript that was manually fed in), the output directory name is derived from the **filename**, not the video title (e.g. `Lun Yydhpyy 抄本 [hash]/` instead of the real title). This does NOT happen with YouTube or Instagram sources — those extractors get the real title. If feeding a text/Whisper file manually, see the manual workflow in `instagram-reel-podcast` skill.

## Legacy entry point (backward compatible)

```bash
uv run python3 SKILL_DIR/scripts/yt2md_pipeline.py "URL" --podcast dual --ppt --visual --lang zh
```

## See Also
- `instagram-reel-podcast` skill — legacy manual Instagram workflow (pre-notehub-integration reference)
- `references/opencc-over-conversions.md` — opencc s2twp over-conversion fixes when converting SC→TC
- `references/groq-whisper-integration.md` — Groq Whisper STT for non-YouTube sources (Bilibili, Vimeo, local video). Free tier, setup, usage pattern.
- `references/voice-shortcuts.md` — Voice alias reference, Edge-TTS reliability notes, pipeline integration details.
- `references/cjk-font-rendering.md` — CJK font inventory, emoji rendering patterns, Pillow font mixing, Docker font installation.
- `references/pipeline-architecture.md` — detailed pipeline architecture, `--obsidian` subfolder usage, VTT garbled-text caveats, and API migration notes.
- `references/organize-architecture.md` — LLM post-processing design: NVIDIA API integration, prompt template, chunking strategy, error handling.
- `references/podcast-architecture.md` — podcast mode flow, prompt templates, Edge TTS voice names, audio merge strategy, Python 3.13 compatibility.
- `references/translation-and-troubleshooting.md` — bilingual translation format, language fallback chain, common yt-dlp fixes, Whisper on RPi tips.
- `references/nvidia-api-rate-limits.md` — NVIDIA NIM free tier rate limits: 40 RPM baseline, unpredictable cooldown (30s-2h+), no usage API, avoidance strategy.
