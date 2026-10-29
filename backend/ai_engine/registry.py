import threading
import logging

logger = logging.getLogger(__name__)

PROVIDERS = {}
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"
user_providers = {}
user_api_keys = {}
user_lock = {}


def _lock(user_id):
    if user_id not in user_lock:
        user_lock[user_id] = threading.Lock()
    return user_lock[user_id]


def register_provider(provider):
    PROVIDERS[provider["id"]] = provider


def get_providers():
    from ai_engine.providers.ollama import _ollama_local_models, OLLAMA_MODELS
    installed = _ollama_local_models()
    ollama_models = [m for m in OLLAMA_MODELS if m["id"] in installed or f"{m['id']}:latest" in installed]
    if not ollama_models and installed:
        ollama_models = [{"id": m, "name": m, "quality": "sconosciuta", "size": "?"} for m in installed]

    return {pid: {
        "name": p["name"],
        "description": p.get("description", ""),
        "models": ollama_models if pid == "ollama" else p.get("models", []),
        "needs_key": p.get("needs_key", False),
        "has_key": p.get("has_key", lambda: False)(),
        "free": p.get("free", False),
        "website": p.get("website", ""),
    } for pid, p in PROVIDERS.items()}


def get_active_config(user_id=None):
    if user_id and user_id in user_providers:
        return dict(user_providers[user_id])
    return {
        "provider": DEFAULT_PROVIDER,
        "model": DEFAULT_MODEL,
    }


def _resolve_model(provider_id, model):
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return None
    if model and any(m["id"] == model for m in provider.get("models", [])):
        return model
    models = provider.get("models", [])
    return models[0]["id"] if models else None


def set_active(user_id, provider_id, model=None):
    if provider_id not in PROVIDERS:
        logger.warning(f"Unknown provider: {provider_id}")
        return False
    with _lock(user_id):
        resolved = _resolve_model(provider_id, model)
        user_providers[user_id] = {"provider": provider_id, "model": resolved}
        logger.info(f"User {user_id}: provider={provider_id}, model={resolved}")
    return True


def set_user_api_key(user_id, provider_id, api_key):
    if not api_key:
        return
    if user_id not in user_api_keys:
        user_api_keys[user_id] = {}
    user_api_keys[user_id][provider_id] = api_key
    logger.info(f"User {user_id}: API key stored for {provider_id}")


def _get_user_api_key(user_id, provider_id):
    return user_api_keys.get(user_id, {}).get(provider_id, "")


def _get_config(user_id):
    if user_id and user_id in user_providers:
        return user_providers[user_id]
    return {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL}
