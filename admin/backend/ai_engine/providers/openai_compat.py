import os
import logging

from ai_engine.registry import register_provider, _get_user_api_key

logger = logging.getLogger(__name__)


def _make_openai_provider(pid, name, desc, base_url, env_key, models, free=True, website="", extra_headers=None):
    def _key(uid=None):
        if uid:
            k = _get_user_api_key(uid, pid)
            if k:
                return k
        return os.environ.get(env_key, "")

    def _generate(messages, model, uid=None):
        import requests
        key = _key(uid)
        if not key:
            logger.error(f"{name} API key not set")
            return None
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            if extra_headers:
                headers.update(extra_headers(key))
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
                timeout=60
            )
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.error(f"{name} error: {resp.status_code} {resp.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"{name} request failed: {e}")
            return None

    def _generate_stream(messages, model, uid=None):
        from ai_engine.streaming import _stream_openai_compatible
        key = _key(uid)
        if not key:
            return
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers(key))
        yield from _stream_openai_compatible(
            f"{base_url}/chat/completions",
            headers,
            {"messages": messages, "temperature": 0.9, "max_tokens": 200},
            model
        )

    return {
        "id": pid,
        "name": name,
        "description": desc,
        "models": models,
        "needs_key": True,
        "has_key": lambda: bool(_key()),
        "free": free,
        "website": website,
        "generate": _generate,
        "generate_stream": _generate_stream,
        "default_model": models[0]["id"] if models else "",
    }


