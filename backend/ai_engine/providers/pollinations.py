import os
import logging

from ai_engine.registry import register_provider

logger = logging.getLogger(__name__)

POLLINATIONS_MODELS = [
    {"id": "openai", "name": "GPT-4o Mini (via Pollinations)", "quality": "alta", "costo": "gratuito"},
    {"id": "gemini", "name": "Gemini Flash (via Pollinations)", "quality": "alta", "costo": "gratuito"},
    {"id": "mistral", "name": "Mistral (via Pollinations)", "quality": "buona", "costo": "gratuito"},
    {"id": "deepseek", "name": "DeepSeek (via Pollinations)", "quality": "alta", "costo": "gratuito"},
]


def _pollinations_generate(messages, model, uid=None):
    import requests
    import urllib.parse
    key = os.environ.get("POLLINATIONS_API_KEY", "")
    try:
        prompt = messages[-1]["content"] if messages else ""
        system_msg = ""
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
                break
        if system_msg:
            prompt = f"{system_msg}\n\n{prompt}"

        encoded = urllib.parse.quote(prompt)
        params = {"model": model, "seed": 42}
        if key:
            params["token"] = key

        resp = requests.get(
            f"https://text.pollinations.ai/{encoded}",
            params=params, timeout=60,
        )
        resp.encoding = "utf-8"
        if resp.status_code == 200 and resp.text.strip():
            return resp.text.strip()
        logger.error(f"Pollinations error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Pollinations request failed: {e}")
        return None


def _pollinations_generate_stream(messages, model, uid=None):
    import requests
    import urllib.parse
    key = os.environ.get("POLLINATIONS_API_KEY", "")
    prompt = messages[-1]["content"] if messages else ""
    system_msg = ""
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
            break
    if system_msg:
        prompt = f"{system_msg}\n\n{prompt}"

    encoded = urllib.parse.quote(prompt)
    params = {"model": model, "seed": 42, "stream": "true"}
    if key:
        params["token"] = key

    try:
        resp = requests.get(
            f"https://text.pollinations.ai/{encoded}",
            params=params, stream=True, timeout=120,
        )
        if resp.status_code != 200:
            logger.error(f"Pollinations stream error: {resp.status_code}")
            return
        for line in resp.iter_lines(decode_unicode=True):
            if line:
                yield line, "pollinations", model
    except Exception as e:
        logger.error(f"Pollinations stream failed: {e}")


register_provider({
    "id": "pollinations",
    "name": "Pollinations AI (API gratuita)",
    "description": "Modelli gratuiti via Pollinations. Nessuna API key richiesta.",
    "models": POLLINATIONS_MODELS,
    "needs_key": False,
    "has_key": lambda: True,
    "free": True,
    "website": "https://pollinations.ai",
    "generate": _pollinations_generate,
    "generate_stream": _pollinations_generate_stream,
    "default_model": "openai",
})
