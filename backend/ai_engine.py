import requests
import json
import os
import time
import logging
import shutil

logger = logging.getLogger(__name__)

# ─── Chat Provider Configuration ────────────────────────────────
# CHAT_PROVIDER=groq  → Groq 70B come prima scelta (italiano perfetto)
# CHAT_PROVIDER=local → modello locale come prima scelta
# CHAT_PROVIDER=auto  → comportamento attuale (catena normale)
CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "groq").lower()

# Modelli Groq prioritari per chat
GROQ_CHAT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "qwen/qwen3.6-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

# ─── Model Discovery Cache ───────────────────────────────────────

_MODEL_CACHE = {}
_CACHE_TTL = int(os.environ.get("MODEL_REFRESH_TTL", 3600))  # default 1 ora


def _cached_fetch(url, headers=None, timeout=10, cache_key=None):
    cache_key = cache_key or url
    now = time.time()
    if cache_key in _MODEL_CACHE and now - _MODEL_CACHE[cache_key]["ts"] < _CACHE_TTL:
        return _MODEL_CACHE[cache_key]["data"]
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            _MODEL_CACHE[cache_key] = {"data": data, "ts": now}
            return data
    except Exception:
        pass
    return None


def _discover_groq_models():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return []
    data = _cached_fetch(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        cache_key="groq_models"
    )
    if not data:
        return []
    available = [m["id"] for m in data.get("data", [])]
    priority = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen/qwen3-32b",
        "qwen/qwen3.6-27b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "mixtral-8x7b-32768",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "llama-guard-3-8b",
    ]
    found = [m for m in priority if m in available]
    extra = [m for m in available if m not in found and not m.startswith("whisper")]
    return found + extra[:5]


def _discover_openrouter_free_models():
    data = _cached_fetch(
        "https://openrouter.ai/api/v1/models",
        cache_key="or_models"
    )
    if not data:
        return []
    available = {}
    for m in data.get("data", []):
        mid = m["id"]
        pricing = m.get("pricing", {})
        prompt_cost = float(pricing.get("prompt", "999"))
        completion_cost = float(pricing.get("completion", "999"))
        available[mid] = {"prompt_cost": prompt_cost, "completion_cost": completion_cost}

    priority = [
        "openai/gpt-4o-mini",
        "deepseek/deepseek-chat",
    ]
    result = [m for m in priority if m in available]
    for mid, costs in available.items():
        if mid not in result and costs["prompt_cost"] == 0 and costs["completion_cost"] == 0:
            result.append(mid)
    return result


def _discover_gemini_models():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return []
    data = _cached_fetch(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
        cache_key="gemini_models"
    )
    if not data:
        return []
    available = [m["name"].replace("models/", "") for m in data.get("models", [])]
    priority = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-preview-09-2025",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
    ]
    found = [m for m in priority if m in available]
    return found


def clear_model_cache():
    _MODEL_CACHE.clear()
    logger.info("Model cache cleared")


def rebuild_free_model_chain():
    chain = []

    chain.append(("ollama", "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"))
    chain.append(("ollama", "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M"))
    chain.append(("ollama", "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M"))
    chain.append(("ollama", "llama3.2:3b"))
    chain.append(("ollama", "llama3.2:1b"))
    # 7B albiterated finale — saltato dal guardiano RAM se memoria poca
    if _ram_ok_for_model(HEAVY_LOCAL_MODELS["hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M"]):
        pass  # disponibile, lo aggiungerà sotto
    chain.append(("ollama", "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M"))

    chain.append(("openrouter", "openai/gpt-4o-mini"))

    groq = _discover_groq_models()
    for m in groq:
        chain.append(("groq", m))

    gemini = _discover_gemini_models()
    for m in gemini:
        chain.append(("gemini", m))

    or_free = _discover_openrouter_free_models()
    for m in or_free:
        chain.append(("openrouter", m))

    chain.append(("ollama", "llama3.2:3b"))
    chain.append(("ollama", "llama3.2:1b"))

    chain.append(("mistral", "mistral-small-latest"))
    chain.append(("mistral", "open-mixtral-8x7b"))
    chain.append(("github", "gpt-4o-mini"))
    chain.append(("github", "gpt-4o"))
    chain.append(("github", "Llama-3.3-70B-Instruct"))
    chain.append(("github", "DeepSeek-R1"))

    global FREE_MODEL_CHAIN
    FREE_MODEL_CHAIN = chain
    logger.info(f"Catena modelli dinamica: {len(chain)} entry")
    for p, m in chain:
        logger.info(f"  {p}/{m}")
    return chain

