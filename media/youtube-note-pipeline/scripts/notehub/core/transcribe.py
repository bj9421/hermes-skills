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
    """m4a → opus 32k（Groq 413 fix：>10MB 會被拒，14MB m4a → ~4.5MB opus）。

    ⚠️ 2026-07-31：RPi CPU 壓大檔很慢，timeout 要給足（60s 會失敗）。
    34.5MB m4a（~40 分鐘音訊）→ opus 32k ≈ 9.6MB < 10MB ✅
    """
    opus_path = path.rsplit(".", 1)[0] + ".opus"
    size = os.path.getsize(path)
    print(f"[INFO] Audio {size/1024/1024:.1f}MB exceeds Groq limit, compressing...", file=sys.stderr)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-c:a", "libopus", "-b:a", "32k", opus_path],
            capture_output=True, text=True, timeout=300,
        )
        if os.path.exists(opus_path):
            print(f"[INFO] Compressed: {os.path.getsize(opus_path)/1024/1024:.1f}MB", file=sys.stderr)
            return opus_path
    except Exception as e:
        print(f"[WARN] Compression failed: {e}", file=sys.stderr)
    print("[WARN] Compression failed, using original file", file=sys.stderr)
    return path


def _segment_audio(path: str, target_mb: float = 9.0) -> list:
    """ffmpeg 無損分段（-c copy，不轉碼超快），動態依檔案大小算段數。

    ⚠️ 2026-07-31：RPi 壓縮大檔慢，改採**分段策略**。固定 10 分鐘/段對
    高碼率影片會 >10MB（實測 33MB 影片 10 分鐘段 = 16MB），所以：
    - ffprobe 拿總時長 → 段數 = ceil(大小/目標9MB) → segment_time = 時長/段數
    確保每段 < 10MB（Groq 413 上限）。
    """
    import glob
    import json
    import math
    import tempfile

    size_mb = os.path.getsize(path) / (1024 * 1024)
    # 拿總時長
    duration = 0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(json.loads(r.stdout)["format"]["duration"])
    except Exception as e:
        print(f"[WARN] ffprobe failed: {e}", file=sys.stderr)
    n = max(1, math.ceil(size_mb / target_mb))
    segment_seconds = max(60, int(duration / n)) if duration else 600
    print(f"[INFO] Segment: {size_mb:.0f}MB/{duration:.0f}s → {n} 段, {segment_seconds}s/段", file=sys.stderr)

    seg_dir = tempfile.mkdtemp(prefix="seg_")
    out_pattern = os.path.join(seg_dir, "seg_%03d.m4a")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-f", "segment",
             "-segment_time", str(segment_seconds), "-c", "copy", out_pattern],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        print(f"[WARN] ffmpeg segment failed: {e}", file=sys.stderr)
        return []
    segs = sorted(glob.glob(os.path.join(seg_dir, "seg_*.m4a")))
    if not segs:
        print("[WARN] ffmpeg segment produced no files", file=sys.stderr)
    return segs


def _groq_single(client, audio_path: str, language: str) -> str | None:
    """單檔 Groq 轉寫（<10MB）。"""
    try:
        with open(audio_path, "rb") as f:
            ext = os.path.splitext(audio_path)[1] or ".m4a"
            result = client.audio.transcriptions.create(
                file=(f"audio{ext}", f),
                model="whisper-large-v3",
                language=language,
                response_format="verbose_json",
            )
        return result.text.strip()
    except Exception as e:
        print(f"[WARN] Groq single failed: {str(e)[:80]}", file=sys.stderr)
        return None


