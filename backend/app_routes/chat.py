import os
import re
import tempfile
import logging

from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from characters import get_character, list_characters, get_categories
from storage import is_content_unlocked, flag_user
import audio_utils
import image_utils
import security_utils
from auth_fastapi import AuthUser, jwt_required
from chat_engine import process_message

from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)


def _send_alert(message):
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if telegram_bot_token and telegram_chat_id:
        try:
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage",
                json={"chat_id": telegram_chat_id, "text": f"[ChatAI] {message[:1000]}", "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")


def _check_character_access(user_id, character):
    if not user_id:
        return False
    category_id = character.get("category", "")
    for cat in get_categories():
        if cat["id"] == category_id:
            mvc_cost = cat.get("mvc_cost", 0)
            if mvc_cost > 0 and not is_content_unlocked(user_id, "category", category_id):
                return False
            break
    return True


class ChatRequest(BaseModel):
    character: Optional[str] = None
    text: str = ""
    username: str = "Utente"
    memory_context: Optional[list] = None
    user_memory: Optional[dict] = None
    character_data: Optional[dict] = None
    image: str = ""
    image_mime: str = "image/jpeg"
    is_favorite: bool = False
    client_storage: bool = False
    relationship_state: Optional[dict] = None
    personality_state: Optional[dict] = None
    evolution_state: Optional[dict] = None
    shifts: Optional[list] = None
    summaries: Optional[list] = None


class TtsRequest(BaseModel):
    text: str = ""
    character_id: str = ""


@router.post("/chat")
@limiter.limit("60/minute")
async def api_chat(request: Request, body: ChatRequest, user: AuthUser = Depends(jwt_required)):
    chars = list_characters()
    character_id = body.character or (chars[0]["id"] if chars else None)
    text = body.text
    username = body.username

    client_state = {
        "relationship": body.relationship_state,
        "personality": body.personality_state,
        "evolution": body.evolution_state,
        "shifts": body.shifts,
        "summaries": body.summaries,
    }

    if not text and not body.image:
        raise HTTPException(400, "text or image required")
    if text:
        ok, msg = security_utils.nsfw_check_text(text)
        if not ok:
            raise HTTPException(400, msg)

    char = get_character(character_id)
    if char and not _check_character_access(user.user_id, char):
        raise HTTPException(403, "premium_required")

    from storage import check_and_count_message, refund_message
    from content_safety import moderate_output
    allowed, status = check_and_count_message(user.user_id)
    if not allowed:
        raise HTTPException(
            429,
            {
                "error": "daily_limit_reached",
                "limit": status["limit"],
                "used": status["used"],
                "unlock_cost": status["unlock_cost"],
                "message": f"Limite giornaliero di messaggi raggiunto ({status['limit']}). "
                           f"Sblocca messaggi illimitati con {status['unlock_cost']} MVC.",
            },
        )

    result = process_message(user.user_id, character_id, text, username,
                             memory_context=body.memory_context,
                             user_memory=body.user_memory,
                             character_data=body.character_data,
                             image_base64=body.image,
                             image_mime=body.image_mime,
                             client_storage=body.client_storage,
                             client_state=client_state,
                             is_favorite=body.is_favorite)
    if not result:
        refund_message(user.user_id)
        raise HTTPException(404, "character not found")

    # Blocco lato server garantito (conformità Google Play): anche se il modello
    # producesse contenuti espliciti, l'output viene filtrato e sostituito.
    ai_text, _blocked = moderate_output(result["ai_text"])
    result["ai_text"] = ai_text

    resp = {
        "response": result["ai_text"],
        "emotion": result["emotion"],
        "emotion_intensity": result["intensity"],
        "ai_provider": result.get("ai_provider", ""),
        "ai_model": result.get("ai_model", ""),
        "character_id": character_id,
        "character_name": result["character"]["name"],
    }
    mem_updates = result.get("memory_updates", {})
    if mem_updates:
        resp["memory_updates"] = mem_updates
    evo_updates = result.get("evo_updates", {})
    if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
        resp["evo_updates"] = evo_updates
    if body.client_storage:
        cs = result.get("client_state", {})
        if cs:
            resp["client_state"] = cs
    return resp


