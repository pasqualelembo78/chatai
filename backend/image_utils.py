import os
import time
import base64
import logging
from pathlib import Path
import security_utils

logger = logging.getLogger(__name__)

UPLOAD_DIR = security_utils.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = security_utils.ALLOWED_IMAGE_EXTS
ALLOWED_IMAGE_MIMES = security_utils.ALLOWED_IMAGE_MIMES
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_DIMENSION = 1920


def validate_image(filename):
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def save_upload_image(file_storage):
    path, ext = security_utils.secure_save_upload(file_storage, prefix="img")
    return path


def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("utf-8")


def resize_image(image_path, max_dim=MAX_DIMENSION):
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not installed, skipping resize")
        return image_path

    try:
        img = Image.open(image_path)
        if img.width <= max_dim and img.height <= max_dim:
            return image_path

        ratio = min(max_dim / img.width, max_dim / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        ext = os.path.splitext(image_path)[1].lower()
        fmt = "JPEG"
        if ext == ".png":
            fmt = "PNG"
        elif ext == ".webp":
            fmt = "WEBP"

        new_path = image_path.replace(".", "_resized.")
        if new_path == image_path:
            new_path = image_path + "_resized.jpg"
        img.save(new_path, fmt)
        os.replace(new_path, image_path)
        return image_path
    except Exception as e:
        logger.warning(f"Image resize failed: {e}")
        return image_path


def _gemini_key():
    return os.environ.get("GEMINI_API_KEY", "")


def describe_image(base64_data, mime_type):
    key = _gemini_key()
    if not key:
        logger.warning("Gemini API key not set, cannot describe image")
        return None

    try:
        import requests

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Descrivi brevemente questa immagine in italiano. Cosa vedi? Rispondi in massimo 2 frasi."},
                    {"inlineData": {"mimeType": mime_type, "data": base64_data}}
                ]
            }]
        }

        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
            json=payload,
            timeout=30
        )

        if resp.status_code == 200:
            candidates = resp.json().get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if text:
                    return text.strip()
        logger.error(f"Gemini describe error: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Gemini describe request failed: {e}")
        return None
