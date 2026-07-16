import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

GITHUB_MODELS = [
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "quality": "alta", "costo": "gratuito"},
    {"id": "gpt-4o", "name": "GPT-4o", "quality": "molto alta", "costo": "gratuito"},
    {"id": "Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B Instruct", "quality": "molto alta", "costo": "gratuito"},
    {"id": "DeepSeek-R1", "name": "DeepSeek R1", "quality": "molto alta", "costo": "gratuito"},
]


def _github_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "github")
        if k:
            return k
    return os.environ.get("GITHUB_TOKEN", "")


def _github_generate(messages, model, user_id=None):
    import requests
    key = _github_key(user_id)
    if not key:
        logger.error("GitHub token not set")
        return None
    try:
        resp = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"GitHub Models error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"GitHub Models request failed: {e}")
        return None


def _github_generate_stream(messages, model, user_id=None):
    from ai_engine.streaming import _stream_openai_compatible
    key = _github_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://models.inference.ai.azure.com/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "github",
    "name": "GitHub Models (Azure AI)",
    "description": "Modelli gratuiti via GitHub. Richiede un personal access token GitHub (gratuito).",
    "models": GITHUB_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_github_key()),
    "free": True,
    "website": "https://github.com/marketplace/models",
    "generate": _github_generate,
    "generate_stream": _github_generate_stream,
    "default_model": "gpt-4o-mini",
})
