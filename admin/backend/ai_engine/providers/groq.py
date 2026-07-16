import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)

GROQ_MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile", "quality": "molto alta", "costo": "gratuito"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "quality": "alta", "costo": "gratuito"},
    {"id": "qwen/qwen3-32b", "name": "Qwen 3 32B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout 17B", "quality": "molto alta", "costo": "gratuito"},
]


def _groq_key(user_id=None):
    from ai_engine.config import _chat_key_rotator
    if user_id:
        k = _get_user_api_key(user_id, "groq")
        if k:
            return k
    return _chat_key_rotator.get_key() or os.environ.get("GROQ_API_KEY", "")


def _groq_generate(messages, model, user_id=None):
    import requests
    from ai_engine.config import _chat_key_rotator
    max_attempts = len(_chat_key_rotator.keys) if _chat_key_rotator.keys else 1

    for attempt in range(max_attempts):
        key = _groq_key(user_id)
        if not key:
            logger.error("Groq API key not set")
            return None

        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
                timeout=60
            )
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                _chat_key_rotator.report_success(key)
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                _chat_key_rotator.report_failure(key, retry_after=30)
                logger.warning(f"Groq rate limited on attempt {attempt + 1}, trying next key...")
                continue
            elif resp.status_code == 401:
                _chat_key_rotator.report_failure(key, retry_after=9999)
                logger.warning(f"Groq invalid key (401) on attempt {attempt + 1}, trying next key...")
                continue
            else:
                logger.error(f"Groq error: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Groq request failed: {e}")
            return None

    logger.error("All Groq keys exhausted")
    return None


def _groq_generate_stream(messages, model, user_id=None):
    import requests
    from ai_engine.config import _chat_key_rotator
    from ai_engine.streaming import _stream_openai_compatible
    max_attempts = len(_chat_key_rotator.keys) if _chat_key_rotator.keys else 1

    for attempt in range(max_attempts):
        key = _groq_key(user_id)
        if not key:
            return

        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages[:1], "temperature": 0.9, "max_tokens": 10},
                timeout=10
            )

            if resp.status_code == 429:
                _chat_key_rotator.report_failure(key, retry_after=30)
                logger.warning(f"Groq streaming rate limited on attempt {attempt + 1}, trying next key...")
                continue
            elif resp.status_code == 401:
                _chat_key_rotator.report_failure(key, retry_after=9999)
                logger.warning(f"Groq streaming invalid key (401) on attempt {attempt + 1}, trying next key...")
                continue
            elif resp.status_code == 200:
                _chat_key_rotator.report_success(key)
                yield from _stream_openai_compatible(
                    "https://api.groq.com/openai/v1/chat/completions",
                    {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    {"messages": messages, "temperature": 0.9, "max_tokens": 200},
                    model
                )
                return
            else:
                continue
        except Exception as e:
            logger.error(f"Groq streaming test failed: {e}")
            continue

    logger.error("All Groq keys exhausted for streaming")


register_provider({
    "id": "groq",
    "name": "Groq (API gratuita)",
    "description": "Inferenza ultraveloce gratuita. Supporta modelli open-source come Mixtral, Llama 3, Gemma. Richiede API key gratuita.",
    "models": GROQ_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_groq_key()),
    "free": True,
    "website": "https://console.groq.com",
    "generate": _groq_generate,
    "generate_stream": _groq_generate_stream,
    "default_model": "llama-3.3-70b-versatile",
})
