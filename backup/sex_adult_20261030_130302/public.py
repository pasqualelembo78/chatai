from typing import Optional

from fastapi import APIRouter, Query, Depends, HTTPException

from characters import get_character, get_categories
from storage import get_user_preferences, get_user_unlocks
from ai_engine import get_providers
import ai_engine
import audio_utils
from auth_fastapi import jwt_optional, AuthUser

router = APIRouter()


@router.get("/")
async def index():
    return {
        "status": "running",
        "endpoints": {
            "register": "/auth/register (POST)",
            "login": "/auth/login (POST)",
            "refresh": "/auth/refresh (POST)",
            "logout": "/auth/logout (POST)",
            "providers": "/providers",
            "available_models": "/available-models",
            "categories": "/categories",
            "characters": "/characters",
            "character_detail": "/characters/<id>",
            "search": "/characters/search?q=<query>",
            "adult": "/characters/adult",
            "chat": "/chat (POST)",
            "transcribe": "/transcribe (POST)",
            "tts": "/tts (POST, JSON)",
            "voice_profile": "/voice-profile/<character_id>",
            "upload_image": "/upload-image (POST)",
            "config": "/config (GET/POST)",
            "memory": "/memory (GET/POST/DELETE)",
            "evolution": "/evolution?character_id=Y",
            "conversations": "/conversations",
            "premium": "/premium/check",
            "stream_chat": "Socket.IO con token auth"
        }
    }


@router.get("/categories")
async def api_categories(
    adult: str = Query("false"),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    is_adult = adult.lower() == "true"
    if not is_adult and user:
        try:
            prefs = get_user_preferences(user.user_id)
            is_adult = prefs.get("show_adult", False)
        except Exception:
            pass
    cats = get_categories()
    unlocks = set()
    if user:
        try:
            prefs = get_user_preferences(user.user_id)
            unlocks = {u["content_id"] for u in get_user_unlocks(user.user_id) if u["content_type"] == "category"}
        except Exception:
            pass
    result = []
    for c in cats:
        entry = dict(c)
        mvc_cost = c.get("mvc_cost", 0)
        entry["locked"] = mvc_cost > 0 and c["id"] not in unlocks
        from characters import get_characters_by_category
        try:
            entry["character_count"] = len(get_characters_by_category(c["id"]))
        except Exception:
            entry["character_count"] = 0
        result.append(entry)
    return result


@router.get("/providers")
async def api_providers():
    return get_providers()


@router.get("/available-models")
async def api_available_models():
    chain = ai_engine.FREE_MODEL_CHAIN
    grouped = {}
    seen = set()
    for pid, model in chain:
        if pid not in grouped:
            grouped[pid] = []
        key = f"{pid}/{model}"
        if key not in seen:
            seen.add(key)
            name = model
            provider = ai_engine.PROVIDERS.get(pid)
            if provider:
                for m in provider.get("models", []):
                    if m["id"] == model:
                        name = m.get("name", model)
                        break
            grouped[pid].append({"id": model, "name": name})
    return grouped


@router.get("/voice-profile/{character_id}")
async def api_voice_profile(character_id: str):
    char = get_character(character_id)
    if not char:
        raise HTTPException(404, "character not found")
    return audio_utils.get_voice_profile(char)


@router.get("/privacy")
async def api_privacy():
    return {
        "version": "1.0",
        "updated_at": "2026-07-06",
        "text": (
            "PRIVACY POLICY — ChatAI\n\n"
            "1. DATI RACCOLTI: username, email (se Google Sign-In), messaggi di chat, "
            "registrazioni audio (solo per trascrizione), immagini caricate (solo per descrizione AI).\n\n"
            "2. FINALITÀ: fornire il servizio di chat AI, migliorare i modelli di conversazione, "
            "assistenza tecnica.\n\n"
            "3. BASE GIURIDICA: consenso esplicito dell'utente (art. 6 GDPR).\n\n"
            "4. CONDIVISIONE: i dati NON vengono venduti a terzi. Le richieste AI vengono inviate "
            "a provider esterni (Groq, Google Gemini, OpenAI, ecc.) senza dati identificativi.\n\n"
            "5. CONSERVAZIONE: messaggi fino a 90 giorni. Log di audit fino a 365 giorni. "
            "I file audio/immagini vengono eliminati dopo 5 minuti.\n\n"
            "6. DIRITTI: accesso, rettifica, cancellazione (diritto all'oblio), limitazione, "
            "portabilità dei dati. Endpoint: GET /user/export, POST /user/delete.\n\n"
            "7. CONTATTI: per esercitare i tuoi diritti, contatta l'amministratore.\n\n"
            "8. MODIFICHE: la policy verrà aggiornata con preavviso di 30 giorni."
        )
    }
