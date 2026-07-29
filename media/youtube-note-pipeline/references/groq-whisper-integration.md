# Groq Whisper Integration for Non-YouTube Sources

## Overview

Groq provides free Whisper STT API (whisper-large-v3). Used for non-YouTube video platforms (Bilibili, Vimeo, local .mp4) where youtube-transcript-api doesn't work.

## Setup

```bash
# 1. Get free API key from https://console.groq.com
# 2. Add to /opt/data/.env
echo 'GROQ_API_KEY=gsk_...' >> /opt/data/.env

# 3. Install SDK
uv pip install groq
```

## Usage Pattern

```python
from groq import Groq

# Load key from .env
api_key = None
with open('/opt/data/.env') as f:
    for line in f:
        stripped = line.strip()
        if stripped.startswith('GROQ_API_KEY='):
            api_key = stripped.split('=', 1)[1]
            break

client = Groq(api_key=api_key)

# Transcribe
with open('audio.m4a', 'rb') as f:
    result = client.audio.transcriptions.create(
        file=('audio.m4a', f),
        model='whisper-large-v3',
        language='zh',
        response_format='verbose_json',
    )

print(result.text)       # Full transcript
print(result.duration)   # Duration in seconds
```

## Supported Formats

m4a, mp3, wav, webm, mp4, mpeg, mpga, ogg, flac. Max 25MB (Groq free tier). Split larger files with ffmpeg.

## Free Tier Limits

~20 requests/minute, no credit card, whisper-large-v3 model.

## yt-dlp Audio Download

```bash
# Bilibili
yt-dlp -x --audio-format m4a -o "audio/%(id)s.%(ext)s" "https://b23.tv/xxxxx"
# Vimeo
yt-dlp -x --audio-format m4a -o "audio/%(id)s.%(ext)s" "https://vimeo.com/xxxxx"
```

## vs NVIDIA NIM Whisper

| Feature | Groq Whisper | NVIDIA NIM Whisper |
|---------|-------------|-------------------|
| Free tier | ✅ Yes | ❌ Needs GPU |
| Speed | Fast (cloud) | Slow (CPU on RPi4) |
| Chinese | ✅ whisper-large-v3 | ✅ same model |
| Setup | API key only | Docker + GPU |

**Decision:** Always use Groq Whisper for non-YouTube transcription. NVIDIA NIM Whisper requires GPU Docker (not feasible on RPi4).
