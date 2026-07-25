# YouTube Note Pipeline — Translation & Common Fixes

## Bilingual Translation Format

Default output style for zh-TW translation:

```markdown
[00:00] Welcome to this tutorial on neural networks.
[00:00] 歡迎來到這個神經網路教學課程。

[01:15] The first concept we need to understand is backpropagation.
[01:15] 我們需要了解的第一個概念是反向傳播。

[03:42] This allows the model to learn from its errors.
[03:42] 這讓模型能夠從錯誤中學習。
```

## Language Fallback Chain

When fetching subtitles, try in order:
1. zh-TW (Traditional Chinese, Taiwan)
2. zh-Hant (Traditional Chinese, generic)
3. zh-Hans (Simplified Chinese)
4. en (English)
5. ja (Japanese — common for tech content)
6. any (last resort, whatever YouTube provides)

## Common yt-dlp Fixes

| Problem | Fix |
|---------|-----|
| "Sign in to confirm" | `--extractor-args "youtube:player_client=android"` |
| JS challenge failure | `--js-runtimes node:node` |
| Geo-blocked | `--geo-bypass` |
| Age-restricted | `--age-limit 21` or cookie file |

## Whisper on RPi 4

- **Default model:** `small` (~1 GB RAM, good accuracy)
- **If OOM:** `--model tiny` (~200 MB RAM)
- **Very long videos (>1 hour):** segment audio into 10-min clips, transcribe separately, merge by timestamp
- **Compute type:** int8 (default for CPU; cuts RAM usage ~2x vs float16)

## Markitdown Notes

markitdown converts VTT to Markdown but may produce messy output with embedded timestamps and speaker labels. When markitdown output looks bad, fall back to the `vtt_to_text()` function in the script which strips all formatting and returns clean paragraph text.