def _transcribe_groq(audio_path: str, language: str = "zh") -> str | None:
    """Step 1: Groq Whisper（whisper-large-v3，免費快速）。

    >10MB 自動**分段轉寫合併**（2026-07-31）：ffmpeg -c copy 切 10 分鐘段
    → 逐段 Groq → 合併文字。避免 413 Request Entity Too Large。
    """
    groq_key = _load_key("GROQ_API_KEY")
    if not groq_key:
        print("[ERROR] GROQ_API_KEY not found in /opt/data/.env", file=sys.stderr)
        return None
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
    except Exception as e:
        print(f"[ERROR] Groq client init failed: {e}", file=sys.stderr)
        return None

    # 大檔：分段轉寫
    if os.path.getsize(audio_path) > 10 * 1024 * 1024:
        segs = _segment_audio(audio_path)
        if segs:
            texts = []
            for i, seg in enumerate(segs):
                if os.path.getsize(seg) > 10 * 1024 * 1024:
                    print(f"[WARN] Groq seg {i+1} still {os.path.getsize(seg)/1048576:.0f}MB — skip", file=sys.stderr)
                    continue
                t = _groq_single(client, seg, language)
                if t:
                    texts.append(t)
                    print(f"[OK] Groq seg {i+1}/{len(segs)}: {len(t)} chars", file=sys.stderr)
            if texts:
                merged = "\n".join(texts)
                print(f"[OK] Groq Whisper (segmented): {len(merged)} chars total", file=sys.stderr)
                return merged
            print("[WARN] 分段轉寫全失敗 — fallback NVIDIA/本地", file=sys.stderr)
            return None
        # 分段失敗 → 嘗試壓縮（壓縮後仍大就放棄 Groq）
        work = _compress_to_opus(audio_path)
        if os.path.getsize(work) <= 10 * 1024 * 1024:
            t = _groq_single(client, work, language)
            if t:
                return t
        return None

    # 小檔：直接轉寫
    text = _groq_single(client, audio_path, language)
    if text:
        print(f"[OK] Groq Whisper: {len(text)} chars", file=sys.stderr)
        return text
    return None


def _transcribe_nvidia(audio_path: str, language: str = "zh") -> str | None:
    """Step 2: NVIDIA Whisper（build.nvidia.com gRPC，whisper-large-v3）。

    ✅ 2026-07-31 實測成功：
    - server: grpc.nvcf.nvidia.com:443
    - function-id: b702f636-f60c-4a3d-a6f4-f3568c13bd7d（whisper-large-v3 固定）
    - 音訊需轉 wav 16-bit mono 16kHz，讀整個檔（含 header，勿用 wave.readframes）
    - config 加 custom_configuration 'task:transcribe'
    - 結果欄位是 alternatives[].transcript（不是 text！）
    """
    nvidia_key = _load_key("NVIDIA_API_KEY")
    if not nvidia_key:
        print("[ERROR] NVIDIA_API_KEY not found in /opt/data/.env", file=sys.stderr)
        return None
    wav_path = None
    try:
        import subprocess
        import tempfile
        import riva.client

        # 轉 wav 16-bit mono 16kHz（Riva 需要）
        wav_path = None
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "16000",
                 "-sample_fmt", "s16", wav_path],
                capture_output=True, text=True, timeout=120,
            )
        except Exception as e:
            print(f"[WARN] NVIDIA Whisper: ffmpeg convert failed: {e}", file=sys.stderr)
            return None

        auth = riva.client.Auth(
            use_ssl=True,
            uri="grpc.nvcf.nvidia.com:443",
            metadata_args=[
                ["function-id", "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"],
                ["authorization", f"Bearer {nvidia_key}"],
            ],
        )
        service = riva.client.ASRService(auth)
        config = riva.client.RecognitionConfig(
            language_code=language, max_alternatives=1,
            enable_automatic_punctuation=True,
        )
        riva.client.add_custom_configuration_to_config(config, "task:transcribe")
        with open(wav_path, "rb") as f:
            data = f.read()
        resp = service.offline_recognize(data, config)
        texts = [a.transcript for r in resp.results for a in r.alternatives]
        text = "".join(texts).strip()
        if text:
            print(f"[OK] NVIDIA Whisper: {len(text)} chars", file=sys.stderr)
            return text
        print("[WARN] NVIDIA Whisper returned empty", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[WARN] NVIDIA Whisper failed: {str(e)[:100]}", file=sys.stderr)
        return None
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


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

    # Step 1: Groq（>10MB 自動分段轉寫合併，見 _transcribe_groq）
    text = _transcribe_groq(audio_path, language)
    if text:
        return text

    # Step 2: NVIDIA
    text = _transcribe_nvidia(audio_path, language)
    if text:
        return text

    # Step 3: 本地 faster-whisper
    return _transcribe_local(audio_path, language)
