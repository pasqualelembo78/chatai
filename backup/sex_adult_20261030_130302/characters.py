import os
from typing import Optional

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from characters import (
    get_character, get_characters_by_category, search_characters,
    get_adult_characters, get_categories, list_characters,
)
from storage import (
    is_user_premium, set_user_premium,
    create_user_character, get_user_characters, delete_user_character,
    get_user_unlocks, get_user_preferences, audit_log,
    set_verified_birth_year, is_age_verified, flag_user,
)
from storage.relationships import get_user_intimacies, describe_intimacy_level
from ai_engine import get_active_config, set_active, clear_model_cache, rebuild_free_model_chain, test_provider_connection
import ai_engine
from auth_fastapi import jwt_required, jwt_optional, AuthUser

router = APIRouter()

_DEFAULT_INTIMACY_CFG = {"threshold_refuse": 15, "threshold_accept": 50}


def _attach_intimacy(chars, user_id):
    """Arricchisce i personaggi con il livello di intimità dell'utente corrente.
    Ritorna NUOVE copie dei dict (non muta la cache globale dei personaggi)."""
    if not user_id:
        return chars
    intimacies = get_user_intimacies(user_id)
    out = []
    for c in chars:
        cc = dict(c)
        intimacy = int(intimacies.get(c.get("id"), 0))
        cfg = c.get("intimacy_config") or {}
        safe_cfg = {
            "threshold_refuse": cfg.get("threshold_refuse", 15),
            "threshold_accept": cfg.get("threshold_accept", 50),
        }
        cc["intimacy"] = intimacy
        cc["intimacy_label"] = describe_intimacy_level(intimacy, safe_cfg)
        out.append(cc)
    return out


class ConfigRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None


class TestRequest(BaseModel):
    provider: str = ""
    api_key: str = ""


class PremiumRequest(BaseModel):
    sku: str = ""
    purchase_token: str = ""


class CreateCharacterRequest(BaseModel):
    name: str = ""
    age: int = 0
    model_config = {"extra": "allow"}


@router.get("/config")
async def api_config(user: AuthUser = Depends(jwt_required)):
    return get_active_config(user_id=user.user_id)


@router.post("/config")
async def api_set_config(body: ConfigRequest, user: AuthUser = Depends(jwt_required)):
    if body.provider:
        set_active(user.user_id, body.provider, body.model)
    return {"status": "ok", "config": get_active_config(user_id=user.user_id)}


@router.post("/refresh-models")
async def api_refresh_models(user: AuthUser = Depends(jwt_required)):
    clear_model_cache()
    rebuild_free_model_chain()
    return {"status": "ok", "chain": [f"{p}/{m}" for p, m in ai_engine.FREE_MODEL_CHAIN]}


@router.post("/api/test")
async def api_test(body: TestRequest, user: AuthUser = Depends(jwt_required)):
    if not body.provider:
        raise HTTPException(400, "provider richiesto")
    success, message = test_provider_connection(body.provider, body.api_key)
    return {"success": success, "message": message}


@router.get("/premium/check")
async def api_premium_check(user: AuthUser = Depends(jwt_required)):
    return {"is_premium": is_user_premium(user.user_id)}


@router.post("/premium/activate")
async def api_premium_activate(body: PremiumRequest, request: Request, user: AuthUser = Depends(jwt_required)):
    set_user_premium(user.user_id, True, body.sku, body.purchase_token)
    audit_log(user.user_id, "premium.activate", f"sku={body.sku}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "is_premium": True}


@router.get("/avatars/{char_id}")
async def api_avatar(char_id: str):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    category = char.get("category", "")
    avatar_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "avatars", category, f"{char_id}.png")
    if not os.path.isfile(avatar_path):
        raise HTTPException(404, "avatar not found")
    return FileResponse(avatar_path, media_type="image/png")


