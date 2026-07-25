# yt2md `--organize` Feature Spec

**Date:** 2026-07-25
**Status:** Draft
**Author:** Hermes_Pi

## Problem

Current `yt2md_pipeline.py` outputs raw transcripts verbatim — timestamps + every spoken word including filler, repetitions, and disorganized rambling. Users must manually clean up the output to create usable notes.

## Goal

Add `--organize` flag that post-processes the raw transcript via LLM into a structured, clean note with summary, sections, and condensed text.

## User Story

```
As a user who watches YouTube videos for learning,
I want to run a single command that gives me an organized note,
So I don't have to manually clean up 30-minute transcripts.
```

## Architecture

```
yt2md_pipeline.py "URL" --organize --obsidian "我的筆記/yt2md"
     │
     ├── Stage 1: Fetch transcript (existing 3-pipeline fallback)
     │     └── Output: raw transcript text
     │
     ├── Stage 2: Save raw transcript → <title>_raw.md
     │
     └── Stage 3: LLM organize (NEW)
           ├── Input: raw transcript
           ├── API: NVIDIA (integrate.api.nvidia.com/v1)
           └── Output: organized markdown → <title>.md
```

### Output Files

| File | Content | When |
|------|---------|------|
| `<title>.md` | Organized note (summary + sections + clean text) | `--organize` |
| `<title>_raw.md` | Original raw transcript with timestamps | `--organize` (always saved as backup) |

Without `--organize`: behavior unchanged (single file, raw transcript).

## LLM Processing

### Prompt Strategy

The LLM receives the raw transcript and produces:

1. **Header Metadata** — title, source URL, date, tags
2. **Executive Summary** — 3-5 bullet points of key takeaways
3. **Structured Sections** — content divided by topic with `##` headings
4. **Condensed Text** — filler words removed, sentences cleaned, meaning preserved
5. **Timestamp References** — `[MM:SS]` markers preserved at section boundaries

### Prompt Template

```
你是一個專業的內容整理助手。請將以下 YouTube 影片逐字稿整理成結構化筆記。

要求：
1. 【重點摘要】— 3-5 個核心要點（bullet points）
2. 【內容整理】— 根據主題分段，每段加 ## 標題
3. 【精簡文字】— 去除贅字、口語重複、語助詞，保留完整語意
4. 【時間標記】— 在每個主要段落開頭保留 [MM:SS] 時間戳
5. 語言：與原文相同（中文影片用中文，英文影片用英文）

逐字稿：
{raw_transcript}
```

### Model Selection

- **Primary:** NVIDIA `meta/llama-3.1-8b-instruct` (fast, free tier)
- **Fallback:** Any model available via NVIDIA API
- **Max tokens:** 4096 output (covers most transcripts; chunk if longer)

### Chunking Strategy

For transcripts > 30,000 characters:
1. Split into ~20,000 char chunks with 1,000 char overlap
2. Organize each chunk independently
3. Merge with unified summary at top

## CLI Interface

```bash
# Existing (unchanged)
uv run python3 yt2md_pipeline.py "URL"
uv run python3 yt2md_pipeline.py "URL" --whisper --model tiny

# New: organize mode
uv run python3 yt2md_pipeline.py "URL" --organize
uv run python3 yt2md_pipeline.py "URL" --organize --obsidian "我的筆記/yt2md"
uv run python3 yt2md_pipeline.py "URL" --organize -o output.md

# Organize without saving raw (raw always saved alongside)
uv run python3 yt2md_pipeline.py "URL" --organize --no-raw
```

## Environment Variables

| Variable | Source | Usage |
|----------|--------|-------|
| `NVIDIA_API_KEY` | `.env` or config.yaml | LLM API authentication |
| `NVIDIA_BASE_URL` | Default: `https://integrate.api.nvidia.com/v1` | API endpoint |

Script reads from environment; no hardcoded keys.

## Error Handling

- **No API key:** Print warning, fall back to raw transcript (no organize)
- **API timeout:** Retry once, then fall back to raw
- **API error:** Print error, save raw transcript anyway
- **Rate limit:** Wait 5s and retry once

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `scripts/yt2md_pipeline.py` | Modify | Add `--organize`, `--no-raw`, LLM call, chunking |
| `SKILL.md` | Modify | Update usage docs with `--organize` examples |
| `references/organize-architecture.md` | Create | Detailed LLM prompt engineering notes |

## Testing

1. **Unit:** `_organize_via_llm()` with mock transcript
2. **Integration:** Full pipeline with `--organize` on a short English video
3. **Edge cases:** Empty transcript, very long transcript (>30K chars), non-English
4. **Fallback:** API down → still saves raw transcript

## Success Criteria

- [ ] `--organize` produces readable, structured notes
- [ ] Raw transcript always saved as backup
- [ ] Works without `--organize` (backward compatible)
- [ ] Handles API failures gracefully (falls back to raw)
- [ ] Cron jobs can use `--organize` unattended
