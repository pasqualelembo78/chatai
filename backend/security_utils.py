import os
import time
import subprocess
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/tmp/chatai_uploads")

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_MIMES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/ogg", "audio/webm", "audio/x-m4a"}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}

EXT_TO_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
    ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}

DANGEROUS_MIMES = {
    "application/x-dosexec",
    "application/x-msdownload",
    "application/vnd.android.package-archive",
    "application/x-sh",
    "application/x-csh",
    "application/x-www-form-urlencoded",
    "text/html",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "application/pdf",
    "image/svg+xml",
}

CLAMDSCAN_PATH = "clamdscan"
CLAMAV_TIMEOUT = 10

AUDIO_MAX_SIZE = 10 * 1024 * 1024
AUDIO_MIN_SAMPLE_RATE = 8000
AUDIO_MAX_SAMPLE_RATE = 48000
AUDIO_MAX_DURATION = 60

CLEANUP_AGE = 5 * 60


def _detect_mime(file_path):
    try:
        import magic
        m = magic.Magic(mime=True)
        return m.from_file(str(file_path)).lower()
    except ImportError:
        logger.warning("python-magic not installed, falling back to extension check")
        return None
    except Exception as e:
        logger.warning(f"MIME detection failed: {e}")
        return None


def validate_file_mime(file_path, expected_ext):
    if not os.path.isfile(file_path):
        return False, "File not found"
    actual = _detect_mime(file_path)
    if actual is None:
        logger.warning(f"MIME detection unavailable, trusting extension for {file_path}")
        return True, ""
    if actual in DANGEROUS_MIMES:
        return False, f"Tipo di file pericoloso rilevato: {actual}"
    expected_mime = EXT_TO_MIME.get(expected_ext.lower())
    if expected_mime and actual != expected_mime:
        if actual in ALLOWED_IMAGE_MIMES or actual in ALLOWED_AUDIO_MIMES:
            logger.info(f"MIME mismatch for {file_path}: declared={expected_mime}, actual={actual} — accepting")
            return True, ""
        return False, f"MIME mismatch: dichiarato {expected_mime}, reale {actual}"
    if actual not in ALLOWED_IMAGE_MIMES and actual not in ALLOWED_AUDIO_MIMES:
        return False, f"Tipo di file non consentito: {actual}"
    return True, ""


def scan_file(file_path):
    if not os.path.isfile(file_path):
        return True, ""
    try:
        result = subprocess.run(
            [CLAMDSCAN_PATH, "--no-summary", str(file_path)],
            capture_output=True, text=True, timeout=CLAMAV_TIMEOUT
        )
        if result.returncode == 0:
            return True, ""
        elif "FOUND" in result.stdout:
            infected = result.stdout.strip()
            logger.warning(f"ClamAV rilevato: {infected}")
            return False, f"File infetto: {infected}"
        elif result.returncode == 2:
            logger.warning(f"ClamAV error (returncode 2): {result.stderr}")
            return True, ""
        else:
            logger.warning(f"ClamAV scan error: {result.stderr}")
            return True, ""
    except FileNotFoundError:
        logger.warning("clamdscan not found, skipping antivirus scan")
        return True, ""
    except subprocess.TimeoutExpired:
        logger.warning(f"ClamAV scan timed out after {CLAMAV_TIMEOUT}s")
        return True, ""
    except Exception as e:
        logger.warning(f"ClamAV scan exception: {e}")
        return True, ""


def strip_exif(image_path):
    try:
        from PIL import Image
        img = Image.open(image_path)
        data = list(img.getdata())
        img_clean = Image.new(img.mode, img.size)
        img_clean.putdata(data)
        img_clean.save(image_path, format=img.format)
        logger.info(f"EXIF stripped from {image_path}")
        return True
    except ImportError:
        logger.warning("Pillow not installed, cannot strip EXIF")
        return False
    except Exception as e:
        logger.warning(f"EXIF strip failed: {e}")
        return False


