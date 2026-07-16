import os
import logging

logger = logging.getLogger(__name__)


def get_ai_response(messages, user_id=None, force_provider=None):
    from ai_engine.registry import PROVIDERS, user_providers, DEFAULT_PROVIDER, DEFAULT_MODEL
    from ai_engine.chain import _provider_ready, FREE_MODEL_CHAIN, _should_skip_heavy_model
    from ai_engine.config import CHAT_PROVIDER, GROQ_CHAT_MODELS

    if force_provider and force_provider in PROVIDERS and _provider_ready(force_provider):
        fp = PROVIDERS[force_provider]
        fmodel = fp.get("models", [{}])[0].get("id") if fp.get("models") else None
        if fmodel:
            try:
                logger.info(f"force_provider: provo {force_provider}/{fmodel}")
                result = fp["generate"](messages, fmodel, user_id=user_id)
                if result:
                    logger.info(f"Risposta AI da {force_provider}/{fmodel} (force_provider)")
                    return result, force_provider, fmodel
                else:
                    logger.warning(f"  force_provider {force_provider}/{fmodel}: generate ha restituito None")
            except Exception as e:
                logger.warning(f"  force_provider {force_provider}/{fmodel} errore ({e}), fallback catena normale")
        else:
            logger.warning(f"  force_provider {force_provider}: nessun modello disponibile")
    elif force_provider:
        logger.warning(f"  force_provider {force_provider}: provider non pronto (ready={_provider_ready(force_provider) if force_provider in PROVIDERS else 'non registrato'})")

    if CHAT_PROVIDER == "groq" and "groq" in PROVIDERS and _provider_ready("groq"):
        for model in GROQ_CHAT_MODELS:
            try:
                result = PROVIDERS["groq"]["generate"](messages, model, user_id=user_id)
                if result:
                    logger.info(f"Risposta AI da groq/{model} (CHAT_PROVIDER=groq)")
                    return result, "groq", model
            except Exception as e:
                logger.warning(f"  groq/{model} errore ({e}), provo il prossimo...")

    if CHAT_PROVIDER == "local" and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        try:
            result = PROVIDERS[DEFAULT_PROVIDER]["generate"](messages, DEFAULT_MODEL, user_id=user_id)
            if result:
                logger.info(f"Risposta AI da {DEFAULT_PROVIDER}/{DEFAULT_MODEL} (CHAT_PROVIDER=local)")
                return result, DEFAULT_PROVIDER, DEFAULT_MODEL
        except Exception as e:
            logger.warning(f"  local: {DEFAULT_PROVIDER}/{DEFAULT_MODEL} errore ({e})")

    force_first = os.environ.get("FORCE_LOCAL_FIRST", "0") == "1"
    if force_first and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        try:
            result = PROVIDERS[DEFAULT_PROVIDER]["generate"](messages, DEFAULT_MODEL, user_id=user_id)
            if result:
                logger.info(f"Risposta AI da {DEFAULT_PROVIDER}/{DEFAULT_MODEL} (FORCE_LOCAL_FIRST)")
                return result, DEFAULT_PROVIDER, DEFAULT_MODEL
        except Exception as e:
            logger.warning(f"  forced: {DEFAULT_PROVIDER}/{DEFAULT_MODEL} errore ({e})")

    if user_id and user_id in user_providers:
        cfg = user_providers[user_id]
        pid = cfg.get("provider")
        model = cfg.get("model")
        if pid and model and pid in PROVIDERS:
            provider = PROVIDERS[pid]
            if _provider_ready(pid):
                try:
                    result = provider["generate"](messages, model, user_id=user_id)
                    if result:
                        logger.info(f"Risposta AI da {pid}/{model} (preferito utente)")
                        return result, pid, model
                except Exception as e:
                    logger.warning(f"  user-pref: {pid}/{model} errore ({e})")

    for pid, model in FREE_MODEL_CHAIN:
        if pid not in PROVIDERS:
            continue
        if not _provider_ready(pid):
            continue
        if pid == "ollama" and _should_skip_heavy_model(model):
            continue
        provider = PROVIDERS[pid]
        try:
            result = provider["generate"](messages, model, user_id=user_id)
            if result:
                logger.info(f"Risposta AI da {pid}/{model}")
                return result, pid, model
        except Exception as e:
            logger.warning(f"  {pid}/{model} errore ({e})")

    logger.error("Tutti i modelli esauriti, nessuna risposta disponibile")
    return None, None, None
