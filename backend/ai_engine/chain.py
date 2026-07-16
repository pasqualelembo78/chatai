import os
import shutil
import logging

from ai_engine.registry import PROVIDERS, DEFAULT_PROVIDER, DEFAULT_MODEL
from ai_engine.config import _cached_fetch, _chat_key_rotator

logger = logging.getLogger(__name__)

RAM_GUARDIAN_MIN_FREE_GB = float(os.environ.get("RAM_GUARDIAN_MIN_FREE_GB", "1.5"))

HEAVY_LOCAL_MODELS = {
    "qwen2.5:7b": 5.0,
    "llama3.1:8b": 5.0,
    "mistral:7b": 4.5,
    "gemma2:9b": 6.0,
    "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M": 5.0,
    "hf.co/huihui-ai/Qwen2.5-7B-Instruct-abliterated-v2-GGUF:Q4_K_M": 5.0,
    "mixtral:8x7b": 27.0,
    "qwen2.5:14b": 9.0,
    "mistral-nemo:12b": 8.0,
    "qwen2.5:32b": 20.0,
    "deepseek-r1:7b": 5.0,
    "llama3.3:70b": 40.0,
    "llama3.1:70b": 40.0,
    "qwen2.5:72b": 45.0,
    "deepseek-r1:70b": 43.0,
}

FREE_MODEL_CHAIN = []


def _check_ram_available():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.available / (1024 ** 3), vm.total / (1024 ** 3)
    except ImportError:
        pass
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
    free_gb, _ = _check_ram_available()
    ok = free_gb >= (required_gb + RAM_GUARDIAN_MIN_FREE_GB)
    if not ok:
        logger.info(f"  ram-guardian: libera {free_gb:.1f} GB, serve {required_gb:.1f}+{RAM_GUARDIAN_MIN_FREE_GB} GB → saldo")
    return ok


def _should_skip_heavy_model(model_id):
    required = HEAVY_LOCAL_MODELS.get(model_id)
    if not required:
        return False
    return not _ram_ok_for_model(required)


def _discover_groq_models():
    from ai_engine.config import _cached_fetch
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
    available = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
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
    from ai_engine.config import _cached_fetch
    data = _cached_fetch(
        "https://openrouter.ai/api/v1/models",
        cache_key="or_models"
    )
    if not data:
        return []
    available = {}
    for m in data.get("data", []):
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not mid:
            continue
        pricing = m.get("pricing", {})
        prompt_cost = float(pricing.get("prompt", "999"))
        completion_cost = float(pricing.get("completion", "999"))
        # Mantiene solo modelli chat (output testuale), esclude audio/immagini/musica
        modality = m.get("architecture", {}).get("modality", "text->text")
        out_modality = modality.split("->")[-1]
        if "text" not in out_modality or out_modality != "text":
            continue
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
    from ai_engine.config import _cached_fetch
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


def rebuild_free_model_chain():
    from ai_engine.providers.ollama import _ollama_available
    chain = []

    from ai_engine.providers.ollama import OLLAMA_MODELS as _OLLAMA_MODELS
    try:
        _ollama_sorted = sorted(
            _OLLAMA_MODELS,
            key=lambda m: float(str(m.get("size", "0")).replace("GB", "").strip() or 0)
        )
    except Exception:
        _ollama_sorted = _OLLAMA_MODELS
    for m in _ollama_sorted:
        chain.append(("ollama", m["id"]))

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

    # Auto-inclusione di tutti i provider free pronti (chiave presente / keyless)
    # aggiunge es. HuggingFace, Pollinations, Cloudflare, llamacpp senza硬编码
    _already = {pid for pid, _ in chain}
    for pid, provider in PROVIDERS.items():
        if pid in ("ollama", "openrouter", "groq", "gemini", "mistral", "github"):
            continue
        if not provider.get("free", False):
            continue
        if not provider.get("has_key", lambda: False)():
            continue
        for m in provider.get("models", []):
            chain.append((pid, m["id"]))

    global FREE_MODEL_CHAIN
    FREE_MODEL_CHAIN = chain
    import ai_engine as _ae
    _ae.FREE_MODEL_CHAIN = chain
    logger.info(f"Catena modelli dinamica: {len(chain)} entry")
    for p, m in chain:
        logger.info(f"  {p}/{m}")
    return chain


def _provider_ready(pid):
    if pid == "ollama":
        from ai_engine.providers.ollama import _ollama_available
        return _ollama_available()
    provider = PROVIDERS.get(pid)
    if not provider:
        logger.warning(f"  auto: provider '{pid}' non registrato")
        return False
    ready = provider.get("has_key", lambda: False)()
    if not ready:
        logger.warning(f"  auto: {pid} non pronto (chiave API mancante o env var non trovata)")
    return ready