# ─── Provider Registry ──────────────────────────────────────────

PROVIDERS = {}
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"
user_providers = {}
user_api_keys = {}
user_lock = {}


def _lock(user_id):
    import threading
    if user_id not in user_lock:
        user_lock[user_id] = threading.Lock()
    return user_lock[user_id]


def register_provider(provider):
    PROVIDERS[provider["id"]] = provider


def get_providers():
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


# ─── Catena automatica modelli gratuiti (dal migliore al peggiore) ──
# Ordine: LOCALI (veloci, zero costo) → FREE CLOUD (buoni, zero costo) → PAGATI (potenti, a pagamento)

FREE_MODEL_CHAIN = [
    # ── LOCALI: nessuna internet, nessun costo, massima privacy ──
    # RP_SLERP = abliterated + merge roleplay: non si blocca a freddo su
    # messaggi espliciti. Questo è il modello di DEFAULT di ChatAI.
    ("ollama",     "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"),
    ("ollama",     "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M"),
    ("ollama",     "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M"),
    ("ollama",     "llama3.2:3b"),
    ("ollama",     "llama3.2:1b"),
    ("llamacpp",   "local"),

    # ── 7B UNCENSORED — finale (pesante, guardiano RAM lo salta se poca memoria libera) ──
    # Da attivare quando il server viene potenziato (>16 GB RAM o GPU).
    # Per ora resta sul disco come fallback di emergenza: viene caricato in RAM
    # solo se tutti i 3B-abliterated precedenti falliscono.
    ("ollama",     "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M"),

    # ── FREE CLOUD: internet richiesta, nessun costo ──
    # Veloce: inferenza ultra-veloce
    ("cerebras",   "gpt-oss-120b"),
    ("cerebras",   "zai-glm-4.7"),
    ("cerebras",   "gemma-4-31b"),
    ("groq",       "llama-3.3-70b-versatile"),
    ("groq",       "llama-3.1-8b-instant"),
    ("groq",       "qwen/qwen3-32b"),
    ("groq",       "qwen/qwen3.6-27b"),
    ("groq",       "meta-llama/llama-4-scout-17b-16e-instruct"),
    ("sambanova",  "DeepSeek-V3.1"),
    ("sambanova",  "Meta-Llama-3.3-70B-Instruct"),
    ("sambanova",  "Llama-4-Maverick-17B-128E-Instruct"),
    # Buoni: modelli di qualita
    ("inference",  "meta-llama/llama-3.3-70b-instruct"),
    ("inference",  "qwen/qwen3-32b"),
    ("inference",  "google/gemma-3-27b-instruct/bf-16"),
    ("inference",  "deepseek/deepseek-r1"),
    ("cohere",     "command-a-plus-05-2026"),
    ("cohere",     "command-r"),
    ("cloudflare", "@cf/meta/llama-3.1-8b-instruct-fp8"),
    ("cloudflare", "@cf/meta/llama-3.3-70b-instruct-fp16"),
    # Buoni: modelli collaudati
    ("gemini",     "gemini-2.5-flash"),
    ("gemini",     "gemini-2.5-flash-lite"),
    ("gemini",     "gemini-2.0-flash"),
    ("mistral",    "mistral-small-latest"),
    ("mistral",    "open-mixtral-8x7b"),
    ("github",     "gpt-4o-mini"),
    ("github",     "gpt-4o"),
    ("github",     "Llama-3.3-70B-Instruct"),
    ("github",     "DeepSeek-R1"),
    ("huggingface","openai/gpt-oss-120b:fastest"),
    ("huggingface","Qwen/Qwen3-8B:fastest"),
    ("huggingface","meta-llama/Llama-3.1-8B-Instruct:fastest"),

    # ── PAGATI: internet richiesta, costo variabile ──
    # Economici: buon rapporto qualita/prezzo
    ("openrouter", "openai/gpt-4o-mini"),
    ("openrouter", "deepseek/deepseek-chat"),
    ("openrouter", "meta-llama/llama-4-scout:free"),
    ("openrouter", "meta-llama/llama-4-maverick:free"),
    ("openrouter", "deepseek/deepseek-r1:free"),
    ("together",   "Qwen/Qwen3.5-9B"),
    ("deepinfra",  "deepseek-ai/DeepSeek-V3"),
    ("nebius",     "deepseek-ai/DeepSeek-V3"),
    ("fireworks",  "accounts/fireworks/models/deepseek-v3p1"),
    ("novita",     "deepseek/deepseek-r1"),
    # Potenti: modelli di alto livello
    ("together",   "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ("deepinfra",  "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ("nebius",     "meta-llama/Meta-Llama-3.1-70B-Instruct"),
    ("fireworks",  "accounts/fireworks/models/llama-v3p3-70b-instruct"),
    ("novita",     "meta-llama/llama-3.3-70b-instruct"),
    # Premium: i piu potenti e costosi
    ("openrouter", "anthropic/claude-3-haiku"),
    ("openrouter", "cohere/command-r-plus"),
    ("together",   "Qwen/Qwen3-235B-A22B"),
    ("deepinfra",  "Qwen/Qwen3-235B-A22B"),
    ("nebius",     "Qwen/Qwen3-235B-A22B"),
]


def _provider_ready(pid):
    if pid == "ollama":
        return _ollama_available()
    provider = PROVIDERS.get(pid)
    if not provider:
        logger.warning(f"  auto: provider '{pid}' non registrato")
        return False
    ready = provider.get("has_key", lambda: False)()
    if not ready:
        logger.warning(f"  auto: {pid} non pronto (chiave API mancante o env var non trovata)")
    return ready


# ─── RAM Guardian per modelli locali pesanti ──────────────────────
# I modelli 7B+ su Ollama vengono caricati in RAM solo all'uso. Se la
# RAM libera è insufficiente, li saltiamo invece di rischiare OOM/swap.
# Soglia configurabile via env RAM_GUARDIAN_MIN_FREE_GB (default 1.5 GB).

RAM_GUARDIAN_MIN_FREE_GB = float(os.environ.get("RAM_GUARDIAN_MIN_FREE_GB", "1.5"))


def _check_ram_available():
    """Ritorna (ram_free_gb, total_gb). Usa psutil se disponibile, fallback shutil."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.available / (1024 ** 3), vm.total / (1024 ** 3)
    except ImportError:
        pass
    try:
        total, used, free = shutil.disk_usage.__self__.usage
    except Exception:
        pass
    # Fallback leggendo /proc/meminfo (Linux)
    try:
        with open("/proc/meminfo", "r") as f:
            info = {}
            for line in f:
                k, _, v = line.partition(":")
                if k in ("MemTotal", "MemAvailable"):
                    info[k] = int(v.strip().split()[0]) * 1024
        return info.get("MemAvailable", 0) / (1024 ** 3), info.get("MemTotal", 0) / (1024 ** 3)
    except Exception:
        return float("inf"), float("inf")


def _ram_ok_for_model(required_gb):
    """True se la RAM libera è >= required_gb + RAM_GUARDIAN_MIN_FREE_GB."""
    free_gb, _ = _check_ram_available()
    ok = free_gb >= (required_gb + RAM_GUARDIAN_MIN_FREE_GB)
    if not ok:
        logger.info(f"  ram-guardian: libera {free_gb:.1f} GB, serve {required_gb:.1f}+{RAM_GUARDIAN_MIN_FREE_GB} GB → saldo")
    return ok


# Mappa dei modelli localmente pesanti → RAM necessaria stimata (GB)
HEAVY_LOCAL_MODELS = {
    "qwen2.5:7b": 5.0,
    "llama3.1:8b": 5.0,
    "mistral:7b": 4.5,
    "gemma2:9b": 6.0,
    "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M": 5.0,
    "hf.co/huihui-ai/Qwen2.5-7B-Instruct-abliterated-v2-GGUF:Q4_K_M": 5.0,
    "mixtral:8x7b": 27.0,
}


def _should_skip_heavy_model(model_id):
    """True se il modello è pesante e la RAM è insufficiente."""
    required = HEAVY_LOCAL_MODELS.get(model_id)
    if not required:
        return False
    return not _ram_ok_for_model(required)


def get_ai_response(messages, user_id=None):
    # ── Determina la catena di provider per le chat ──
    # Priorita: CHAT_PROVIDER env → preferenza utente → FORCE_LOCAL_FIRST → catena normale
    
    # 1. Se CHAT_PROVIDER=groq, prova Groq per primo
    if CHAT_PROVIDER == "groq" and "groq" in PROVIDERS and _provider_ready("groq"):
        for model in GROQ_CHAT_MODELS:
            try:
                result = PROVIDERS["groq"]["generate"](messages, model, user_id=user_id)
                if result:
                    logger.info(f"Risposta AI da groq/{model} (CHAT_PROVIDER=groq)")
                    return result, "groq", model
            except Exception as e:
                logger.warning(f"  groq/{model} errore ({e}), provo il prossimo...")
    
    # 2. Se CHAT_PROVIDER=local, prova il modello locale per primo
    if CHAT_PROVIDER == "local" and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        try:
            result = PROVIDERS[DEFAULT_PROVIDER]["generate"](messages, DEFAULT_MODEL, user_id=user_id)
            if result:
                logger.info(f"Risposta AI da {DEFAULT_PROVIDER}/{DEFAULT_MODEL} (CHAT_PROVIDER=local)")
                return result, DEFAULT_PROVIDER, DEFAULT_MODEL
        except Exception as e:
            logger.warning(f"  local: {DEFAULT_PROVIDER}/{DEFAULT_MODEL} errore ({e})")

    # 3. FORCE_LOCAL_FIRST (compatibilita con comportamento precedente)
    force_first = os.environ.get("FORCE_LOCAL_FIRST", "0") == "1"
    if force_first and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        try:
            result = PROVIDERS[DEFAULT_PROVIDER]["generate"](messages, DEFAULT_MODEL, user_id=user_id)
            if result:
                logger.info(f"Risposta AI da {DEFAULT_PROVIDER}/{DEFAULT_MODEL} (FORCE_LOCAL_FIRST)")
                return result, DEFAULT_PROVIDER, DEFAULT_MODEL
        except Exception as e:
            logger.warning(f"  forced: {DEFAULT_PROVIDER}/{DEFAULT_MODEL} errore ({e})")

    # 4. Preferenza utente
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

    # 5. Catena normale (fallback)
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


# ─── Streaming helpers ──────────────────────────────────────────

STREAM_STOP_FLAGS = {}


def _stream_stop_requested(user_id):
    return STREAM_STOP_FLAGS.get(user_id, False)


def _stream_clear_stop(user_id):
    STREAM_STOP_FLAGS.pop(user_id, None)


def _stream_openai_compatible(url, headers, payload, model, timeout=120):
    """Generator che yielda token da API OpenAI-compatibili con stream=True."""
    payload = {**payload, "stream": True, "model": model}
    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
        if resp.status_code != 200:
            logger.error(f"Stream error {resp.status_code}: {resp.text[:200]}")
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Stream request failed: {e}")


def _gemini_generate_stream(messages, model, user_id=None):
    """Gemini streaming via SSE."""
    key = _gemini_key(user_id)
    if not key:
        logger.error("Gemini API key not set")
        return
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
        body = {"contents": chat}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={key}&alt=sse",
            json=body, stream=True, timeout=60
        )
        if resp.status_code != 200:
            logger.error(f"Gemini stream error {resp.status_code}: {resp.text[:200]}")
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            token = p.get("text", "")
                            if token:
                                yield token
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Gemini stream failed: {e}")


def _anthropic_generate_stream(messages, model, user_id=None):
    """Anthropic streaming."""
    key = _anthropic_key(user_id)
    if not key:
        logger.error("Anthropic API key not set")
        return
    system = ""
    chat = []
    for m in messages:
        if m["role"] == "system":
            system += m["content"] + "\n"
        else:
            chat.append({"role": m["role"], "content": m["content"]})
    try:
        body = {"model": model, "max_tokens": 200, "messages": chat, "stream": True}
        if system.strip():
            body["system"] = system.strip()
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key, "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body, stream=True, timeout=60
        )
        if resp.status_code != 200:
            logger.error(f"Anthropic stream error {resp.status_code}: {resp.text[:200]}")
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
                if data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    token = delta.get("text", "")
                    if token:
                        yield token
            except json.JSONDecodeError:
                continue
    except Exception as e:
        logger.error(f"Anthropic stream failed: {e}")


def _ollama_generate_stream(messages, model, user_id=None):
    """Ollama streaming via /api/chat con stream=true."""
    OLLAMA_STREAM_OPTIONS = {**OLLAMA_OPTIONS, "num_predict": 200}
    if not _ensure_ollama():
        return
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": messages, "options": OLLAMA_STREAM_OPTIONS, "stream": True},
            stream=True, timeout=120
        )
        if resp.status_code != 200:
            logger.error(f"Ollama stream error {resp.status_code}: {resp.text[:200]}")
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue
    except Exception as e:
        logger.error(f"Ollama stream failed: {e}")


def _stream_wrapper(gen_func):
    """Avvolge una generate sincrona in un generatore che yielda l'intero testo."""
    def wrapper(messages, model, user_id=None):
        result = gen_func(messages, model, user_id=user_id)
        if result:
            yield result
    return wrapper


def get_ai_response_stream(messages, user_id=None):
    """Generator: tenta provider in catena con streaming, yielda (token, provider_id, model)."""
    chain = []

    # 1. Se CHAT_PROVIDER=groq, prova Groq per primo con streaming
    if CHAT_PROVIDER == "groq" and "groq" in PROVIDERS and _provider_ready("groq"):
        for model in GROQ_CHAT_MODELS:
            chain.append(("groq", model))

    # 2. Se CHAT_PROVIDER=local, prova il modello locale per primo
    if CHAT_PROVIDER == "local" and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        chain.append((DEFAULT_PROVIDER, DEFAULT_MODEL))

    # 3. FORCE_LOCAL_FIRST (compatibilita)
    force_first = os.environ.get("FORCE_LOCAL_FIRST", "0") == "1"
    if force_first and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        if (DEFAULT_PROVIDER, DEFAULT_MODEL) not in chain:
            chain.append((DEFAULT_PROVIDER, DEFAULT_MODEL))

    # 4. Preferenza utente
    if user_id and user_id in user_providers:
        cfg = user_providers[user_id]
        pid = cfg.get("provider")
        model = cfg.get("model")
        if pid and model and pid in PROVIDERS and (pid, model) not in chain:
            chain.append((pid, model))

    # 5. Catena normale (fallback)
    for pid, model in FREE_MODEL_CHAIN:
        if pid in PROVIDERS and (pid, model) not in chain:
            chain.append((pid, model))

    seen = set()
    for pid, model in chain:
        key = (pid, model)
        if key in seen:
            continue
        seen.add(key)

        if not _provider_ready(pid):
            continue

        if pid == "ollama" and _should_skip_heavy_model(model):
            logger.info(f"  auto: {pid}/{model} saltato (RAM insufficiente)")
            continue

        provider = PROVIDERS[pid]
        stream_fn = provider.get("generate_stream") or provider.get("generate")

        if not stream_fn:
            continue

        try:
            gen = stream_fn(messages, model, user_id=user_id)
            first_token = None
            for token in gen:
                if first_token is None:
                    first_token = token
                    logger.info(f"Streaming response da {pid}/{model}")
                if _stream_stop_requested(user_id):
                    logger.info(f"Stream {pid}/{model} fermato dall'utente")
                    return
                yield token, pid, model
            if first_token is not None:
                return
        except Exception as e:
            logger.warning(f"  stream {pid}/{model} errore ({e}), provo il prossimo...")
            continue

    logger.error("Tutti i modelli streaming esauriti")
    # Fallback: usa generate normale
    text, pid, model = get_ai_response(messages, user_id=user_id)
    if text:
        yield text, pid, model


# ─── Ollama (Free, Local) ───────────────────────────────────────

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
    import time, subprocess, sys

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
    # ── UNCENSORED (abliterated) — prima in catena ──
    # RP_SLERP = merge specializzato roleplay: non si blocca neanche a freddo
    # su messaggi espliciti. ★ = modello principale/consigliato
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M", "name": "Qwen 2.5 3B Abliterated RP ★ (uncensored, roleplay)", "quality": "alta", "size": "2.1GB"},
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Qwen 2.5 3B Abliterated (uncensored)", "quality": "alta", "size": "2.0GB"},
    {"id": "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Llama 3.2 3B Abliterated (uncensored, fallback)", "quality": "media", "size": "2.0GB"},
    # ── STANDARD (censurati) — solo fallback emergenza ──
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B (censurato)", "quality": "media", "size": "2.0GB"},
    {"id": "llama3.2:1b", "name": "Llama 3.2 1B (censurato)", "quality": "base", "size": "0.7GB"},
    # 7B uncensored (relativo) — finale di catena, guardiano RAM lo protegge
    {"id": "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M", "name": "Qwen 2.5 7B Abliterated (uncensored, pesante)", "quality": "molto alta", "size": "4.7GB"},
    {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B (censurato)", "quality": "alta", "size": "4.7GB"},
    {"id": "llama3.1:8b", "name": "Llama 3.1 8B (censurato)", "quality": "alta", "size": "4.7GB"},
    {"id": "mistral:7b", "name": "Mistral 7B (censurato)", "quality": "alta", "size": "4.1GB"},
    {"id": "gemma2:9b", "name": "Gemma 2 9B (censurato)", "quality": "alta", "size": "5.5GB"},
    {"id": "mixtral:8x7b", "name": "Mixtral 8x7B (censurato)", "quality": "molto alta", "size": "26GB"},
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
        return None
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": messages, "options": OLLAMA_OPTIONS, "stream": False},
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json()["message"]["content"]
        logger.error(f"Ollama error: {resp.status_code} {resp.text}")
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
    "generate_stream": _ollama_generate_stream,
    "default_model": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M",
})