@router.get("/characters")
async def api_characters(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    user_id = user.user_id if user else None
    include_adult = False
    if category == "per_te":
        from characters import list_characters as _lc
        all_chars = _lc(include_adult=include_adult)
        if user_id:
            prefs = get_user_preferences(user_id)
            interests = [t.lower() for t in prefs.get("interest_tags", [])]
            if interests:
                matching = [c for c in all_chars if any(t.lower() in interests for t in c.get("tags", []))]
                rest = [c for c in all_chars if c not in matching]
                chars = matching + rest
            else:
                chars = all_chars
        else:
            chars = all_chars
    else:
        chars = get_characters_by_category(category, include_adult=include_adult) if category else list_characters(include_adult=include_adult)

    if user_id:
        unlocks = {u["content_id"] for u in get_user_unlocks(user_id) if u["content_type"] == "category"}
        categories = get_categories()
        cat_cost = {c["id"]: c.get("mvc_cost", 0) for c in categories}
        chars = [c for c in chars if not cat_cost.get(c.get("category"), 0) or c["category"] in unlocks]
        try:
            prefs = get_user_preferences(user_id)
            gender = prefs.get("gender_interest", "")
            age_range = prefs.get("age_range", "")
            age_min, age_max = 0, 999
            if age_range:
                if "+" in age_range:
                    age_min = int(age_range.replace("+", ""))
                elif "-" in age_range:
                    parts = age_range.split("-")
                    age_min, age_max = int(parts[0]), int(parts[1])
            has_gender = gender and gender != "non binario"
            has_age = bool(age_range)
            if has_age or has_gender:
                from characters import infer_character_sex
                def _age_match(c):
                    return age_min <= c.get("age", 0) <= age_max
                def _gender_match(c):
                    return infer_character_sex(c) == gender
                def _unknown_gender(c):
                    return infer_character_sex(c) == ""
                if has_age and has_gender:
                    p1 = [c for c in chars if _age_match(c) and _gender_match(c)]
                    p2 = [c for c in chars if _age_match(c) and not _gender_match(c)]
                    p3 = [c for c in chars if not _age_match(c) and _gender_match(c)]
                    p4 = [c for c in chars if _age_match(c) and _unknown_gender(c)]
                    p5 = [c for c in chars if not _age_match(c) and _unknown_gender(c)]
                    p6 = [c for c in chars if not _age_match(c) and not _gender_match(c) and not _unknown_gender(c)]
                    chars = p1 + p2 + p3 + p4 + p5 + p6
                elif has_age:
                    chars = [c for c in chars if _age_match(c)] + [c for c in chars if not _age_match(c)]
                elif has_gender:
                    chars = ([c for c in chars if _gender_match(c)] +
                             [c for c in chars if _unknown_gender(c)] +
                             [c for c in chars if not _gender_match(c) and not _unknown_gender(c)])
        except Exception:
            pass
    if user_id:
        chars = _attach_intimacy(chars, user_id)
    return chars[offset:offset + limit]


@router.get("/characters/search")
async def api_search_characters(
    q: str = Query(""),
    category: Optional[str] = Query(None),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    q = q.strip()
    if not q:
        return []
    results = search_characters(q)
    if category:
        results = [c for c in results if c.get("category") == category]
    user_id = user.user_id if user else None
    if user_id:
        try:
            prefs = get_user_preferences(user_id)
            gender = prefs.get("gender_interest", "")
            if gender and gender != "non binario":
                from characters import infer_character_sex
                matching = [c for c in results if infer_character_sex(c) == gender]
                unknown = [c for c in results if infer_character_sex(c) == ""]
                rest = [c for c in results if infer_character_sex(c) not in (gender, "")]
                results = matching + unknown + rest
        except Exception:
            pass
    if user_id:
        results = _attach_intimacy(results, user_id)
    return results


@router.get("/characters/adult")
async def api_adult_characters(user: Optional[AuthUser] = Depends(jwt_optional)):
    # Contenuti adulti rimossi dall'app: endpoint sempre vuoto.
    return []


class AgeVerificationRequest(BaseModel):
    birth_year: int


@router.post("/me/verify-age")
async def api_verify_age(
    body: AgeVerificationRequest,
    user: AuthUser = Depends(jwt_required),
):
    """Verifica l'eta' dell'utente (self-asserted) e la memorizza lato server.

    Conforme al pattern di app companion su Google Play: il gate 18+ e' fatto
    valere sul server, non solo lato client, perche' i contenuti per adulti non
    siano raggiungibili da minori modificando preferenze locali.
    """
    ok = set_verified_birth_year(user.user_id, body.birth_year)
    return {"success": True, "age_verified": ok}


class ReportRequest(BaseModel):
    content_type: str  # "character" | "message"
    content_id: str
    reason: str
    snippet: str = ""


@router.post("/report")
async def api_report(
    body: ReportRequest,
    user: AuthUser = Depends(jwt_required),
):
    """Segnalazione contenuti da parte degli utenti (conformità Google Play UGC).

    I flag finiscono in moderation_flags e sono visibili agli admin. Il
    content_type distingue personaggio da messaggio; content_id e' l'id del
    soggetto segnalato, reason e' la motivazione scelta dall'utente.
    """
    if not body.content_id or not body.reason:
        raise HTTPException(400, "Dati segnalazione mancanti")
    if body.content_type not in ("character", "message"):
        body.content_type = "other"
    flag_user(
        user_id=body.content_id,
        reason=body.reason,
        content_type=body.content_type,
        content_snippet=(body.snippet or "")[:200],
        severity="medium",
        flagged_by=user.user_id,
    )
    audit_log(user.user_id, "content.report", f"{body.content_type}:{body.content_id}", "", "")
    return {"success": True}


@router.get("/characters/user")
async def api_user_characters(user: AuthUser = Depends(jwt_required)):
    return get_user_characters(user.user_id)


@router.post("/characters", status_code=201)
async def api_create_character(
    request: Request,
    body: CreateCharacterRequest,
    user: AuthUser = Depends(jwt_required),
):
    data = body.dict()
    if not data.get("name"):
        raise HTTPException(400, "name required")
    age = data.get("age", 0)
    if not isinstance(age, int) or age < 15:
        raise HTTPException(400, "L'età deve essere almeno 15 anni")
    # I personaggi adult/NSFW non sono creabili da questa sezione (scarico nuovi
    # personaggi): l'app dedicata è www.mevacoin.com/aria-adult.apk. Ogni eventuale
    # flag is_adult inviato dal client viene ignorato e forzato a False.
    data["is_adult"] = False
    char = create_user_character(user.user_id, data)
    audit_log(user.user_id, "character.create", char['id'],
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return char


@router.get("/characters/{char_id}")
async def api_character_detail(
    char_id: str,
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    if char.get("is_adult"):
        raise HTTPException(403, "Contenuto non disponibile")
    if "hobbies" in char and isinstance(char["hobbies"], list):
        formatted = []
        for h in char["hobbies"]:
            if isinstance(h, dict):
                skill = h.get("skill", "")
                formatted.append(f"{h['name']} ({skill})" if skill else h["name"])
            else:
                formatted.append(str(h))
        char = {**char, "hobbies": formatted}
    if user and user.user_id:
        intimacies = get_user_intimacies(user.user_id)
        intimacy = int(intimacies.get(char.get("id"), 0))
        char = {**char, "intimacy": intimacy,
                "intimacy_label": describe_intimacy_level(intimacy, char.get("intimacy_config") or _DEFAULT_INTIMACY_CFG)}
    return char


@router.get("/characters/{char_id}/core")
async def api_character_core(
    char_id: str,
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    if char.get("is_adult"):
        raise HTTPException(403, "Contenuto non disponibile")
    core_fields = [
        "id", "name", "full_name", "surname", "age", "role", "category",
        "avatar", "description", "tags", "essence", "personality",
        "personality_profile", "speaking_style", "backstory",
        "hobbies", "possessions", "core_traits", "evolution",
        "refusal_style", "intimacy_config",
        "knowledge_domains", "personality_depth", "family",
        "education", "occupation", "childhood", "system_prompt",
    ]
    return {k: char.get(k) for k in core_fields if k in char}


@router.delete("/characters/{char_id}")
async def api_delete_character(char_id: str, user: AuthUser = Depends(jwt_required)):
    char = get_character(char_id)
    if char and char.get("user_created"):
        delete_user_character(char_id)
        return {"status": "deleted"}
    raise HTTPException(404, "not found or not deletable")
