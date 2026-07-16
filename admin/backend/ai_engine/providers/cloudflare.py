import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

CLOUDFLARE_MODELS = [
    {"id": "@cf/meta/llama-3.1-8b-instruct-fp8", "name": "Llama 3.1 8B FP8", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/meta/llama-3.3-70b-instruct-fp16", "name": "Llama 3.3 70B FP16", "quality": "molto alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/qwen/qwen1.5-14b-chat-awq", "name": "Qwen 1.5 14B", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/microsoft/phi-2", "name": "Phi-2", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
]


def _cloudflare_key(uid=None):
    if uid:
        k = _get_user_api_key(uid, "cloudflare")
        if k:
            return k
    return os.environ.get("CLOUDFLARE_API_TOKEN", "")


def _cloudflare_account_id():
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")


def _cloudflare_generate(messages, model, uid=None):
    import requests
    key = _cloudflare_key(uid)
    account_id = _cloudflare_account_id()
    if not key or not account_id:
        logger.error("Cloudflare API token or Account ID not set")
        return None
    try:
        resp = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Cloudflare error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Cloudflare request failed: {e}")
        return None


def _cloudflare_generate_stream(messages, model, uid=None):
    from ai_engine.streaming import _stream_openai_compatible
    key = _cloudflare_key(uid)
    account_id = _cloudflare_account_id()
    if not key or not account_id:
        return
    yield from _stream_openai_compatible(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "cloudflare",
    "name": "Cloudflare Workers AI",
    "description": "Modelli gratuiti via Cloudflare Workers. Richiede Account ID e API Token.",
    "models": CLOUDFLARE_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_cloudflare_key()) and bool(_cloudflare_account_id()),
    "free": True,
    "website": "https://developers.cloudflare.com/workers-ai",
    "generate": _cloudflare_generate,
    "generate_stream": _cloudflare_generate_stream,
    "default_model": "@cf/meta/llama-3.1-8b-instruct-fp8",
})