# ─── OpenAI (API a pagamento) ──────────────────────────────────

OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "quality": "molto alta", "costo": "$5/1M token"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "quality": "alta", "costo": "$0.15/1M token"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "quality": "molto alta", "costo": "$10/1M token"},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "quality": "alta", "costo": "$0.5/1M token"},
]


def _openai_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "openai")
        if k:
            return k
    return os.environ.get("OPENAI_API_KEY", "")


def _openai_generate(messages, model, user_id=None):
    key = _openai_key(user_id)
    if not key:
        logger.error("OpenAI API key not set")
        return None
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"OpenAI error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        return None


def _openai_generate_stream(messages, model, user_id=None):
    key = _openai_key(user_id)
    if not key:
        logger.error("OpenAI API key not set")
        return
    yield from _stream_openai_compatible(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "openai",
    "name": "OpenAI (API)",
    "description": "Modelli GPT di OpenAI. Qualità eccellente. È necessaria una chiave API (apikey).",
    "models": OPENAI_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_openai_key()),
    "free": False,
    "website": "https://platform.openai.com",
    "generate": _openai_generate,
    "generate_stream": _openai_generate_stream,
    "default_model": "gpt-4o-mini",
})


# ─── Anthropic (API a pagamento) ────────────────────────────────

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
    "generate_stream": _anthropic_generate_stream,
    "default_model": "claude-3-5-sonnet-20240620",
})


