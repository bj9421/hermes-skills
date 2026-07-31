# NVIDIA Whisper gRPC 調用（build.nvidia.com whisper-large-v3）

> 2026-07-31 實測驗證成功。NVIDIA 的 Whisper **沒有 OpenAI 相容 HTTP endpoint**
> （integrate.api.nvidia.com / ai.api.nvidia.com 都 404）——託管版唯一方式是 gRPC。
> 已實作於 `notehub/core/transcribe.py` 的 `_transcribe_nvidia()`。

## 關鍵參數

| 項目 | 值 |
|------|-----|
| server | `grpc.nvcf.nvidia.com:443` |
| function-id | `b702f636-f60c-4a3d-a6f4-f3568c13bd7d`（whisper-large-v3 固定） |
| 認證 | metadata `authorization: Bearer $NVIDIA_API_KEY` |
| 依賴 | `nvidia-riva-client`（pip 安裝；注意會 downgrade protobuf 到 6.x） |

## 完整呼叫範例（實測可用）

```python
import riva.client, subprocess, tempfile

# 1. 音訊轉 wav 16-bit mono 16kHz（Riva 要求）
wav_path = '/tmp/audio.wav'
subprocess.run(['ffmpeg', '-y', '-i', audio_path, '-ac', '1', '-ar', '16000',
                '-sample_fmt', 's16', wav_path], capture_output=True, timeout=120)

# 2. gRPC 認證 + service
auth = riva.client.Auth(
    use_ssl=True,
    uri='grpc.nvcf.nvidia.com:443',
    metadata_args=[
        ['function-id', 'b702f636-f60c-4a3d-a6f4-f3568c13bd7d'],
        ['authorization', f'Bearer {nvidia_key}'],
    ],
)
service = riva.client.ASRService(auth)

# 3. config + 轉寫
config = riva.client.RecognitionConfig(
    language_code='zh', max_alternatives=1,
    enable_automatic_punctuation=True,
)
riva.client.add_custom_configuration_to_config(config, 'task:transcribe')
with open(wav_path, 'rb') as f:
    data = f.read()  # 🔴 讀整個檔（含 header）！勿用 wave.readframes()
resp = service.offline_recognize(data, config)

# 4. 🔴 結果欄位是 transcript（不是 text！）
texts = [a.transcript for r in resp.results for a in r.alternatives]
text = ''.join(texts).strip()
```

## 踩過的坑（按順序）

1. **HTTP endpoint 404**：`integrate.api.nvidia.com/v1/audio/transcriptions` 與 `ai.api.nvidia.com` 都 404 → 只有 gRPC
2. **`INVALID_ARGUMENT: encoding not specified`**：raw PCM bytes（wave.readframes）需設 `encoding=1`(LINEAR_PCM) + `sample_rate_hertz`；**或直接讀整個 wav 檔（含 header）讓 Riva 自動偵測**
3. **轉寫結果空字串 / `AttributeError: is_final`**：結果欄位是 `alternatives[].transcript`，不是常見的 `text`。`resp.results[0]` 只有 `channel_tag` + `audio_processed` 是「處理成功但無文字」的假象
4. **`language_code='cmn-Hant-TW'` 等長格式會 INVALID_ARGUMENT**：用 `'zh'` 或 `'multi'`（自動偵測）
5. **custom configuration 必要**：`add_custom_configuration_to_config(config, 'task:transcribe')` 不加可能空結果

## 驗證數據

- 5.95s 音訊 → 40 chars 轉寫成功（「这是第二段测试,验证NVIDIA Whisper Fallback是否正常运作。」）
- NVIDIA Whisper 對 zh 輸出**簡體** → 後續 opencc `_convert_to_traditional()` 轉繁體

## 其他 NVIDIA speech 模型（若需替換 function-id）

- streaming: `1598d209-5e27-4d3c-8079-4751568b1081`（transcribe_file.py，即時）
- TTS: `0149dedb-2be8-4195-b9a0-e57e0e14f972`（talk.py）
- 各模型 function-id 從 build.nvidia.com 模型頁「Try API」取得
