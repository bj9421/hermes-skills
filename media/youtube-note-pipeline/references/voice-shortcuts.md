# Voice Shortcuts & Edge-TTS Reliability

## Voice Alias Table

| Alias | Voice ID | Language | Notes |
|-------|----------|----------|-------|
| 台男 | zh-TW-YunJheNeural | 繁中男 | Default male for dual |
| 台女 | zh-TW-HsiaoChenNeural | 繁中女 | Default female, solo default |
| 英男 | en-US-GuyNeural | 美式男 | |
| 英女 | en-US-JennyNeural | 美式女 | |
| 美男 | en-US-ChristopherNeural | 美式男（低沉） | |
| 美女 | en-US-AriaNeural | 美式女（自然） | |
| 日男 | ja-JP-KeitaNeural | 日文男 | |
| 日女 | ja-JP-NanamiNeural | 日文女 | |

## Implementation

In `notehub/__main__.py`:
1. `VOICE_ALIASES` dict maps Chinese shortcuts → full Edge-TTS voice names
2. `resolve_voice(v)` looks up alias, returns full name or passes through
3. After parsing `--voice-a`/`--voice-b`, scans remaining args for alias matches
4. First match → `voice_a` (if no explicit `--voice-a`)
5. `--voice-a`/`--voice-b` flags take priority over auto-detection

## Edge-TTS Reliability

Edge-TTS is intermittently unstable (rate limiting, `NoAudioReceived` errors, timeouts). All mitigations are in `podcast.py`:

### Retry pattern
- 5 attempts per segment with exponential backoff (5s/10s/15s/20s/25s)
- Rate limit: 2s minimum between API calls (`_tts_last_call` global timestamp)

### Long-text splitting
- `_split_long_text(text, max_chars=200)` splits at sentence boundaries (`。！？.!?`)
- Each chunk generated separately, merged via pydub `AudioSegment`
- Prevents `NoAudioReceived` on longer paragraphs

### Segment file handling
- **ALWAYS** use `tempfile.TemporaryDirectory` for `_seg_*.mp3`
- NEVER save segment files to output/obsidian directory
- Only final merged `_podcast.mp3` + `script.md` go to output dir
- User preference: "seg音檔不要存obsidian"

### Common failure modes
1. `NoAudioReceived` — text too long or connection timeout → split + retry
2. Timeout at 180s — text too long for single segment → split into ≤200 char chunks
3. Intermittent 503 — Edge-TTS server overload → retry with backoff
4. Corrupted segment (invalid MP3) — skip and continue, don't abort entire pipeline

## Pipeline Integration

NoteHub pipeline (`notehub/core/pipeline.py`) directly imports `podcast.py`'s `produce_podcast()`:
```python
from podcast import produce_podcast  # NOT from ..generators.podcast
```

This ensures shared prompt templates (`_SOLO_PROMPT` / `_DUAL_PROMPT`) produce clean spoken-text output without meta-commentary or markdown markers.
