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
    """Call LLM with rate limiting, retry, and fallback.

    ⚠️ 2026-07-31 使用者指示：口播腳本用免費穩定模型。
    優先 OpenCode Zen（deepseek-v4-flash-free，免費免 Key），
    失敗才 fallback 到 NVIDIA API 鏈。

    Args:
        messages: Chat messages (role + content)
        max_tokens: Max response tokens
        temperature: Sampling temperature
        model_override: Force a specific model (bypass fallback)

    Returns:
        Response text or None on failure.
    """
    # 優先：OpenCode Zen（免費、穩定、bookmark-manager 每日驗證）
    zen_result = call_zen(messages, max_tokens, temperature)
    if zen_result:
        return zen_result
    print("[WARN] Zen LLM unavailable — falling back to NVIDIA chain", file=sys.stderr)

    client = get_client()
    if not client:
        print("[ERROR] No NVIDIA API key available", file=sys.stderr)
        return None

    models = [model_override] if model_override else FALLBACK_MODELS
    max_retries = 3
    base_delay = 3.0

    for model in models:
        for attempt in range(max_retries):
            _rate_limit()
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=45,  # ⚠️ 2026-07-31：無 timeout 會卡死（SDK 預設 600s×重試），實測 job 12 卡 10+ 分鐘
                )
                result = response.choices[0].message.content
                if result:
                    return result.strip()
                print(f"[WARN] LLM returned empty on {model}", file=sys.stderr)
                return None
            except Exception as e:
                err_str = str(e)
                is_rl = "503" in err_str or "ResourceExhausted" in err_str or "rate" in err_str.lower()
                if is_rl and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"[WARN] LLM {model} rate limited ({attempt+1}/{max_retries}), retry in {delay:.0f}s...", file=sys.stderr)
                    time.sleep(delay)
                elif is_rl:
                    print(f"[WARN] LLM {model} exhausted, trying next...", file=sys.stderr)
                    break
                else:
                    print(f"[ERROR] LLM {model}: {e}", file=sys.stderr)
                    return None

    print("[ERROR] All LLM models exhausted", file=sys.stderr)
    return None
