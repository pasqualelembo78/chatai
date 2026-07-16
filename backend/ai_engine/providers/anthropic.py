import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

ANTHROPIC_MODELS = [
    {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet", "quality": "molto alta", "costo": "$3/1M token"},
    {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "quality": "alta", "costo": "$0.25/1M token"},
]


def _anthropic_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "anthropic")
        if k:
            return k
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _anthropic_generate(messages, model, user_id=None):
    import requests
    key = _anthropic_key(user_id)
    if not key:
        logger.error("Anthropic API key not set")
        return None

    system = ""
    chat = []
    for m in messages:
        if m["role"] == "system":
            system += m["content"] + "\n"
        else:
            chat.append({"role": m["role"], "content": m["content"]})

    try:
        body = {
            "model": model,
            "max_tokens": 200,
            "messages": chat,
        }
        if system.strip():
            body["system"] = system.strip()

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"]
        logger.error(f"Anthropic error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"Anthropic request failed: {e}")
        return None


register_provider({
    "id": "anthropic",
    "name": "Anthropic Claude (API)",
    "description": "Modelli Claude di Anthropic. Eccellenti per roleplay e conversazione naturale.",
    "models": ANTHROPIC_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_anthropic_key()),
    "free": False,
    "website": "https://console.anthropic.com",
    "generate": _anthropic_generate,
    "generate_stream": lambda msgs, model, user_id=None: _gen_stream(msgs, model, user_id),
    "default_model": "claude-3-5-sonnet-20240620",
})


def _gen_stream(messages, model, user_id=None):
    from ai_engine.streaming import _anthropic_generate_stream
    return _anthropic_generate_stream(messages, model, user_id=user_id)
