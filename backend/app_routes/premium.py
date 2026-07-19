import json
import logging
import random
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from characters import get_character, get_categories
from storage import (
    get_user_preferences, save_user_preferences,
    get_mevacoins_balance, get_user_unlocks,
    get_mevacoins_transactions,
    unlock_content, is_content_unlocked,
    get_new_user_bonus, claim_new_user_bonus,
    get_or_create_referral_code, claim_referral_bonus,
    get_daily_share_count, add_social_share,
    get_streak_30_status,
    claim_streak_30_day, calculate_streak_reward,
    credit_referral_first_message,
    audit_log,
    get_daily_message_status, unlock_unlimited_messages,
)
from auth_fastapi import jwt_optional, jwt_required, AuthUser
from chat_engine import FEATURES

router = APIRouter()


class SpendRequest(BaseModel):
    content_type: str = ""
    content_id: str = ""
    amount: int = 0


class ClaimBonusRequest(BaseModel):
    day: int = 1


class ClaimReferralRequest(BaseModel):
    code: str = ""


class ShareRequest(BaseModel):
    platform: str = ""


class RollbackRequest(BaseModel):
    purchase_id: str = ""


class SuggestionRequest(BaseModel):
    character_id: str = ""


@router.get("/user/preferences")
async def api_get_preferences(user: AuthUser = Depends(jwt_required)):
    return get_user_preferences(user.user_id)


@router.put("/user/preferences")
async def api_save_preferences(request: Request, user: AuthUser = Depends(jwt_required)):
    data = await request.json()
    save_user_preferences(user.user_id, data)
    audit_log(user.user_id, "preferences.update", json.dumps(data),
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok"}


@router.get("/user/mevacoins")
async def api_mevacoins_balance(user: AuthUser = Depends(jwt_required)):
    return {"balance": get_mevacoins_balance(user.user_id)}


@router.get("/user/mevacoins/missions")
async def api_mevacoins_missions(user: AuthUser = Depends(jwt_required)):
    from storage.missions import get_active_missions
    return {"missions": get_active_missions(user.user_id)}


class StoreItemRequest(BaseModel):
    item: str = ""


@router.get("/user/mevacoins/store")
async def api_mevacoins_store(user: AuthUser = Depends(jwt_required)):
    from storage.store import get_shop_payload
    return get_shop_payload(user.user_id)


@router.get("/user/mevacoins/badges")
async def api_mevacoins_badges(user: AuthUser = Depends(jwt_required)):
    from storage.store import get_gamification
    return get_gamification(user.user_id)


@router.get("/user/mevacoins/purchases")
async def api_mevacoins_purchases(user: AuthUser = Depends(jwt_required)):
    from storage.rollback import get_purchases, ROLLBACK_FEE
    return {"purchases": get_purchases(user.user_id), "rollback_fee": ROLLBACK_FEE}


@router.post("/user/mevacoins/rollback")
async def api_mevacoins_rollback(body: RollbackRequest, user: AuthUser = Depends(jwt_required)):
    if not body.purchase_id:
        raise HTTPException(400, "purchase_id richiesto")
    from storage.rollback import rollback_purchase
    ok, payload, msg = rollback_purchase(user.user_id, body.purchase_id)
    if not ok:
        if msg in ("saldo_insufficiente_rollback", "acquisto_non_trovato"):
            raise HTTPException(400, msg)
        raise HTTPException(500, msg)
    return {"status": "ok", **payload}


@router.post("/user/mevacoins/store/buy")
async def api_mevacoins_store_buy(body: StoreItemRequest, user: AuthUser = Depends(jwt_required)):
    from storage.store import buy_consumable
    if not body.item:
        raise HTTPException(400, "item richiesto")
    ok, msg = buy_consumable(user.user_id, body.item)
    if not ok:
        raise HTTPException(400 if msg == "saldo_insufficiente" else 500, msg)
    return {"status": "ok", "item": body.item}


@router.post("/user/mevacoins/store/use")
async def api_mevacoins_store_use(body: StoreItemRequest, user: AuthUser = Depends(jwt_required)):
    from storage.store import use_consumable
    if not body.item:
        raise HTTPException(400, "item richiesto")
    ok, msg = use_consumable(user.user_id, body.item)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "item": body.item}