# ─── Google Gemini (API, con free tier) ─────────────────────────

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
        body = {"contents": chat}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}

        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            json=body,
            timeout=60
        )
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
    "generate_stream": _gemini_generate_stream,
    "default_model": "gemini-2.0-flash",
})


# ─── Groq (API gratuita) ────────────────────────────────────────

GROQ_MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile", "quality": "molto alta", "costo": "gratuito"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "quality": "alta", "costo": "gratuito"},
    {"id": "qwen/qwen3-32b", "name": "Qwen 3 32B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout 17B", "quality": "molto alta", "costo": "gratuito"},
]


def _groq_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "groq")
        if k:
            return k
    return os.environ.get("GROQ_API_KEY", "")


def _groq_generate(messages, model, user_id=None):
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
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Groq error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"Groq request failed: {e}")
        return None


def _groq_generate_stream(messages, model, user_id=None):
    key = _groq_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


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


# ─── OpenRouter (API, gateway multi-modello) ────────────────────

OPENROUTER_MODELS = [
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "quality": "alta", "costo": "da $0.15/1M"},
    {"id": "meta-llama/llama-4-scout:free", "name": "Llama 4 Scout (free)", "quality": "molto alta", "costo": "gratuito"},
    {"id": "meta-llama/llama-4-maverick:free", "name": "Llama 4 Maverick (free)", "quality": "molto alta", "costo": "gratuito"},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B (free)", "quality": "molto alta", "costo": "gratuito"},
    {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (free)", "quality": "molto alta", "costo": "gratuito"},
    {"id": "mistralai/mistral-small:free", "name": "Mistral Small (free)", "quality": "alta", "costo": "gratuito"},
    {"id": "qwen/qwen3-coder:free", "name": "Qwen 3 Coder (free)", "quality": "alta", "costo": "gratuito"},
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek V3", "quality": "molto alta", "costo": "da $0.14/1M"},
    {"id": "qwen/qwen-110b-chat", "name": "Qwen 110B", "quality": "molto alta", "costo": "da $1.62/1M"},
    {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku", "quality": "alta", "costo": "da $0.25/1M"},
    {"id": "cohere/command-r-plus", "name": "Command R+", "quality": "alta", "costo": "da $2.5/1M"},
]


def _openrouter_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "openrouter")
        if k:
            return k
    return os.environ.get("OPENROUTER_API_KEY", "")


