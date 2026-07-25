# Organize Architecture — LLM Post-Processing

> Design doc for `--organize` flag in `yt2md_pipeline.py`. Spec: `docs/specs/2026-07-25-organize-feature-design.md`

## LLM Integration

**Provider:** NVIDIA API (`https://integrate.api.nvidia.com/v1`)
**SDK:** `openai` Python package (compatible endpoint)
**Auth:** `NVIDIA_API_KEY` env var (read from environment, never hardcoded)
**Model:** `meta/llama-3.1-8b-instruct` (fast, free tier on NVIDIA)

### Why NVIDIA, not Hermes gateway

Hermes gateway is a **messaging router** (Telegram → Agent), not an LLM API server. Python scripts cannot call it for LLM completions. NVIDIA API is already configured in `config.yaml` and available.

### Connection Code Pattern

```python
from openai import OpenAI

client = OpenAI(
    base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    api_key=os.environ.get("NVIDIA_API_KEY", ""),
)

response = client.chat.completions.create(
    model="meta/llama-3.1-8b-instruct",
    messages=[
        {"role": "system", "content": ORGANIZE_PROMPT},
        {"role": "user", "content": raw_transcript},
    ],
    max_tokens=4096,
    temperature=0.3,  # low temp for faithful summarization
)
```

## Prompt Template

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

## Chunking Strategy

For transcripts > 25,000 characters (configurable via `LLM_MAX_CHARS`):

1. Split at paragraph boundaries near 25K chars
2. 1,000 char overlap between chunks (preserves context)
3. First chunk prompt: "this is part 1 of N"; last chunk prompt: "add overall summary"
4. Organize each chunk independently
5. Merge with `---` horizontal rules between chunks
6. Max 4096 tokens per LLM call output

## Error Handling

| Failure | Response |
|---------|----------|
| No `NVIDIA_API_KEY` | Print `[WARN] No API key, skipping organize`, save raw only |
| API timeout | Retry once (5s wait), then fall back to raw |
| API error (4xx/5xx) | Print error, save raw transcript |
| Rate limit | Wait 5s, retry once |
| Empty transcript | Skip organize, save raw |

**Golden rule:** Raw transcript is ALWAYS saved first. LLM processing is additive — failure never loses data.

## Output Format

### Organized file (`<title>.md`)

```markdown
---
created: 2026-07-25
source: https://youtube.com/watch?v=...
title: Video Title
language: zh-TW
pipeline: transcript-api
mode: organized
tags: [youtube, transcript, notes]
---

# Video Title

> https://youtube.com/watch?v=...

## 重點摘要

- 要點一
- 要點二
- 要點三

## [0:18] 第一段主題

精簡後的內容...

## [3:45] 第二段主題

精簡後的內容...
```

### Raw file (`<title>_raw.md`)

Same format as current output (timestamps + verbatim text), filename suffix `_raw`.

## Flags

| Flag | Effect |
|------|--------|
| `--organize` | Enable LLM post-processing (two-file output) |
| `--no-raw` | Skip raw backup file in organize mode (organized only) |
| `--whisper` | Force Whisper transcription (skip transcript-api + VTT) |
| `--model tiny` | Use smaller Whisper model (less RAM) |
| `-o out.md` | Save to specific file path |
| `--obsidian [subdir]` | Save to Obsidian vault (default subdir: `YouTube/`) |
