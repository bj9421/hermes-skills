---
name: youtube-note-pipeline
description: YouTube/IG/Bilibili 影片轉口播 podcast 完整流程。Notehub CLI + bookmark-manager 整合。
related_skills: [verified-capabilities, taiwan-stock-data-pipeline, instagram-reel-podcast]
---

# NoteHub YouTube Pipeline

## 🎯 功能總覽

完整影片處理流程：YouTube/IG/Bilibili → Whisper 轉寫 → LLM 整理 → TTS 口播

## 📋 核心模組

| 模組 | 路徑 | 功能 |
|------|------|------|
| Pipeline | `notehub/core/pipeline.py` | 主流程協調 |
| LLM | `notehub/core/llm.py` | 多 provider fallback chain |
| Transcribe | `notehub/core/transcribe.py` | Whisper 三層 fallback |
| Podcast | `podcast.py` | 口播腳本生成 + TTS |
| Extractors | `notehub/extractors/` | YouTube/IG/Bilibili |

## 🔧 LLM Fallback Chain（2026-07-31 更新）

```
1. OpenCode Zen (deepseek-v4-flash-free) — 20 RPM
   ↓ 429 限流
2. AGNES API (agnes-2.5-flash) — 20 RPM
   ↓ 失敗
3. Groq (llama-3.3-70b-versatile) — 30 RPM
   ↓ 失敗
4. 本地正則 (add_punctuation.py) — ∞
```

## 📊 Provider RPM 限制

| Provider | 模型 | RPM | 狀態 |
|----------|------|-----|------|
| OpenCode Zen | deepseek-v4-flash-free | 20 | ❌ 429 限流中 |
| AGNES | agnes-2.5-flash | 20 | ✅ 正常 |
| Groq | llama-3.3-70b-versatile | 30 | ✅ 可用 |
| 本地正則 | add_punctuation.py | ∞ | ✅ 備用 |

## 🔒 RPM 限流保護（pitfall 22）

```python
# llm.py 中的 rate limiters
_zen_interval = 3.0   # 20 RPM
_agnes_interval = 3.0 # 20 RPM
_groq_interval = 2.0  # 30 RPM

def _rate_limit(latest_call: float, interval: float) -> float:
    with _rate_lock:
        elapsed = time.time() - latest_call
        if elapsed < interval:
            time.sleep(interval - elapsed)
        return time.time()
```

**🔴 規則**：任何 LLM 呼叫必須經過 `_rate_limit()`，禁止直接 `requests.post()`

## 📝 使用方式

```bash
# CLI
cd /opt/data/skills/media/youtube-note-pipeline/scripts
python -m notehub <url> --podcast solo --lang zh

# 直接呼叫
from notehub.core.llm import call_llm
result = call_llm([{'role': 'user', 'content': '...'}])
```

## ⚠️ Pitfalls

19. **抽共用模組前先調查既有實作** — 血的教訓：bilibili.py 的 `_check_size_and_compress` 早已存在，未參考導致重寫出缺陷版本

20. **notehub 口播 pipeline 的 LLM 一律不用 NVIDIA** — 範圍限定本 pipeline，NVIDIA 只負責 Whisper 轉寫

21. **Zen API 限流 fallback 流程** — 當 Zen 429 時，自動切換到 AGNES API（agnes-2.5-flash）

22. **RPM 限流保護** — 每個 provider 都有 `_rate_limit()`，避免 429 限流或封號

23. **Provider RPM 限制調查** — OpenCode Zen 未公開 RPM（實際被限），AGNES ~20 RPM，Groq 30 RPM / 6K TPM
