"""LLM calling module — rate limiter, retry, and multi-model fallback.

Uses NVIDIA API (OpenAI-compatible) with:
- 2s minimum interval between calls (40 RPM free tier)
- 3-retry exponential backoff per model
- 3-model fallback chain: deepseek-v4-flash → llama-3.3-70b → nemotron-70b
"""

import os
import sys
import time

# Rate limiter
_last_api_call = 0.0
_API_INTERVAL = 2.0

# Config
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
FALLBACK_MODELS = [
    "deepseek-ai/deepseek-v4-flash",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
]


def _rate_limit():
    """Enforce minimum interval between API calls."""
    global _last_api_call
    elapsed = time.time() - _last_api_call
    if elapsed < _API_INTERVAL:
        time.sleep(_API_INTERVAL - elapsed)
    _last_api_call = time.time()


def get_client():
    """Create OpenAI-compatible client pointing at NVIDIA API."""
    api_key = NVIDIA_API_KEY
    if not api_key:
        env_path = "/opt/data/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NVIDIA_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not api_key:
        return None

    from openai import OpenAI
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def call_agnes(messages: list[dict], max_tokens: int = 4096,
               temperature: float = 0.3) -> str | None:
    """呼叫 AGNES API（agnes-2.0-flash）。

    當 OpenCode Zen 限流時的 fallback provider。
    """
    import http.client
    import json
    import os

    key = os.environ.get('AGNES_API_KEY', '')
    if not key:
        # 從 .env 讀取
        try:
            with open('/opt/data/.env') as f:
                for line in f:
                    if line.startswith('AGNES_API_KEY='):
                        key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
        except:
            pass

    if not key:
        print("[WARN] AGNES_API_KEY not found", file=sys.stderr)
        return None

    payload = {
        'model': 'agnes-2.0-flash',
        'messages': messages,
        'temperature': temperature,
    }
    if max_tokens and max_tokens > 0:
        payload['max_tokens'] = max_tokens
    body = json.dumps(payload, ensure_ascii=False)
    try:
        conn = http.client.HTTPSConnection('apihub.agnes-ai.com', timeout=45)
        conn.request('POST', '/v1/chat/completions', body.encode('utf-8'),
                     {'Content-Type': 'application/json',
                      'Authorization': f'Bearer {key}'})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8'))
        conn.close()
        if resp.status == 200:
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return content.strip() if content else None
        print(f"[WARN] AGNES API HTTP {resp.status}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[WARN] AGNES API failed: {e}", file=sys.stderr)
        return None


def call_zen(messages: list[dict], max_tokens: int = 0,
             temperature: float = 0.3) -> str | None:
    """呼叫 OpenCode Zen（deepseek-v4-flash-free，免費免 Key）。

    這是 bookmark-manager 每天在用的穩定免費模型（opencode.ai/zen/v1）。
    失敗回傳 None，由呼叫方決定是否 fallback。

    ⚠️ 注意：deepseek-v4-flash 是 reasoning 模型，輸出在 reasoning_content。
    不要傳 max_tokens（或傳 0）——設了會被思考過程吃光導致 content 空。
    """
    import http.client
    import json

    payload = {
        'model': 'deepseek-v4-flash-free',
        'messages': messages,
        'temperature': temperature,
    }
    if max_tokens and max_tokens > 0:
        payload['max_tokens'] = max_tokens
    body = json.dumps(payload, ensure_ascii=False)
    try:
        conn = http.client.HTTPSConnection('opencode.ai', timeout=45)
        conn.request('POST', '/zen/v1/chat/completions', body.encode('utf-8'),
                     {'Content-Type': 'application/json'})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8'))
        conn.close()
        if resp.status == 200:
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return content.strip() if content else None
        print(f"[WARN] Zen LLM HTTP {resp.status}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[WARN] Zen LLM failed: {e}", file=sys.stderr)
        return None


def call_llm(messages: list[dict], max_tokens: int = 4096,
             temperature: float = 0.3, model_override: str = None) -> str | None:
    """Call LLM — **只走 OpenCode Zen**（免費穩定）。

    ⚠️ 2026-07-31 使用者明確指示：**NVIDIA 在 pipeline 只負責 Whisper 轉寫，
    LLM 整理文檔（口播腳本/標題翻譯）一律不用 NVIDIA 模型**。
    Zen 失敗直接回 None（job 標 failed 比卡死好——NVIDIA 曾無 timeout 卡 10+ 分鐘）。

    Args:
        messages: Chat messages (role + content)
        max_tokens: Max response tokens
        temperature: Sampling temperature
        model_override: 保留簽名相容，不再使用

    Returns:
        Response text or None on failure.
    """
    zen_result = call_zen(messages, max_tokens, temperature)
    if zen_result:
        return zen_result
    # Zen 限流時 fallback 到 AGNES API
    print("[INFO] Zen LLM unavailable, falling back to AGNES API...", file=sys.stderr)
    agnes_result = call_agnes(messages, max_tokens, temperature)
    if agnes_result:
        print("[OK] AGNES API fallback successful", file=sys.stderr)
        return agnes_result
    print("[WARN] AGNES API also failed — job will be marked as failed", file=sys.stderr)
    return None