@router.get("/user/mevacoins/unlocks")
async def api_mevacoins_unlocks(user: AuthUser = Depends(jwt_required)):
    unlocks = get_user_unlocks(user.user_id)
    unlocked_ids = {u["content_id"] for u in unlocks if u["content_type"] == "category"}
    unlocked_features = {u["content_id"] for u in unlocks if u["content_type"] == "feature"}
    return {
        "categories": list(unlocked_ids),
        "features": list(unlocked_features),
        "all": unlocks,
    }


@router.get("/user/mevacoins/transactions")
async def api_mevacoins_tx(user: AuthUser = Depends(jwt_required)):
    return get_mevacoins_transactions(user.user_id)


@router.get("/user/messages/status")
async def api_daily_message_status(user: AuthUser = Depends(jwt_required)):
    return get_daily_message_status(user.user_id)


@router.post("/user/messages/unlock")
async def api_unlock_unlimited_messages(request: Request, user: AuthUser = Depends(jwt_required)):
    ok, msg = unlock_unlimited_messages(user.user_id)
    if not ok:
        if msg == "saldo_insufficiente":
            raise HTTPException(400, "saldo_insufficiente")
        raise HTTPException(500, msg)
    audit_log(user.user_id, "messages.unlock", "daily limit lifted via MVC",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "unlocked": True, "message_status": get_daily_message_status(user.user_id)}


@router.post("/user/mevacoins/checkin")
async def api_daily_checkin(request: Request, user: AuthUser = Depends(jwt_required)):
    log = logging.getLogger(__name__)
    try:
        success, earned, msg = claim_streak_30_day(user.user_id)
        log.info(f"checkin user={user.user_id} success={success} earned={earned} msg={msg}")
    except Exception as e:
        log.error(f"checkin FAILED user={user.user_id} error={e}")
        raise HTTPException(500, f"checkin error: {e}")
    if success:
        audit_log(user.user_id, "mevacoins.checkin", f"streak day earned={earned}",
                  request.client.host if request.client else "",
                  request.headers.get("User-Agent", ""))
    status = get_streak_30_status(user.user_id)
    return {
        "already_checked": not success,
        "earned": earned if success else 0,
        "streak": status["current_day"],
        "reward": earned if success else 0,
        "total_earned": status["total_earned"],
    }


