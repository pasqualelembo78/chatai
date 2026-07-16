import os
import time
import subprocess
import logging
import requests

from ai_engine.registry import register_provider

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_BASE}/api/chat"

OLLAMA_OPTIONS = {
    "temperature": 0.8,
    "top_p": 0.8,
    "repeat_penalty": 1.05,
    "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", 4096)),
    "num_predict": int(os.environ.get("OLLAMA_NUM_PREDICT", 512)),
    "num_thread": int(os.environ.get("OLLAMA_NUM_THREAD", 6)),
    "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "30m"),
}

OLLAMA_STARTED = False
OLLAMA_START_LOCK = False


def _ensure_ollama():
    global OLLAMA_STARTED, OLLAMA_START_LOCK
    if OLLAMA_STARTED:
        return True
    if OLLAMA_START_LOCK:
        return False

    try:
        if requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2).status_code == 200:
            OLLAMA_STARTED = True
            return True
    except Exception:
        pass

    OLLAMA_START_LOCK = True
    logger.info("Ollama non in esecuzione. Avvio in corso...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        for i in range(20):
            time.sleep(2)
            try:
                if requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2).status_code == 200:
                    OLLAMA_STARTED = True
                    logger.info("Ollama avviato con successo.")
                    return True
            except Exception:
                continue
        logger.error("Ollama non si è avviato dopo 40 secondi.")
        return False
    except Exception as e:
        logger.error(f"Impossibile avviare Ollama: {e}")
        return False
    finally:
        OLLAMA_START_LOCK = False


OLLAMA_MODELS = [
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M", "name": "Qwen 2.5 3B Abliterated RP ★ (uncensored, roleplay)", "quality": "alta", "size": "2.1GB"},
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Qwen 2.5 3B Abliterated (uncensored)", "quality": "alta", "size": "2.0GB"},
    {"id": "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Llama 3.2 3B Abliterated (uncensored, fallback)", "quality": "media", "size": "2.0GB"},
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B (censurato)", "quality": "media", "size": "2.0GB"},
    {"id": "llama3.2:1b", "name": "Llama 3.2 1B (censurato)", "quality": "base", "size": "0.7GB"},
    {"id": "openchat/openchat-7b", "name": "OpenChat 7B (censurato)", "quality": "alta", "size": "4.1GB"},
    {"id": "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Qwen 2.5 7B Abliterated (uncensored, pesante)", "quality": "molto alta", "size": "4.7GB"},
    {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B (censurato)", "quality": "alta", "size": "4.7GB"},
    {"id": "llama3.1:8b", "name": "Llama 3.1 8B (censurato)", "quality": "alta", "size": "4.7GB"},
    {"id": "mistral:7b", "name": "Mistral 7B (censurato)", "quality": "alta", "size": "4.1GB"},
    {"id": "gemma2:9b", "name": "Gemma 2 9B (censurato)", "quality": "alta", "size": "5.5GB"},
    {"id": "mixtral:8x7b", "name": "Mixtral 8x7B (censurato)", "quality": "molto alta", "size": "26GB"},
    {"id": "qwen2.5:14b", "name": "Qwen 2.5 14B (censurato)", "quality": "alta", "size": "9.0GB"},
    {"id": "mistral-nemo:12b", "name": "Mistral Nemo 12B (censurato)", "quality": "alta", "size": "7.5GB"},
    {"id": "qwen2.5:32b", "name": "Qwen 2.5 32B (censurato)", "quality": "molto alta", "size": "20GB"},
    {"id": "deepseek-r1:7b", "name": "DeepSeek-R1 7B (ragiona)", "quality": "alta", "size": "4.7GB"},
    {"id": "llama3.3:70b", "name": "Llama 3.3 70B (censurato, server grande)", "quality": "top", "size": "40GB"},
    {"id": "llama3.1:70b", "name": "Llama 3.1 70B (censurato, server grande)", "quality": "top", "size": "40GB"},
    {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B (censurato, server grande)", "quality": "top", "size": "45GB"},
    {"id": "deepseek-r1:70b", "name": "DeepSeek-R1 70B (ragiona, server grande)", "quality": "top", "size": "43GB"},
]


def _ollama_available():
    try:
        if requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2).status_code == 200:
            return True
    except Exception:
        pass
    return _ensure_ollama()


def _ollama_local_models():
    if not _ensure_ollama():
        return []
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def _ollama_generate(messages, model, user_id=None):
    if not _ensure_ollama():
        logger.error(f"Ollama non disponibile")
        return None
    try:
        logger.info(f"Ollama: invio a {model}, {len(messages)} messaggi")
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": messages, "options": OLLAMA_OPTIONS, "stream": False},
            timeout=120
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            if content:
                logger.info(f"Ollama: risposta ricevuta ({len(content)} chars)")
                return content
            else:
                logger.warning(f"Ollama: risposta vuota da {model}")
                return None
        logger.error(f"Ollama error: {resp.status_code} {resp.text[:300]}")
        return None
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        return None


register_provider({
    "id": "ollama",
    "name": "Ollama (Locale)",
    "description": "Modelli AI gratuiti eseguiti localmente. Nessun dato inviato a server esterni. Richiede GPU per modelli grandi.",
    "models": OLLAMA_MODELS,
    "needs_key": False,
    "has_key": lambda: True,
    "free": True,
    "website": "https://ollama.ai",
    "available": _ollama_available,
    "generate": _ollama_generate,
    "generate_stream": lambda msgs, model, user_id=None: _generate_stream_impl(msgs, model, user_id),
    "default_model": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M",
})


def _generate_stream_impl(messages, model, user_id=None):
    from ai_engine.streaming import _ollama_generate_stream
    return _ollama_generate_stream(messages, model, user_id=user_id)
