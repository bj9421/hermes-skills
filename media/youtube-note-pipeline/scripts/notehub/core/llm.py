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


def call_llm(messages: list[dict], max_tokens: int = 4096,
             temperature: float = 0.3, model_override: str = None) -> str | None:
    """Call LLM with rate limiting, retry, and fallback.

    Args:
        messages: Chat messages (role + content)
        max_tokens: Max response tokens
        temperature: Sampling temperature
        model_override: Force a specific model (bypass fallback)

    Returns:
        Response text or None on failure.
    """
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