def get_audio_properties(file_path):
    try:
        import soundfile as sf
        info = sf.info(str(file_path))
        return {
            "duration": info.duration,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
        }
    except Exception:
        try:
            import wave
            with wave.open(str(file_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return {
                    "duration": frames / rate if rate > 0 else 0,
                    "sample_rate": rate,
                    "channels": wf.getnchannels(),
                    "format": "WAV",
                }
        except Exception:
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_streams", str(file_path)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    import json as _json
                    data = _json.loads(result.stdout)
                    for s in data.get("streams", []):
                        if s.get("codec_type") == "audio":
                            duration = float(s.get("duration", 0))
                            rate = int(s.get("sample_rate", 0))
                            return {
                                "duration": duration,
                                "sample_rate": rate,
                                "channels": s.get("channels", 0),
                                "format": s.get("codec_name", ""),
                            }
            except Exception:
                pass
            return None


def validate_audio_duration(file_path, max_seconds=AUDIO_MAX_DURATION):
    props = get_audio_properties(file_path)
    if props is None:
        logger.warning(f"Cannot determine audio duration for {file_path}")
        return True, ""
    if props["duration"] > max_seconds:
        return False, f"Audio troppo lungo: {props['duration']:.0f}s (massimo {max_seconds}s)"
    return True, ""


def validate_audio_sample_rate(file_path):
    props = get_audio_properties(file_path)
    if props is None:
        logger.warning(f"Cannot determine audio sample rate for {file_path}")
        return True, ""
    rate = props["sample_rate"]
    if rate < AUDIO_MIN_SAMPLE_RATE or rate > AUDIO_MAX_SAMPLE_RATE:
        return False, f"Frequenza di campionamento non valida: {rate}Hz (richiesto {AUDIO_MIN_SAMPLE_RATE}-{AUDIO_MAX_SAMPLE_RATE}Hz)"
    return True, ""


def nsfw_check_image(image_path, threshold=0.7):
    try:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            logger.warning("Gemini key not set, skipping NSFW check")
            return True, ""

        import base64 as _b64
        with open(image_path, "rb") as f:
            b64_data = _b64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime = EXT_TO_MIME.get(ext, "image/jpeg")

        import requests
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": "Analizza questa immagine e rispondi SOLO con un JSON. "
                                "Campi: safe (bool), reason (string se unsafe), categories (lista stringhe). "
                                "safe=true se l'immagine NON contiene nudità, violenza estesa, armi, droga, sangue, "
                                "contenuti sessuali espliciti, pedopornografia. "
                                "safe=false altrimenti. Sii severo: ogni dubbio → safe=false."
                    },
                    {"inlineData": {"mimeType": mime, "data": b64_data}}
                ]
            }]
        }
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
            json=payload, timeout=15
        )
        if resp.status_code == 200:
            text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if text:
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    import json as _json
                    result = _json.loads(json_match.group(0))
                    if not result.get("safe", True):
                        reason = result.get("reason", "Contenuto non sicuro")
                        categories = result.get("categories", [])
                        logger.warning(f"NSFW detected in {image_path}: {reason} ({categories})")
                        return False, reason
            return True, ""
        logger.error(f"Gemini NSFW error: {resp.status_code}")
        return True, ""
    except Exception as e:
        logger.warning(f"NSFW check failed: {e}")
        return True, ""


def nsfw_check_text(text):
    """Filtra SOLO contenuti di pedopornografia.
    Tutto il resto (sesso tra adulti, erotica, linguaggio esplicito) è permesso."""
    text_lower = text.lower()

    # 1. Famiglia "pedo-": pedofilia, pedofilo, pedopornografia, ecc.
    if re.search(r'\bpedo\w*\b|\bpedofil\w*\b', text_lower):
        logger.warning("Keyword filter triggered (pedo root)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    # 2. Loli/shota (anime/manga erotici con personaggi bambino)
    if re.search(r'\b(loli|shota|lolicon|shotacon)\b', text_lower):
        logger.warning("Keyword filter triggered (loli/shota)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    # 3. Child porn / kiddy porn (en)
    if re.search(r'\b(child\s*(porn|porno|nude|abuse)|kidd(y|ie)\s*(porn|porno|nude|sex)|csa\b|cp\b)', text_lower):
        logger.warning("Keyword filter triggered (child porn en)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    # 4. Teen + espliciti (en)
    if re.search(r'\bteen\s*(s)?\s*(sex|nude|nudes|porn|porno|fuck|cock|blowjob|pussy|hentai|anal|creampie)\b', text_lower):
        logger.warning("Keyword filter triggered (teen + sex en)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    # 5. Underage + espliciti (en)
    if re.search(r'\bunder\s*age\s*(sex|nude|nudes|porn|porno|fuck|cock|blowjob|pussy|hentai|anal)', text_lower):
        logger.warning("Keyword filter triggered (underage + sex en)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    # 6. Termine di "minore" vicino (entro ~40 caratteri) a termine sessuale esplicito
    minor_words = r'(minorenne|minorenn\w*|bambin[oi]|bambin[ai]|ragazzin[oi]|ragazzin[ai]|fanciull\w*|piccol\w*|neonato|neonata|underage|child|kids?)'
    sex_words = r'(nud[oaioy]|nudes?|porno?|sessual\w*|erotico?|scopare|sbora|sborra|sesso\s*orale|sesso\s*anale|fuck|cock|blowjob|pussy|hentai|anal|creampie|violenta|stupro|seduttrice|sedurre)'
    pattern = rf'({minor_words}).{{0,40}}?({sex_words})|({sex_words}).{{0,40}}?({minor_words})'
    if re.search(pattern, text_lower, re.DOTALL):
        logger.warning("Keyword filter triggered (minor + sex words proximity)")
        return False, "Testo rifiutato: contenuti di pedopornografia non consentiti"

    return True, ""


def secure_save_upload(file_storage, prefix="upload"):
    os.makedirs(str(UPLOAD_DIR), exist_ok=True)
    ext = os.path.splitext(file_storage.filename)[1].lower()
    timestamp = int(time.time())
    rand = os.urandom(4).hex()
    filename = f"{prefix}_{timestamp}_{rand}"
    path = str(UPLOAD_DIR / filename)
    file_storage.save(path)
    os.chmod(path, 0o600)
    return path, ext


def cleanup_old_files():
    now = time.time()
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > CLEANUP_AGE:
            try:
                f.unlink()
                logger.debug(f"Cleaned up: {f}")
            except Exception:
                pass
