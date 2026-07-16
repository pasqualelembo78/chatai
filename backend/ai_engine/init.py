import os
import time
import logging
import threading

import requests

logger = logging.getLogger(__name__)


def init_provider():
    from ai_engine.registry import DEFAULT_PROVIDER, DEFAULT_MODEL, PROVIDERS
    from ai_engine.chain import rebuild_free_model_chain
    from ai_engine.providers.ollama import _ollama_available, _ollama_local_models, OLLAMA_MODELS

    providers_snapshot = {k: v for k, v in PROVIDERS.items()}
    default_p = DEFAULT_PROVIDER
    default_m = DEFAULT_MODEL

    if _ollama_available():
        local = _ollama_local_models()
        for m in [m["id"] for m in OLLAMA_MODELS]:
            if m in local or m.replace(":latest", "") in local:
                default_p = "ollama"
                default_m = m
                logger.info(f"Default: Ollama with {m}")
                _apply_defaults(default_p, default_m)
                rebuild_free_model_chain()
                return
        if local:
            default_p = "ollama"
            default_m = local[0]
            logger.info(f"Default: Ollama with {local[0]}")
            _apply_defaults(default_p, default_m)
            rebuild_free_model_chain()
            return
        logger.warning("Ollama disponibile ma nessun modello trovato. Verifica con 'ollama list'.")
    else:
        logger.warning("Ollama non disponibile, provo altri provider.")

    from ai_engine.registry import get_providers
    providers = get_providers()

    for preferred in ["llamacpp", "groq", "cerebras", "sambanova", "inference", "pollinations", "gemini", "cohere", "cloudflare", "mistral", "github", "huggingface", "openrouter", "openai", "anthropic", "together", "deepinfra", "fireworks", "nebius", "novita"]:
        info = providers.get(preferred)
        if not info:
            continue

        if info.get("has_key"):
            default_p = preferred
            default_m = providers[preferred]["models"][0]["id"] if providers[preferred]["models"] else None
            logger.info(f"Default: {preferred}")
            _apply_defaults(default_p, default_m)
            rebuild_free_model_chain()
            return

    default_p = "ollama"
    default_m = "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"
    logger.info("Fallback default: ollama with Qwen2.5-3B-abliterated-RP_SLERP")
    logger.info("Se il modello non e' installato, esegui: ollama pull hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M")
    _apply_defaults(default_p, default_m)
    rebuild_free_model_chain()


def _apply_defaults(provider, model):
    import ai_engine.registry as reg
    reg.DEFAULT_PROVIDER = provider
    reg.DEFAULT_MODEL = model


def test_provider_connection(provider_id, api_key):
    if not api_key:
        return False, "Nessuna API key fornita"
    try:
        if provider_id == "groq":
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "openai":
            resp = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "openrouter":
            resp = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "anthropic":
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                },
                timeout=10
            )
        elif provider_id == "gemini":
            resp = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=10
            )
        elif provider_id == "together":
            resp = requests.get(
                "https://api.together.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "cerebras":
            resp = requests.get(
                "https://api.cerebras.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "cohere":
            resp = requests.get(
                "https://api.cohere.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "deepinfra":
            resp = requests.get(
                "https://api.deepinfra.com/v1/openai/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "fireworks":
            resp = requests.get(
                "https://api.fireworks.ai/inference/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "sambanova":
            resp = requests.get(
                "https://api.sambanova.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "nebius":
            resp = requests.get(
                "https://api.studio.nebius.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "novita":
            resp = requests.get(
                "https://api.novita.ai/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "inference":
            resp = requests.get(
                "https://api.inference.net/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        elif provider_id == "huggingface":
            resp = requests.get(
                "https://router.huggingface.co/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
        else:
            return False, f"Provider '{provider_id}' non supportato"
        if resp.status_code == 200:
            return True, "Connessione riuscita"
        if resp.status_code == 401:
            return False, "API key non valida (401)"
        return False, f"Errore {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        return False, "Timeout: il server non risponde"
    except requests.exceptions.ConnectionError:
        return False, "Errore di connessione: verifica la rete"
    except Exception as e:
        return False, str(e)[:200]


def _start_auto_refresh():
    from ai_engine.config import _CACHE_TTL
    from ai_engine.config import clear_model_cache
    from ai_engine.chain import rebuild_free_model_chain

    def _refresh_loop():
        while True:
            time.sleep(_CACHE_TTL)
            try:
                logger.info("Auto-refresh: aggiornamento modelli disponibili...")
                clear_model_cache()
                rebuild_free_model_chain()
                logger.info("Auto-refresh: completato")
            except Exception as e:
                logger.warning(f"Auto-refresh: errore ({e})")

    t = threading.Thread(target=_refresh_loop, daemon=True)
    t.start()
    logger.info(f"Auto-refresh modelli ogni {_CACHE_TTL} secondi attivato")


_start_auto_refresh()