@router.post("/user/mevacoins/spend")
async def api_mevacoins_spend(request: Request, body: SpendRequest, user: AuthUser = Depends(jwt_required)):
    if not body.content_type or not body.content_id or body.amount <= 0:
        raise HTTPException(400, "richiesta non valida")
    if body.content_type == "category":
        valid = any(c["id"] == body.content_id and c.get("mvc_cost", 0) == body.amount for c in get_categories())
        if not valid:
            raise HTTPException(400, "categoria o costo non valido")
    elif body.content_type == "feature":
        feat = FEATURES.get(body.content_id)
        if not feat or feat["mvc_cost"] != body.amount:
            raise HTTPException(400, "feature o costo non valido")
    else:
        raise HTTPException(400, "content_type non valido")
    if is_content_unlocked(user.user_id, body.content_type, body.content_id):
        return {"status": "ok", "unlocked": True, "already_unlocked": True}
    ok, msg = unlock_content(user.user_id, body.content_type, body.content_id, body.amount)
    if not ok:
        raise HTTPException(400 if msg == "saldo_insufficiente" else 500, msg)
    audit_log(user.user_id, "mevacoins.spend", f"{body.content_type}:{body.content_id} cost={body.amount}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "unlocked": True}


@router.get("/user/mevacoins/new-user-bonus")
async def api_new_user_bonus(user: AuthUser = Depends(jwt_required)):
    return get_new_user_bonus(user.user_id)


@router.post("/user/mevacoins/new-user-bonus/claim")
async def api_claim_bonus(body: ClaimBonusRequest, user: AuthUser = Depends(jwt_required)):
    ok = claim_new_user_bonus(user.user_id, body.day)
    return {"claimed": ok}


@router.get("/user/referral/code")
async def api_referral_code(user: AuthUser = Depends(jwt_required)):
    code = get_or_create_referral_code(user.user_id)
    if not code:
        raise HTTPException(500, "errore generazione codice")
    return {"code": code}


@router.post("/user/referral/claim")
async def api_claim_referral(request: Request, body: ClaimReferralRequest, user: AuthUser = Depends(jwt_required)):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(400, "codice richiesto")
    ok, msg = claim_referral_bonus(user.user_id, code)
    if not ok:
        raise HTTPException(400, msg)
    audit_log(user.user_id, "referral.claim", f"code={code}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "bonus": 50}


@router.post("/user/mevacoins/share")
async def api_social_share(request: Request, body: ShareRequest, user: AuthUser = Depends(jwt_required)):
    ok, msg = add_social_share(user.user_id, body.platform)
    if not ok:
        raise HTTPException(400 if msg == "limite_giornaliero" else 500, msg)
    audit_log(user.user_id, "mevacoins.share", f"platform={body.platform}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "earned": 30}


@router.get("/user/mevacoins/share/status")
async def api_share_status(user: AuthUser = Depends(jwt_required)):
    count = get_daily_share_count(user.user_id)
    return {"today_count": count, "max_daily": 3}


@router.get("/user/mevacoins/streak")
async def api_streak_30(user: AuthUser = Depends(jwt_required)):
    return get_streak_30_status(user.user_id)


@router.post("/user/mevacoins/streak/claim")
async def api_streak_30_claim(request: Request, user: AuthUser = Depends(jwt_required)):
    success, earned, msg = claim_streak_30_day(user.user_id)
    if not success:
        if msg == "gia_riscosso":
            raise HTTPException(400, "Già riscosso oggi")
        raise HTTPException(500, msg)
    audit_log(user.user_id, "mevacoins.streak_claim", f"day={earned}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"earned": earned, "success": True}


@router.post("/user/mevacoins/streak/shield")
async def api_streak_shield(request: Request, user: AuthUser = Depends(jwt_required)):
    from storage.streak import use_streak_shield
    success, msg, earned = use_streak_shield(user.user_id)
    if not success and msg not in ("nothing_to_protect",):
        if msg == "no_shield":
            raise HTTPException(400, "Nessuno Streak Shield disponibile")
        raise HTTPException(500, msg)
    audit_log(user.user_id, "mevacoins.streak_shield", f"msg={msg} earned={earned}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"success": success, "message": msg, "earned": earned}


@router.post("/chat/suggestion")
async def api_chat_suggestion(body: SuggestionRequest, user: Optional[AuthUser] = Depends(jwt_optional)):
    char = get_character(body.character_id)
    if not char:
        raise HTTPException(404, "character not found")
    tags_str = "generali"
    if user:
        prefs = get_user_preferences(user.user_id)
        tags = prefs.get("interest_tags", [])
        tags_str = ", ".join(tags) if tags else "generali"
    prompt = (
        f"Genera UNA domanda o frase di apertura che l'utente potrebbe inviare al personaggio '{char['name']}' "
        f"per iniziare una conversazione interessante. "
        f"La domanda deve essere naturale, in italiano, e tenere conto che l'utente ha questi interessi: {tags_str}. "
        f"Il personaggio è: {char.get('essence', 'un personaggio virtuale')}. "
        f"Restituisci SOLO la domanda, senza prefazioni o spiegazioni."
    )
    from ai_engine import get_ai_response as _gair
    uid = user.user_id if user else "anonymous"
    suggestion, _, _ = _gair([
        {"role": "system", "content": "Sei un assistente che genera domande di apertura per chat con personaggi virtuali. Rispondi solo con la domanda, nient'altro."},
        {"role": "user", "content": prompt}
    ], user_id=uid)
    if not suggestion:
        fallbacks = [f"Ciao {char['name']}! Come stai?", f"Raccontami qualcosa di te, {char['name']}.", f"Che cosa ti appassiona di più, {char['name']}?"]
        suggestion = random.choice(fallbacks)
    return {"suggestion": suggestion.strip()}
