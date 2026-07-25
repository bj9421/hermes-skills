# Podcast Mode Architecture

## Flow

```
Transcript (raw text from pipeline)
    ↓
LLM Script Generation (NVIDIA API)
    → solo: paragraphs
    → dual: A:/B: alternating dialogue
    ↓
TTS Segments (Edge TTS, async)
    → voice_a for A/solo, voice_b for B
    → each segment → separate MP3
    ↓
Merge (ffmpeg concat demuxer)
    → concat list file → single MP3
    ↓
Output: 口播/{title}/{title}_podcast.mp3 + script.md
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
