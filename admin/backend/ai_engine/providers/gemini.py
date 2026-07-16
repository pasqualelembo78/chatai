import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "quality": "molto alta", "costo": "free tier"},
    {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "quality": "alta", "costo": "free tier"},
    {"id": "gemini-2.5-flash-preview-09-2025", "name": "Gemini 2.5 Flash Preview", "quality": "molto alta", "costo": "free tier"},
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "quality": "alta", "costo": "free tier + a pagamento"},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "quality": "molto alta", "costo": "free tier + a pagamento"},
]


def _gemini_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "gemini")
        if k:
            return k
    return os.environ.get("GEMINI_API_KEY", "")


def _gemini_generate(messages, model, user_id=None):
    import requests
    key = _gemini_key(user_id)
    if not key:
        logger.error("Gemini API key not set")
        return None

    system = ""
    chat = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        elif m["role"] == "user":
            chat.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            chat.append({"role": "model", "parts": [{"text": m["content"]}]})

    try:
        body = {
            "contents": chat,
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}

        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            json=body,
            timeout=60
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            candidates = resp.json().get("candidates", [])
            if candidates:
                return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        logger.error(f"Gemini error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"Gemini request failed: {e}")
        return None


register_provider({
    "id": "gemini",
    "name": "Google Gemini (API)",
    "description": "Modelli Gemini di Google. Include un tier gratuito molto generoso. Ottima qualità.",
    "models": GEMINI_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_gemini_key()),
    "free": True,
    "website": "https://ai.google.dev",
    "generate": _gemini_generate,
    "generate_stream": lambda msgs, model, user_id=None: _gen_stream(msgs, model, user_id),
    "default_model": "gemini-2.0-flash",
})


def _gen_stream(messages, model, user_id=None):
    from ai_engine.streaming import _gemini_generate_stream
    return _gemini_generate_stream(messages, model, user_id=user_id)
