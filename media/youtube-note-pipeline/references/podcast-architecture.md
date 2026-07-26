# Podcast Mode Architecture

## Flow

```
Transcript (raw text from pipeline)
    ↓
LLM Script Generation (NVIDIA API)
    → solo: paragraphs
    → dual: A:/B: alternating dialogue
    ↓
Dedup post-processing (_dedup_script)
    → detects 3+ consecutive identical lines → truncates
    ↓
TTS Segments (Edge TTS, async)
    → voice_a for A/solo, voice_b for B
    → each segment → separate MP3
    ↓
Merge (ffmpeg concat demuxer)
    → concat list file → single MP3
    ↓
Output: 口播/{title} [{video_id}]/{title}_podcast.mp3 + script.md
```

## Script Prompts

### Solo
- First-person narrator, conversational tone
- Natural transitions ("接下來...", "有趣的是...")
- Opening intro + closing summary
- No timestamps [MM:SS]

### Dual
- A (主持人): asks questions, guides topics, summarizes
- B (評論員): deep analysis, examples, elaboration
- Max 3 consecutive same-role turns
- A opens and closes

## LLM Configuration &防护

**Default model:** `deepseek-ai/deepseek-v4-flash` (284B MoE, strong Chinese)
**Override:** env var `NVIDIA_ORGANIZE_MODEL`
**API:** NVIDIA Integrate (`integrate.api.nvidia.com/v1`)

### Anti-degeneration measures (all applied in `podcast.py`):

1. **frequency_penalty=0.3** — penalizes token reuse within the response
2. **presence_penalty=0.2** — encourages new topics over repetition
3. **System prompt** — explicit instruction: "嚴格禁止重複相同或相似的段落，每個論點只講一次"
4. **max_tokens=4096** — caps output length (8-min video ≈ 60 lines of script; 8192 was excessive)
5. **`_dedup_script()` post-processing** — scans output for 3+ consecutive near-identical lines (after stripping role prefix), truncates at first repeat

### Model selection notes

| Model | Chinese quality | Degeneration risk | Notes |
|-------|----------------|-------------------|-------|
| `meta/llama-3.1-8b-instruct` | ⭐⭐ | 🔴 HIGH | Known to loop on Chinese. Avoid for podcast. |
| `meta/llama-3.3-70b-instruct` | ⭐⭐⭐⭐ | 🟢 Low | Good fallback |
| `deepseek-ai/deepseek-v4-flash` | ⭐⭐⭐⭐⭐ | 🟢 Low | Current default. 284B MoE. |
| `qwen/qwen3-235b-a22b` | ⭐⭐⭐⭐⭐ | 🟢 Low | Best Chinese if available |

If degeneration still occurs with the default model, check `NVIDIA_ORGANIZE_MODEL` override — the caller may have set a weaker model.

## Edge TTS Voice Names (v7+)

| Role | Voice ID | Gender |
|------|----------|--------|
| A (host) | `zh-TW-HsiaoChenNeural` | Female |
| B (commentator) | `zh-TW-YunJheNeural` | Male |
| Alt female | `zh-TW-HsiaoYuNeural` | Female |

Full voice list: `edge_tts.list_voices()` → filter by `ShortName`.

## Audio Merge Strategy

- **Primary:** ffmpeg concat demuxer (fast, <10s for 200+ segments)
  - `ffmpeg -f concat -safe 0 -i list.txt -acodec libmp3lame -b:a 192k out.mp3`
  - Re-encodes to ensure uniform format
- **Fallback:** pydub AudioSegment (slow, ~5min for 200+ segments)
  - Used only if ffmpeg concat fails

## Python 3.13 Compatibility

- `pydub` requires `audioop-lts` package (audioop removed in 3.13)
- Install: `uv pip install audioop-lts`
- SyntaxWarning from pydub about regex escape sequences — harmless
