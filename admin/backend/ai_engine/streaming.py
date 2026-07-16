import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

STREAM_STOP_FLAGS = {}


def _stream_stop_requested(user_id):
    return STREAM_STOP_FLAGS.get(user_id, False)


def _stream_clear_stop(user_id):
    STREAM_STOP_FLAGS.pop(user_id, None)


def _stream_openai_compatible(url, headers, payload, model, timeout=120):
    payload = {**payload, "stream": True, "model": model}
    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
        resp.encoding = "utf-8"
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
    from ai_engine.registry import _get_user_api_key
    key = os.environ.get("GEMINI_API_KEY", "")
    if user_id:
        k = _get_user_api_key(user_id, "gemini")
        if k:
            key = k
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
        body = {
            "contents": chat,
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={key}&alt=sse",
            json=body, stream=True, timeout=60
        )
        resp.encoding = "utf-8"
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
    from ai_engine.registry import _get_user_api_key
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if user_id:
        k = _get_user_api_key(user_id, "anthropic")
        if k:
            key = k
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
        resp.encoding = "utf-8"
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
    from ai_engine.providers.ollama import OLLAMA_URL, OLLAMA_OPTIONS, _ensure_ollama
    OLLAMA_STREAM_OPTIONS = {**OLLAMA_OPTIONS, "num_predict": 200}
    if not _ensure_ollama():
        return
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": messages, "options": OLLAMA_STREAM_OPTIONS, "stream": True},
            stream=True, timeout=120
        )
        resp.encoding = "utf-8"
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
    def wrapper(messages, model, user_id=None):
        result = gen_func(messages, model, user_id=user_id)
        if result:
            yield result
    return wrapper


def get_ai_response_stream(messages, user_id=None, force_provider=None):
    from ai_engine.registry import PROVIDERS, user_providers, DEFAULT_PROVIDER, DEFAULT_MODEL
    from ai_engine.chain import _provider_ready, FREE_MODEL_CHAIN, _should_skip_heavy_model
    from ai_engine.config import CHAT_PROVIDER, GROQ_CHAT_MODELS, _chat_key_rotator
    from ai_engine.ensemble import ENSEMBLE_ENABLED, _ensemble_parallel_stream
    from ai_engine.response import get_ai_response

    if force_provider and force_provider in PROVIDERS and _provider_ready(force_provider):
        fp = PROVIDERS[force_provider]
        fmodel = fp.get("models", [{}])[0].get("id") if fp.get("models") else None
        if fmodel:
            stream_fn = fp.get("generate_stream") or fp.get("generate")
            try:
                if stream_fn == fp.get("generate"):
                    result = stream_fn(messages, fmodel, user_id=user_id)
                    if result:
                        logger.info(f"Risposta AI da {force_provider}/{fmodel} (force_provider, sync)")
                        yield result, force_provider, fmodel
                        return
                else:
                    for token in stream_fn(messages, fmodel, user_id=user_id):
                        yield token, force_provider, fmodel
                    logger.info(f"Risposta AI da {force_provider}/{fmodel} (force_provider, stream)")
                    return
            except Exception as e:
                logger.warning(f"  force_provider {force_provider}/{fmodel} errore ({e}), fallback catena normale")

    if ENSEMBLE_ENABLED:
        ensemble_gen = _ensemble_parallel_stream(messages, user_id=user_id)
        first_token = None
        for token, pid, model in ensemble_gen:
            if first_token is None:
                first_token = token
                logger.info(f"Ensemble streaming response da {pid}/{model}")
            yield token, pid, model
        if first_token is not None:
            return

    chain = []

    if CHAT_PROVIDER == "groq" and "groq" in PROVIDERS and _provider_ready("groq"):
        for model in GROQ_CHAT_MODELS:
            chain.append(("groq", model))

    if CHAT_PROVIDER == "local" and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        chain.append((DEFAULT_PROVIDER, DEFAULT_MODEL))

    force_first = os.environ.get("FORCE_LOCAL_FIRST", "0") == "1"
    if force_first and DEFAULT_PROVIDER in PROVIDERS and _provider_ready(DEFAULT_PROVIDER):
        if (DEFAULT_PROVIDER, DEFAULT_MODEL) not in chain:
            chain.append((DEFAULT_PROVIDER, DEFAULT_MODEL))

    if user_id and user_id in user_providers:
        cfg = user_providers[user_id]
        pid = cfg.get("provider")
        model = cfg.get("model")
        if pid and model and pid in PROVIDERS and (pid, model) not in chain:
            chain.append((pid, model))

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
    text, pid, model = get_ai_response(messages, user_id=user_id)
    if text:
        yield text, pid, model