@router.post("/transcribe")
@limiter.limit("10/minute")
async def api_transcribe(request: Request, audio: UploadFile = File(...), user: AuthUser = Depends(jwt_required)):
    if not audio.filename or audio.filename.strip() == "":
        raise HTTPException(400, "audio file required")
    if not audio_utils.allowed_audio_file(audio.filename):
        raise HTTPException(400, "formato audio non supportato")

    content = await audio.read()
    path = tempfile.mktemp(suffix=os.path.splitext(audio.filename)[1])
    with open(path, "wb") as f:
        f.write(content)

    ok, msg = security_utils.validate_file_mime(path, os.path.splitext(audio.filename)[1])
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"⚠️ File infetto rilevato — user={user.user_id} detail={msg}")
        raise HTTPException(400, msg)

    ok, msg = security_utils.validate_audio_duration(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.validate_audio_sample_rate(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    text = audio_utils.transcribe_audio(path)
    try: os.remove(path)
    except Exception: pass
    if not text:
        raise HTTPException(500, detail="transcription failed")
    return {"text": text}


@router.post("/tts")
async def api_tts(body: TtsRequest, user: AuthUser = Depends(jwt_required)):
    if not body.text:
        raise HTTPException(400, "text required")
    if not is_content_unlocked(user.user_id, "feature", "premium_voice"):
        raise HTTPException(403, "premium_voice_required")
    char = get_character(body.character_id) if body.character_id else None
    voice_profile = audio_utils.get_voice_profile(char) if char else {"model": "it_IT-riccardo-medium", "speed": 1.0, "pitch": 1.0}
    output_path = audio_utils.text_to_speech(body.text, voice_profile)
    if not output_path:
        raise HTTPException(500, "TTS generation failed")

    def generate():
        with open(output_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk
        try: os.remove(output_path)
        except Exception: pass

    return StreamingResponse(generate(), media_type="audio/wav",
                             headers={"Content-Disposition": "inline; filename=response.wav"})


@router.post("/upload-image")
@limiter.limit("10/minute")
async def api_upload_image(request: Request, image: UploadFile = File(...), user: AuthUser = Depends(jwt_required)):
    if not image.filename or image.filename.strip() == "":
        raise HTTPException(400, "image file required")
    if not image_utils.validate_image(image.filename):
        raise HTTPException(400, "invalid image format (jpg/png/webp only)")

    content = await image.read()
    if len(content) > image_utils.MAX_IMAGE_SIZE:
        raise HTTPException(400, "image too large (max 10MB)")

    ext = os.path.splitext(image.filename)[1]
    path = tempfile.mktemp(suffix=ext)
    with open(path, "wb") as f:
        f.write(content)

    ok, msg = security_utils.validate_file_mime(path, ext)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"⚠️ Immagine infetta rilevata — user={user.user_id} detail={msg}")
        raise HTTPException(400, msg)

    ok, msg = security_utils.nsfw_check_image(path)
    if not ok:
        flag_user(user.user_id, f"NSFW image: {msg}", "image", msg, "high")
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"🔞 NSFW rilevato — user={user.user_id} reason={msg}")
        raise HTTPException(400, "Contenuto non appropriato")

    security_utils.strip_exif(path)
    path = image_utils.resize_image(path)
    b64 = image_utils.image_to_base64(path)
    mime = security_utils.EXT_TO_MIME.get(ext, "image/jpeg")
    try: os.remove(path)
    except Exception: pass
    return {"base64": b64, "mime": mime}


@router.get("/static/videos/{filename}")
async def api_video(filename: str):
    if not re.match(r"^[a-f0-9]{32}\.mp4$", filename):
        raise HTTPException(400, "invalid")
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "videos", filename)
    if not os.path.isfile(video_path):
        raise HTTPException(404, "not found")
    return FileResponse(video_path, media_type="video/mp4")
