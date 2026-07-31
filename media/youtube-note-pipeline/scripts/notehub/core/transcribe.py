"""音訊轉寫共用模組 — Whisper fallback chain: Groq → NVIDIA → 本地 faster-whisper.

2026-07-31 使用者指示（硬性規則）：
先用 Groq Whisper（免費快速），fallback NVIDIA Whisper，
最後不行才跑本地 faster-whisper（RPi CPU 慢，但零依賴）。

所有 extractor（youtube / bilibili / instagram）共用此函數，
避免三份重複的 Groq 呼叫邏輯。
"""

import os
import subprocess
import sys

ENV_PATH = "/opt/data/.env"


def _load_key(name: str) -> str | None:
    """從 /opt/data/.env 讀 API key。"""
    try:
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"[ERROR] Cannot read {ENV_PATH}: {e}", file=sys.stderr)
    return None


def _compress_to_opus(path: str) -> str:
    """m4a → opus 32k（Groq 413 fix：>10MB 會被拒，14MB m4a → ~4.5MB opus）。"""
    opus_path = path.rsplit(".", 1)[0] + ".opus"
    size = os.path.getsize(path)
    print(f"[INFO] Audio {size/1024/1024:.1f}MB exceeds Groq limit, compressing...", file=sys.stderr)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-c:a", "libopus", "-b:a", "32k", opus_path],
            capture_output=True, text=True, timeout=60,
        )
        if os.path.exists(opus_path):
            print(f"[INFO] Compressed: {os.path.getsize(opus_path)/1024/1024:.1f}MB", file=sys.stderr)
            return opus_path
    except Exception as e:
        print(f"[WARN] Compression failed: {e}", file=sys.stderr)
    print("[WARN] Compression failed, using original file", file=sys.stderr)
    return path


def _transcribe_groq(audio_path: str, language: str = "zh") -> str | None:
    """Step 1: Groq Whisper（whisper-large-v3，免費快速）。"""
    groq_key = _load_key("GROQ_API_KEY")
    if not groq_key:
        print("[ERROR] GROQ_API_KEY not found in /opt/data/.env", file=sys.stderr)
        return None
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        with open(audio_path, "rb") as f:
            ext = os.path.splitext(audio_path)[1] or ".m4a"
            result = client.audio.transcriptions.create(
                file=(f"audio{ext}", f),
                model="whisper-large-v3",
                language=language,
                response_format="verbose_json",
            )
        text = result.text.strip()
        print(f"[OK] Groq Whisper: {len(text)} chars, {getattr(result, 'duration', '?')}s", file=sys.stderr)
        return text
    except Exception as e:
        print(f"[WARN] Groq Whisper failed: {e}", file=sys.stderr)
        return None


def _transcribe_nvidia(audio_path: str, language: str = "zh") -> str | None:
    """Step 2: NVIDIA Whisper（嘗試層）。

    ⚠️ 2026-07-31 查證：NVIDIA build.nvidia.com 的 Whisper 是 **gRPC-only**
    （grpc.nvcf.nvidia.com + function-id），無 OpenAI 相容 HTTP endpoint
    （integrate.api.nvidia.com / ai.api.nvidia.com 都 404）。
    此層保留快速嘗試，失敗即跳過 → 本地 faster-whisper。
    """
    nvidia_key = _load_key("NVIDIA_API_KEY")
    if not nvidia_key:
        print("[ERROR] NVIDIA_API_KEY not found in /opt/data/.env", file=sys.stderr)
        return None
    try:
        from openai import OpenAI
        client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key, timeout=10)
        with open(audio_path, "rb") as f:
            ext = os.path.splitext(audio_path)[1] or ".m4a"
            result = client.audio.transcriptions.create(
                file=(f"audio{ext}", f),
                model="openai/whisper-large-v3",
                language=language,
                response_format="verbose_json",
            )
        text = result.text.strip()
        print(f"[OK] NVIDIA Whisper: {len(text)} chars", file=sys.stderr)
        return text
    except Exception as e:
        print(f"[WARN] NVIDIA Whisper failed (gRPC-only, 跳過): {str(e)[:80]}", file=sys.stderr)
        return None


def _transcribe_local(audio_path: str, language: str = "zh") -> str | None:
    """Step 3: 本地 faster-whisper（small, int8，RPi CPU 慢但零依賴）。"""
    try:
        # ⚠️ Docker 中 /root/.cache 無寫入權限 → 模型快取改放 /opt/data
        os.environ.setdefault("HF_HOME", "/opt/data/.cache/huggingface")
        os.environ.setdefault("HF_HUB_CACHE", "/opt/data/.cache/huggingface/hub")
        os.makedirs("/opt/data/.cache/huggingface", exist_ok=True)
        from faster_whisper import WhisperModel
        print("[INFO] Local faster-whisper (small, CPU)...", file=sys.stderr)
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language=language)
        text = "".join(s.text for s in segments).strip()
        print(f"[OK] Local faster-whisper: {len(text)} chars", file=sys.stderr)
        return text
    except Exception as e:
        print(f"[ERROR] Local faster-whisper failed: {e}", file=sys.stderr)
        return None


def transcribe_audio(audio_path: str, language: str = "zh") -> str | None:
    """Whisper fallback chain: Groq → NVIDIA → 本地 faster-whisper.

    2026-07-31 使用者指示：先用 Groq，fallback NVIDIA，最後本地。
    """
    if not os.path.exists(audio_path):
        print(f"[ERROR] Audio file not found: {audio_path}", file=sys.stderr)
        return None

    # Step 1: Groq（>10MB 先壓縮成 opus 32k）
    work_path = audio_path
    if os.path.getsize(audio_path) > 10 * 1024 * 1024:
        work_path = _compress_to_opus(audio_path)
    text = _transcribe_groq(work_path, language)
    if text:
        return text

    # Step 2: NVIDIA
    text = _transcribe_nvidia(audio_path, language)
    if text:
        return text

    # Step 3: 本地 faster-whisper
    return _transcribe_local(audio_path, language)
