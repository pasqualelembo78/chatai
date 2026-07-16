"""Environment loading, API key management, and rotator initialization."""

import os

from avatar.keys import KeyRotator, ProviderRotator
from avatar.config import ROOT, ENV_FILE

if os.path.isfile(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def get_api_keys(env_var, single_var=None):
    """Carica multiple keys da env (separate da virgola) o singola key."""
    keys = []
    multi_var = env_var + "S"
    multi_val = os.environ.get(multi_var, "")
    if multi_val:
        keys = [k.strip() for k in multi_val.split(",") if k.strip()]
    if not keys and single_var:
        single_val = os.environ.get(single_var, "")
        if single_val:
            keys = [single_val]
    return keys


groq_keys = get_api_keys("GROQ_API_KEY", "GROQ_API_KEY")
pexels_keys = get_api_keys("PEXELS_API_KEY", "PEXELS_API_KEY")

groq_rotator = KeyRotator(groq_keys, "Groq") if groq_keys else None
pexels_rotator = KeyRotator(pexels_keys, "Pexels") if pexels_keys else None

llm_provider_rotator = ProviderRotator()

for key in groq_keys:
    llm_provider_rotator.add_provider(
        name=f"Groq",
        api_key=key,
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1/chat/completions"
    )

gemini_key = os.environ.get("GEMINI_API_KEY", "")
if gemini_key:
    def gemini_headers(api_key):
        return {"Content-Type": "application/json", "x-goog-api-key": api_key}
    def gemini_payload(prompt, model, max_tokens, temperature):
        return {
            "model": "gemini-1.5-flash",
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}
        }
    llm_provider_rotator.add_provider(
        name="Google Gemini",
        api_key=gemini_key,
        model="gemini-1.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        headers_func=gemini_headers,
        payload_func=gemini_payload
    )

cerebras_key = os.environ.get("CEREBRAS_API_KEY", "")
if cerebras_key:
    llm_provider_rotator.add_provider(
        name="Cerebras",
        api_key=cerebras_key,
        model="llama-3.3-70b-versatile",
        base_url="https://api.cerebras.ai/v1/chat/completions"
    )

sambanova_key = os.environ.get("SAMBANOVA_API_KEY", "")
if sambanova_key:
    llm_provider_rotator.add_provider(
        name="SambaNova",
        api_key=sambanova_key,
        model="Meta-Llama-3.3-70B-Instruct",
        base_url="https://api.sambanova.ai/v1/chat/completions"
    )

mistral_key = os.environ.get("MISTRAL_API_KEY", "")
if mistral_key:
    llm_provider_rotator.add_provider(
        name="Mistral AI",
        api_key=mistral_key,
        model="mistral-large-latest",
        base_url="https://api.mistral.ai/v1/chat/completions"
    )
