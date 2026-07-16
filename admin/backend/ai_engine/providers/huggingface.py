import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key
from ai_engine.streaming import _stream_wrapper

logger = logging.getLogger(__name__)

HUGGINGFACE_MODELS = [
    {"id": "openai/gpt-oss-120b:fastest", "name": "GPT-OSS 120B", "quality": "molto alta", "costo": "free tier"},
    {"id": "meta-llama/Llama-3.1-8B-Instruct:fastest", "name": "Llama 3.1 8B Instruct", "quality": "alta", "costo": "free tier"},
    {"id": "Qwen/Qwen3-8B:fastest", "name": "Qwen3 8B", "quality": "alta", "costo": "free tier"},
    {"id": "Qwen/Qwen2.5-7B-Instruct:fastest", "name": "Qwen2.5 7B Instruct", "quality": "buona", "costo": "free tier"},
]


def _huggingface_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "huggingface")
        if k:
            return k
    return os.environ.get("HUGGINGFACE_API_KEY", "")


def _huggingface_generate(messages, model, user_id=None):
    import requests
    key = _huggingface_key(user_id)
    if not key:
        logger.error("HuggingFace API key not set")
        return None
    try:
        resp = requests.post(
            "https://router.huggingface.co/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "max_tokens": 500, "temperature": 0.9},
            timeout=120
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0].get("message", {}).get("content", "")
        logger.error(f"HuggingFace error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"HuggingFace request failed: {e}")
        return None


register_provider({
    "id": "huggingface",
    "name": "Hugging Face (Inference API)",
    "description": "Modelli open-source gratuiti via Inference API. Richiede chiave API Hugging Face (gratuita).",
    "models": HUGGINGFACE_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_huggingface_key()),
    "free": True,
    "website": "https://huggingface.co/inference-api",
    "generate": _huggingface_generate,
    "generate_stream": _stream_wrapper(_huggingface_generate),
    "default_model": "openai/gpt-oss-120b:fastest",
})
