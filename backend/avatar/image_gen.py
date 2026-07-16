"""Image generation functions — Pollinations, Pexels, free providers, HF."""

import time
import urllib.parse

from avatar.config import API_URL
from avatar.env import pexels_rotator
from avatar.gender import build_pexels_keyword
from avatar.prompts import get_negative_prompt


def generate_image_pollinations(prompt, char_id, api_key=None, negative_prompt=None):
    """Genera immagine full-body con Pollinations.AI."""
    import requests

    encoded_prompt = urllib.parse.quote(prompt)
    seed = abs(hash(char_id)) % 10000

    params = f"width=512&height=768&seed={seed}&model=flux&nologo=true&private=true"

    if negative_prompt:
        encoded_neg = urllib.parse.quote(negative_prompt)
        params += f"&negative_prompt={encoded_neg}"

    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?{params}"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=120)
            if resp.status_code == 200:
                return resp.content
            elif resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate limit Pollinations, attesa {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  Errore Pollinations.AI: HTTP {resp.status_code}")
                break
        except requests.exceptions.Timeout:
            print(f"  Timeout Pollinations (tentativo {attempt+1}/3)")
            time.sleep(5)
        except Exception as e:
            print(f"  Errore Pollinations.AI: {e}")
            break

    return None


def generate_image_pexels(keyword, api_key, orientation="portrait"):
    """Cerca e scarica foto reali da Pexels."""
    import requests

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {
        "query": keyword,
        "per_page": 10,
        "orientation": orientation
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get('photos', [])

            if photos:
                import random
                photo = random.choice(photos[:5])
                photo_url = photo.get('src', {}).get('large', '')
                photographer = photo.get('photographer', 'Unknown')

                print(f"  Pexels: trovata foto di {photographer}")

                img_resp = requests.get(photo_url, timeout=60)
                if img_resp.status_code == 200:
                    return img_resp.content
        else:
            print(f"  Errore Pexels: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  Errore Pexels: {e}")

    return None


def generate_image_free(model_id, char_id, char_name, prompt=None, api_key=None, negative_prompt=None, char=None, original_model=None):
    """Genera avatar usando API gratuite con fallback automatico."""
    import requests

    if not negative_prompt:
        negative_prompt = get_negative_prompt()

    if pexels_rotator and model_id in ["free", "pexels"] and original_model != "pollinations":
        keyword = build_pexels_keyword(char_name, prompt, char_id, char)

        attempts = 0
        max_attempts = len(pexels_rotator.keys) * 2

        while attempts < max_attempts:
            pexels_key = pexels_rotator.get_current_key()

            if not pexels_key:
                pexels_key = pexels_rotator.wait_for_available_key(max_wait=300)
                if not pexels_key:
                    print(f"  ❌ Timeout: nessuna key Pexels disponibile dopo 5 minuti")
                    break

            result = generate_image_pexels(keyword, pexels_key)
            if result:
                pexels_rotator.report_success(pexels_key)
                return result

            pexels_rotator.report_failure(pexels_key, retry_after=60)
            attempts += 1

    if model_id in ["free", "pollinations"]:
        if not prompt:
            prompt = (
                f"Candid photo of a young person, "
                f"natural indoor lighting, realistic skin texture, "
                f"casual pose, shot on iPhone"
            )
        result = generate_image_pollinations(prompt, char_id, api_key, negative_prompt)
        if result:
            return result

    if model_id in ["free", "pexels", "pollinations", "tpde"]:
        try:
            url = f"https://thispersondoesnotexist.com/?seed={abs(hash(char_id))}"
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 10000:
                return resp.content
        except Exception as e:
            print(f"  Fallback TPDE fallito: {e}")

    if model_id in ["free", "pexels", "pollinations", "pravatar"]:
        try:
            url = f"https://i.pravatar.cc/512?u={char_id}"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except Exception as e:
            print(f"  Fallback PrAvatar fallito: {e}")

    if model_id in ["free", "pexels", "pollinations", "dicebear"]:
        try:
            styles = ["adventurer", "avataaars", "big-ears", "fun-emoji", "lorelei"]
            style_idx = abs(hash(char_id)) % len(styles)
            style = styles[style_idx]
            url = f"https://api.dicebear.com/7.x/{style}/png?seed={char_id}&size=512"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except Exception as e:
            print(f"  Fallback DiceBear fallito: {e}")

    return None


def generate_image(token, model_id, prompt, retries=3):
    """Genera immagine tramite HuggingFace Inference API."""
    import requests
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": "cartoon, anime, illustration, low quality, blurry, distorted face, bad anatomy, extra fingers",
            "guidance_scale": 7.5,
            "num_inference_steps": 28,
        },
    }
    for attempt in range(retries):
        print(f"  [tentativo {attempt + 1}/{retries}] Generazione...")
        resp = requests.post(API_URL + model_id, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.content
        if resp.status_code == 503:
            wait = int(resp.headers.get("x-wait-time", 20))
            print(f"  Modello in caricamento, attesa {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            print("  Rate limit, attesa 30s...")
            time.sleep(30)
            continue
        print(f"  Errore {resp.status_code}: {resp.text[:200]}")
        break
    return None
