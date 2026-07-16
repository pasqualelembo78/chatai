import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "quality": "molto alta", "costo": "$5/1M token"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "quality": "alta", "costo": "$0.15/1M token"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "quality": "molto alta", "costo": "$10/1M token"},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "quality": "alta", "costo": "$0.5/1M token"},
]


def _openai_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "openai")
        if k:
            return k
    return os.environ.get("OPENAI_API_KEY", "")


def _openai_generate(messages, model, user_id=None):
    import requests
    key = _openai_key(user_id)
    if not key:
        logger.error("OpenAI API key not set")
        return None
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"OpenAI error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        return None


def _openai_generate_stream(messages, model, user_id=None):
    from ai_engine.streaming import _stream_openai_compatible
    key = _openai_key(user_id)
    if not key:
        logger.error("OpenAI API key not set")
        return
    yield from _stream_openai_compatible(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "openai",
    "name": "OpenAI (API)",
    "description": "Modelli GPT di OpenAI. Qualità eccellente. È necessaria una chiave API (apikey).",
    "models": OPENAI_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_openai_key()),
    "free": False,
    "website": "https://platform.openai.com",
    "generate": _openai_generate,
    "generate_stream": _openai_generate_stream,
    "default_model": "gpt-4o-mini",
})