def _openrouter_generate(messages, model, user_id=None):
    key = _openrouter_key(user_id)
    if not key:
        logger.error("OpenRouter API key not set")
        return None
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://airoleplay.chat",
            },
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"OpenRouter error: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        return None


def _openrouter_generate_stream(messages, model, user_id=None):
    key = _openrouter_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://openrouter.ai/api/v1/chat/completions",
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://airoleplay.chat",
        },
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "openrouter",
    "name": "OpenRouter (API)",
    "description": "Gateway unico per 200+ modelli (OpenAI, Anthropic, Google, Meta, Mistral, ecc.). Unica chiave API per tutti.",
    "models": OPENROUTER_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_openrouter_key()),
    "free": False,
    "website": "https://openrouter.ai",
    "generate": _openrouter_generate,
    "generate_stream": _openrouter_generate_stream,
    "default_model": "openai/gpt-4o-mini",
})


# ─── Hugging Face (Inference API, free tier) ────────────────────

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


# ─── Mistral AI (API, free tier) ─────────────────────────────────

MISTRAL_MODELS = [
    {"id": "mistral-small-latest", "name": "Mistral Small", "quality": "alta", "costo": "free tier"},
    {"id": "open-mistral-7b", "name": "Open Mistral 7B", "quality": "alta", "costo": "gratuito"},
    {"id": "open-mixtral-8x7b", "name": "Open Mixtral 8x7B", "quality": "molto alta", "costo": "gratuito"},
    {"id": "codestral-latest", "name": "Codestral", "quality": "molto alta", "costo": "free tier"},
]


