import os
import logging

from ai_engine.registry import register_provider

logger = logging.getLogger(__name__)

LLAMACPP_MODELS = [
    {"id": "local", "name": "Modello locale", "quality": "dipende dal modello", "costo": "gratuito"},
]


def _llamacpp_key(uid=None):
    return os.environ.get("LLAMACPP_API_KEY", "")


def _llamacpp_available():
    import requests
    try:
        resp = requests.get("http://localhost:8080/v1/models", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _llamacpp_generate(messages, model, uid=None):
    import requests
    if not _llamacpp_available():
        logger.error("llama.cpp non disponibile su localhost:8080")
        return None
    try:
        key = _llamacpp_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        server_model = model if model and model != "local" else os.environ.get("LLAMACPP_MODEL", "local-model")
        resp = requests.post(
            "http://localhost:8080/v1/chat/completions",
            headers=headers,
            json={
                "model": server_model,
                "messages": messages,
                "temperature": float(os.environ.get("LLAMACPP_TEMP", "0.8")),
                "max_tokens": int(os.environ.get("LLAMACPP_MAX_TOKENS", "512")),
            },
            timeout=120
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"llama.cpp error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"llama.cpp request failed: {e}")
        return None


def _llamacpp_generate_stream(messages, model, uid=None):
    from ai_engine.streaming import _stream_openai_compatible
    if not _llamacpp_available():
        return
    key = _llamacpp_key()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    server_model = model if model and model != "local" else os.environ.get("LLAMACPP_MODEL", "local-model")
    yield from _stream_openai_compatible(
        "http://localhost:8080/v1/chat/completions",
        headers,
        {"messages": messages, "temperature": float(os.environ.get("LLAMACPP_TEMP", "0.8")), "max_tokens": int(os.environ.get("LLAMACPP_MAX_TOKENS", "512"))},
        server_model
    )


register_provider({
    "id": "llamacpp",
    "name": "llama.cpp (Locale)",
    "description": "Server locale llama.cpp. Esegui modelli GGUF su localhost:8080. Nessuna API key richiesta.",
    "models": LLAMACPP_MODELS,
    "needs_key": False,
    "has_key": lambda: _llamacpp_available(),
    "free": True,
    "website": "https://github.com/ggerganov/llama.cpp",
    "generate": _llamacpp_generate,
    "generate_stream": _llamacpp_generate_stream,
    "default_model": "local",
    "available": _llamacpp_available,
})