# ─── Together AI ─────────────────────────────────────────────────
TOGETHER_MODELS = [
    {"id": "Qwen/Qwen3.5-9B", "name": "Qwen 3.5 9B", "quality": "alta", "costo": "gratuito (crediti iniziali)"},
    {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B Turbo", "quality": "molto alta", "costo": "da $0.88/1M"},
    {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3", "quality": "molto alta", "costo": "da $0.27/1M"},
    {"id": "Qwen/Qwen3-235B-A22B", "name": "Qwen 3 235B", "quality": "molto alta", "costo": "da $0.65/1M"},
    {"id": "mistralai/Mistral-Small-24B-Instruct-2501", "name": "Mistral Small 24B", "quality": "alta", "costo": "da $0.1/1M"},
]
register_provider(_make_openai_provider(
    "together", "Together AI", "API open-source con modelli Llama, Mistral, Qwen. Crediti gratuiti all'iscrizione.",
    "https://api.together.ai/v1", "TOGETHER_API_KEY", TOGETHER_MODELS,
    free=False, website="https://api.together.ai"
))


# ─── Cerebras ────────────────────────────────────────────────────
CEREBRAS_MODELS = [
    {"id": "zai-glm-4.7", "name": "ZAI GLM 4.7", "quality": "molto alta", "costo": "gratuito (30 RPM)"},
    {"id": "gpt-oss-120b", "name": "GPT-OSS 120B", "quality": "molto alta", "costo": "gratuito (30 RPM)"},
    {"id": "gemma-4-31b", "name": "Gemma 4 31B", "quality": "molto alta", "costo": "gratuito (30 RPM)"},
]
register_provider(_make_openai_provider(
    "cerebras", "Cerebras", "Inferenza ultraveloce con Cerebras. Modelli gratuiti con limite 30 RPM.",
    "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", CEREBRAS_MODELS,
    free=True, website="https://cloud.cerebras.ai"
))


# ─── Cohere ──────────────────────────────────────────────────────
COHERE_MODELS = [
    {"id": "command-a-plus-05-2026", "name": "Command A+ 2026", "quality": "molto alta", "costo": "gratuito (rate limited)"},
    {"id": "command-r", "name": "Command R", "quality": "alta", "costo": "gratuito (rate limited)"},
    {"id": "command-r-plus", "name": "Command R+", "quality": "molto alta", "costo": "gratuito (rate limited)"},
    {"id": "command-light", "name": "Command Light", "quality": "media", "costo": "gratuito (rate limited)"},
]
register_provider(_make_openai_provider(
    "cohere", "Cohere", "Modelli Cohere per NLP e chat. API key gratuita disponibile.",
    "https://api.cohere.com/compatibility/v1", "COHERE_API_KEY", COHERE_MODELS,
    free=True, website="https://cohere.com"
))


# ─── DeepInfra ──────────────────────────────────────────────────
DEEPINFRA_MODELS = [
    {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3", "quality": "molto alta", "costo": "da $0.14/1M"},
    {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B Turbo", "quality": "molto alta", "costo": "da $0.88/1M"},
    {"id": "Qwen/Qwen3-235B-A22B", "name": "Qwen 3 235B", "quality": "molto alta", "costo": "da $0.65/1M"},
    {"id": "mistralai/Mistral-Small-24B-Instruct-2501", "name": "Mistral Small 24B", "quality": "alta", "costo": "da $0.1/1M"},
]
register_provider(_make_openai_provider(
    "deepinfra", "DeepInfra", "API open-source con modelli vari. Crediti gratuiti all'iscrizione.",
    "https://api.deepinfra.com/v1/openai", "DEEPINFRA_API_KEY", DEEPINFRA_MODELS,
    free=False, website="https://deepinfra.com"
))


# ─── Fireworks AI ───────────────────────────────────────────────
FIREWORKS_MODELS = [
    {"id": "accounts/fireworks/models/deepseek-v3p1", "name": "DeepSeek V3.1", "quality": "molto alta", "costo": "da $0.27/1M"},
    {"id": "accounts/fireworks/models/llama-v3p3-70b-instruct", "name": "Llama 3.3 70B", "quality": "molto alta", "costo": "da $0.9/1M"},
    {"id": "accounts/fireworks/models/qwen3-235b-a22b", "name": "Qwen 3 235B", "quality": "molto alta", "costo": "da $0.65/1M"},
    {"id": "accounts/fireworks/models/mistral-small-24b-instruct-2501", "name": "Mistral Small 24B", "quality": "alta", "costo": "da $0.1/1M"},
]
register_provider(_make_openai_provider(
    "fireworks", "Fireworks AI", "API open-source con modelli vari. Crediti gratuiti all'iscrizione.",
    "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY", FIREWORKS_MODELS,
    free=False, website="https://fireworks.ai"
))


# ─── SambaNova Cloud ───────────────────────────────────────────
SAMBANOVA_MODELS = [
    {"id": "DeepSeek-V3.1", "name": "DeepSeek V3.1", "quality": "molto alta", "costo": "gratuito (rate limited)"},
    {"id": "Meta-Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B", "quality": "molto alta", "costo": "gratuito (rate limited)"},
    {"id": "Llama-4-Maverick-17B-128E-Instruct", "name": "Llama 4 Maverick 17B", "quality": "molto alta", "costo": "gratuito (rate limited)"},
    {"id": "QwQ-32B", "name": "QwQ 32B", "quality": "molto alta", "costo": "gratuito (rate limited)"},
]
register_provider(_make_openai_provider(
    "sambanova", "SambaNova Cloud", "Modelli open-source gratuiti con SambaNova. API key gratuita.",
    "https://api.sambanova.ai/v1", "SAMBANOVA_API_KEY", SAMBANOVA_MODELS,
    free=True, website="https://cloud.sambanova.ai"
))


# ─── Nebius AI Studio ──────────────────────────────────────────
NEBIUS_MODELS = [
    {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct", "name": "Llama 3.1 70B", "quality": "molto alta", "costo": "da $0.2/1M"},
    {"id": "Qwen/Qwen3-235B-A22B", "name": "Qwen 3 235B", "quality": "molto alta", "costo": "da $0.2/1M"},
    {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3", "quality": "molto alta", "costo": "da $0.1/1M"},
    {"id": "mistralai/Mistral-Small-24B-Instruct-2501", "name": "Mistral Small 24B", "quality": "alta", "costo": "da $0.05/1M"},
]
register_provider(_make_openai_provider(
    "nebius", "Nebius AI Studio", "API open-source con modelli vari. Crediti gratuiti all'iscrizione.",
    "https://api.studio.nebius.com/v1", "NEBIUS_API_KEY", NEBIUS_MODELS,
    free=False, website="https://studio.nebius.com"
))


# ─── Novita AI ─────────────────────────────────────────────────
NOVITA_MODELS = [
    {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "quality": "molto alta", "costo": "da $0.55/1M"},
    {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "quality": "molto alta", "costo": "da $0.88/1M"},
    {"id": "qwen/qwen3-235b-a22b", "name": "Qwen 3 235B", "quality": "molto alta", "costo": "da $0.65/1M"},
    {"id": "mistralai/mistral-small-24b-instruct-2501", "name": "Mistral Small 24B", "quality": "alta", "costo": "da $0.1/1M"},
]
register_provider(_make_openai_provider(
    "novita", "Novita AI", "API open-source con modelli vari. Crediti gratuiti all'iscrizione.",
    "https://api.novita.ai/openai/v1", "NOVITA_API_KEY", NOVITA_MODELS,
    free=False, website="https://novita.ai"
))


# ─── Inference.net ─────────────────────────────────────────────
INFERENCE_MODELS = [
    {"id": "google/gemma-3-27b-instruct/bf-16", "name": "Gemma 3 27B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "qwen/qwen3-32b", "name": "Qwen 3 32B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "quality": "molto alta", "costo": "gratuito"},
]
register_provider(_make_openai_provider(
    "inference", "Inference.net", "Modelli open-source gratuiti. API key gratuita.",
    "https://api.inference.net/v1", "INFERENCE_API_KEY", INFERENCE_MODELS,
    free=True, website="https://inference.net"
))