def _mistral_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "mistral")
        if k:
            return k
    return os.environ.get("MISTRAL_API_KEY", "")


def _mistral_generate(messages, model, user_id=None):
    key = _mistral_key(user_id)
    if not key:
        logger.error("Mistral API key not set")
        return None
    try:
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Mistral error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Mistral request failed: {e}")
        return None


def _mistral_generate_stream(messages, model, user_id=None):
    key = _mistral_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://api.mistral.ai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "mistral",
    "name": "Mistral AI (API)",
    "description": "Modelli Mistral AI con free tier generoso. Richiede chiave API Mistral (gratuita su console.mistral.ai).",
    "models": MISTRAL_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_mistral_key()),
    "free": True,
    "website": "https://console.mistral.ai",
    "generate": _mistral_generate,
    "generate_stream": _mistral_generate_stream,
    "default_model": "mistral-small-latest",
})


# ─── GitHub Models (Azure AI Inference, free tier) ──────────────

GITHUB_MODELS = [
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "quality": "alta", "costo": "gratuito"},
    {"id": "gpt-4o", "name": "GPT-4o", "quality": "molto alta", "costo": "gratuito"},
    {"id": "Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B Instruct", "quality": "molto alta", "costo": "gratuito"},
    {"id": "DeepSeek-R1", "name": "DeepSeek R1", "quality": "molto alta", "costo": "gratuito"},
]


