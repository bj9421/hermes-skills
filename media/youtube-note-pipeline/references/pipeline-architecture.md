# Pipeline Architecture Notes

## Why 3-Stage Auto-Fallback?

Each pipeline stage exists because no single backend works for every video:

| Priority | Pipeline | Why it's here | Caveat |
|----------|----------|---------------|--------|
| **1** | `youtube-transcript-api` | Returns **segments** (one logical sentence per entry) — cleanest, no overlap | Fails on some region-locked or API-restricted videos |
| **2** | `yt-dlp VTT` | Works where API fails, especially for auto-generated captions | Auto-captions produce **overlapping/phantom lines** — each timestamp block renders independently, and consecutive ASR windows overlap. The deduplicator helps but isn't perfect. |
| **3** | `faster-whisper` | Last resort for videos without any subtitles | CPU-only on RPi; `--model tiny` for long videos (200 MB RAM) |

## youtube-transcript-api v1.x API

The library uses **v1.x API** — the old `get_transcript()` classmethod is deprecated:

```python
# ✅ Correct (v1.x)
api = YouTubeTranscriptApi()
segments = api.fetch(video_id, languages=["en"])
for seg in segments:
    print(seg.text, seg.start, seg.duration)  # .text, .start, .duration

# ❌ Deprecated — will raise AttributeError
segments = YouTubeTranscriptApi.get_transcript(video_id)
```

Available methods: `fetch()`, `list()` (both instance methods).

## Output Path Configuration

`OBSIDIAN_BASE = /opt/data/obsidian-vault/   # vault root, no intermediate Holographic/`

- `--obsidian` → saves to `{OBSIDIAN_BASE}/YouTube/{title}.md`
- `--obsidian "我的筆記/yt2md"` → saves to `{OBSIDIAN_BASE}/我的筆記/yt2md/{title}.md`
- Subdirectories are auto-created via `os.makedirs(exist_ok=True)`
- Filename sanitized: `re.sub(r'[<>:"/\\|?*]', '_', title)` truncated to 120 chars

## Timestamp Policy

**Always preserved.** Every pipeline produces `[MM:SS]` or `[HH:MM:SS]` markers per segment. Do not strip, reformat, or remove them unless the user explicitly says "不用時間軸" or similar.

## Obsidian Frontmatter

```markdown
---
created: 2026-07-07
source: https://youtube.com/watch?v=...
title: Video Title
language: en            # detected language from pipeline
pipeline: transcript-api # which backend succeeded: transcript-api | vtt | whisper-{size}
tags: [youtube, transcript]
---
```

## Known Pitfalls

- **VTT auto-generated captions** are designed for on-screen display, not parsing. Each subtitle frame is independently rendered, so consecutive frames overlap by ~1-2 words. Pipeline 1 avoids this entirely.
- **`yt-dlp` JS runtime**: YouTube extraction without a JS runtime is deprecated. Install `node` and set `--js-runtimes node:node` in config or per-command. The pipeline handles this internally.
- **Audio download failures**: Some videos block audio extraction. Pipeline 3 will fail with "Cannot download audio" — tell the user the video likely has DRM or is geo-blocked.
