import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

MISTRAL_MODELS = [
    {"id": "mistral-small-latest", "name": "Mistral Small", "quality": "alta", "costo": "free tier"},
    {"id": "open-mistral-7b", "name": "Open Mistral 7B", "quality": "alta", "costo": "gratuito"},
    {"id": "open-mixtral-8x7b", "name": "Open Mixtral 8x7B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "codestral-latest", "name": "Codestral", "quality": "molto alta", "costo": "free tier"},
]


def _mistral_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "mistral")
        if k:
            return k
    return os.environ.get("MISTRAL_API_KEY", "")


def _mistral_generate(messages, model, user_id=None):
    import requests
    key = _mistral_key(user_id)
    if not key:
        logger.error("Mistral API key not set")
        return None
    try:
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Mistral error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Mistral request failed: {e}")
        return None


def _mistral_generate_stream(messages, model, user_id=None):
    from ai_engine.streaming import _stream_openai_compatible
    key = _mistral_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://api.mistral.ai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "mistral",
    "name": "Mistral AI (API)",
    "description": "Modelli Mistral AI con free tier generoso. Richiede chiave API Mistral (gratuita su console.mistral.ai).",
    "models": MISTRAL_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_mistral_key()),
    "free": True,
    "website": "https://console.mistral.ai",
    "generate": _mistral_generate,
    "generate_stream": _mistral_generate_stream,
    "default_model": "mistral-small-latest",
})