def _github_key(user_id=None):
    if user_id:
        k = _get_user_api_key(user_id, "github")
        if k:
            return k
    return os.environ.get("GITHUB_TOKEN", "")


def _github_generate(messages, model, user_id=None):
    key = _github_key(user_id)
    if not key:
        logger.error("GitHub token not set")
        return None
    try:
        resp = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"GitHub Models error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"GitHub Models request failed: {e}")
        return None


def _github_generate_stream(messages, model, user_id=None):
    key = _github_key(user_id)
    if not key:
        return
    yield from _stream_openai_compatible(
        "https://models.inference.ai.azure.com/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )


register_provider({
    "id": "github",
    "name": "GitHub Models (Azure AI)",
    "description": "Modelli gratuiti via GitHub. Richiede un personal access token GitHub (gratuito).",
    "models": GITHUB_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_github_key()),
    "free": True,
    "website": "https://github.com/marketplace/models",
    "generate": _github_generate,
    "generate_stream": _github_generate_stream,
    "default_model": "gpt-4o-mini",
})


# ─── Factory per provider OpenAI-compatibili ─────────────────────

def _make_openai_provider(pid, name, desc, base_url, env_key, models, free=True, website="", extra_headers=None):
    """Crea un provider dict per API OpenAI-compatibili."""
    def _key(uid=None):
        if uid:
            k = _get_user_api_key(uid, pid)
            if k:
                return k
        return os.environ.get(env_key, "")

    def _generate(messages, model, uid=None):
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
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.error(f"{name} error: {resp.status_code} {resp.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"{name} request failed: {e}")
            return None

    def _generate_stream(messages, model, uid=None):
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


# ─── Cloudflare Workers AI ──────────────────────────────────────

CLOUDFLARE_MODELS = [
    {"id": "@cf/meta/llama-3.1-8b-instruct-fp8", "name": "Llama 3.1 8B FP8", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/meta/llama-3.3-70b-instruct-fp16", "name": "Llama 3.3 70B FP16", "quality": "molto alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/qwen/qwen1.5-14b-chat-awq", "name": "Qwen 1.5 14B", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
    {"id": "@cf/microsoft/phi-2", "name": "Phi-2", "quality": "alta", "costo": "gratuito (quota giornaliera)"},
]

def _cloudflare_key(uid=None):
    if uid:
        k = _get_user_api_key(uid, "cloudflare")
        if k:
            return k
    return os.environ.get("CLOUDFLARE_API_TOKEN", "")

def _cloudflare_account_id():
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

def _cloudflare_generate(messages, model, uid=None):
    key = _cloudflare_key(uid)
    account_id = _cloudflare_account_id()
    if not key or not account_id:
        logger.error("Cloudflare API token or Account ID not set")
        return None
    try:
        resp = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.9, "max_tokens": 200},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Cloudflare error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Cloudflare request failed: {e}")
        return None

def _cloudflare_generate_stream(messages, model, uid=None):
    key = _cloudflare_key(uid)
    account_id = _cloudflare_account_id()
    if not key or not account_id:
        return
    yield from _stream_openai_compatible(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"messages": messages, "temperature": 0.9, "max_tokens": 200},
        model
    )

register_provider({
    "id": "cloudflare",
    "name": "Cloudflare Workers AI",
    "description": "Modelli gratuiti via Cloudflare Workers. Richiede Account ID e API Token.",
    "models": CLOUDFLARE_MODELS,
    "needs_key": True,
    "has_key": lambda: bool(_cloudflare_key()) and bool(_cloudflare_account_id()),
    "free": True,
    "website": "https://developers.cloudflare.com/workers-ai",
    "generate": _cloudflare_generate,
    "generate_stream": _cloudflare_generate_stream,
    "default_model": "@cf/meta/llama-3.1-8b-instruct-fp8",
})


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


# ─── llama.cpp (locale) ─────────────────────────────────────────

LLAMACPP_MODELS = [
    {"id": "local", "name": "Modello locale", "quality": "dipende dal modello", "costo": "gratuito"},
]

def _llamacpp_key(uid=None):
    return os.environ.get("LLAMACPP_API_KEY", "")

def _llamacpp_available():
    try:
        resp = requests.get("http://localhost:8080/v1/models", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False

def _llamacpp_generate(messages, model, uid=None):
    if not _llamacpp_available():
        logger.error("llama.cpp non disponibile su localhost:8080")
        return None
    try:
        key = _llamacpp_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        # llama.cpp server accetta qualsiasi model name, ma passiamo quello reale
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
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"llama.cpp error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"llama.cpp request failed: {e}")
        return None

def _llamacpp_generate_stream(messages, model, uid=None):
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


# ─── Init: find best available default ──────────────────────────

def init_provider():
    global DEFAULT_PROVIDER, DEFAULT_MODEL
    providers = get_providers()

    # ── Prima scelta: Ollama locale ──
    if _ollama_available():
        local = _ollama_local_models()
        for m in [m["id"] for m in OLLAMA_MODELS]:
            if m in local or m.replace(":latest", "") in local:
                DEFAULT_PROVIDER = "ollama"
                DEFAULT_MODEL = m
                logger.info(f"Default: Ollama with {m}")
                rebuild_free_model_chain()
                return
        if local:
            DEFAULT_PROVIDER = "ollama"
            DEFAULT_MODEL = local[0]
            logger.info(f"Default: Ollama with {local[0]}")
            rebuild_free_model_chain()
            return
        logger.warning("Ollama disponibile ma nessun modello trovato. Verifica con 'ollama list'.")
    else:
        logger.warning("Ollama non disponibile, provo altri provider.")

    for preferred in ["llamacpp", "groq", "cerebras", "sambanova", "inference", "gemini", "cohere", "cloudflare", "mistral", "github", "huggingface", "openrouter", "openai", "anthropic", "together", "deepinfra", "fireworks", "nebius", "novita"]:
        info = providers.get(preferred)
        if not info:
            continue

        if info.get("has_key"):
            DEFAULT_PROVIDER = preferred
            DEFAULT_MODEL = providers[preferred]["models"][0]["id"] if providers[preferred]["models"] else None
            logger.info(f"Default: {preferred}")
            rebuild_free_model_chain()
            return

    DEFAULT_PROVIDER = "ollama"
    DEFAULT_MODEL = "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"
    logger.info("Fallback default: ollama with Qwen2.5-3B-abliterated-RP_SLERP")
    logger.info("Se il modello non e' installato, esegui: ollama pull hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M")
    rebuild_free_model_chain()


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


# ─── Auto-refresh scheduler ─────────────────────────────────────
# Ogni ora ricostruisce la catena per scoprire nuovi modelli
# e rimuovere quelli deprecati, senza bisogno di riavviare.


def _start_auto_refresh():
    import threading

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
