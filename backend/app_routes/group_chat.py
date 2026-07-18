import asyncio
import re
import random
import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from auth_fastapi import jwt_required, AuthUser
from storage import (
    is_content_unlocked,
    list_group_chats as _lgc,
    get_user_group_chats as _ugc,
    create_group_chat as _cgc,
    audit_log,
    get_group_chat as _ggc,
    get_group_messages as _ggm,
    is_group_participant as _igp,
    get_group_participants as _gp,
    delete_group_chat as _dgc,
    add_group_character as _agc,
    remove_group_character as _rgc,
    create_group_invitation as _ci,
    user_exists as _ue,
    get_user_pending_invitations as _gpi,
    respond_to_invitation as _ri,
    remove_group_participant as _rp,
    search_users as _su,
    add_group_message as _agm,
    get_blocked_users,
)
from characters import get_character
from chat_engine import FEATURES
from content_safety import moderate_output

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateGroupChatRequest(BaseModel):
    name: str
    character_ids: list = []


@router.get("/group-chats")
async def list_group_chats(user: AuthUser = Depends(jwt_required)):
    owned = _lgc(user.user_id)
    participating = _ugc(user.user_id)
    owned_ids = {c["id"] for c in owned}
    for c in participating:
        if c["id"] not in owned_ids:
            owned.append(c)
    return owned


@router.post("/group-chats")
async def create_group_chat(request: Request, body: CreateGroupChatRequest, user: AuthUser = Depends(jwt_required)):
    name = body.name.strip()
    character_ids = body.character_ids
    if not name:
        raise HTTPException(400, "Nome chat richiesto")
    if not character_ids or len(character_ids) < 2:
        raise HTTPException(400, "Servono almeno 2 personaggi per una chat di gruppo")
    if len(character_ids) > 8:
        raise HTTPException(400, "Massimo 8 personaggi per chat di gruppo")
    if not is_content_unlocked(user.user_id, "feature", "group_chat"):
        feat = FEATURES["group_chat"]
        raise HTTPException(403, f"Per usare Chat di Gruppo serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.")
    chat = _cgc(user.user_id, name, character_ids)
    audit_log(user.user_id, "group_chat.create", f"name={name} chars={len(character_ids)}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return chat


@router.get("/group-chats/{chat_id}")
async def get_group_chat(chat_id: int, user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    if chat["user_id"] != user.user_id and not _igp(chat_id, user.user_id):
        raise HTTPException(403, "Non sei autorizzato a visualizzare questa chat")
    messages = _ggm(chat_id, limit=100)
    blocked = set(get_blocked_users(user.user_id))
    if blocked:
        messages = [
            m for m in messages
            if not (m.get("sender_type") == "user" and m.get("sender_id") in blocked)
        ]
    participants = _gp(chat_id)
    chat["messages"] = messages
    chat["participants"] = [p["user_id"] for p in participants]
    return chat


@router.delete("/group-chats/{chat_id}")
async def delete_group_chat(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    if chat["user_id"] != user.user_id:
        raise HTTPException(403, "Solo il proprietario può eliminare la chat")
    _dgc(chat_id)
    audit_log(user.user_id, "group_chat.delete", f"chat={chat_id} name={chat['name']}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "deleted": chat_id}


@router.post("/group-chats/{chat_id}/characters")
async def add_character_to_group(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    data = await request.json()
    character_id = data.get("character_id", "").strip()
    if not character_id:
        raise HTTPException(400, "character_id richiesto")
    char = get_character(character_id)
    if not char:
        raise HTTPException(404, "Personaggio non trovato")
    current_ids = chat.get("character_ids", [])
    if character_id in current_ids:
        raise HTTPException(400, "Personaggio già presente nella chat")
    if len(current_ids) >= 8:
        raise HTTPException(400, "Massimo 8 personaggi per chat di gruppo")
    _agc(chat_id, character_id)
    audit_log(user.user_id, "group_chat.add_char", f"chat={chat_id} char={character_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "character_id": character_id, "character_name": char["name"]}


@router.delete("/group-chats/{chat_id}/characters/{character_id}")
async def remove_character_from_group(chat_id: int, character_id: str, request: Request,
                                       user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    current_ids = chat.get("character_ids", [])
    if character_id not in current_ids:
        raise HTTPException(400, "Personaggio non presente nella chat")
    if len(current_ids) <= 2:
        raise HTTPException(400, "Servono almeno 2 personaggi nella chat")
    _rgc(chat_id, character_id)
    audit_log(user.user_id, "group_chat.remove_char", f"chat={chat_id} char={character_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "removed": character_id}


@router.get("/group-chats/{chat_id}/participants")
async def get_group_participants(chat_id: int, user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    return _gp(chat_id)


@router.post("/group-chats/{chat_id}/participants")
async def invite_to_group(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    if not is_content_unlocked(user.user_id, "feature", "group_chat"):
        feat = FEATURES["group_chat"]
        raise HTTPException(403, f"Per usare Chat di Gruppo serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.")
    chat = _ggc(chat_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    if chat["user_id"] != user.user_id:
        raise HTTPException(403, "Solo il proprietario può invitare utenti")
    data = await request.json()
    invitee_id = data.get("user_id", "").strip()
    if not invitee_id:
        raise HTTPException(400, "user_id richiesto")
    if invitee_id == user.user_id:
        raise HTTPException(400, "Non puoi invitare te stesso")
    if not _ue(invitee_id):
        raise HTTPException(404, "Utente non trovato")
    if _igp(chat_id, invitee_id):
        raise HTTPException(400, "Utente già nella chat")
    _ci(chat_id, user.user_id, invitee_id)
    audit_log(user.user_id, "group_chat.invite", f"chat={chat_id} user={invitee_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "invited", "user_id": invitee_id}


@router.get("/user/invitations")
async def list_pending_invitations(user: AuthUser = Depends(jwt_required)):
    return _gpi(user.user_id)


@router.post("/user/invitations/{invitation_id}/respond")
async def respond_to_invitation(invitation_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    if not is_content_unlocked(user.user_id, "feature", "group_chat"):
        feat = FEATURES["group_chat"]
        raise HTTPException(403, f"Per usare Chat di Gruppo serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.")
    data = await request.json()
    accept = data.get("accept", False)
    chat_id = _ri(invitation_id, user.user_id, accept)
    if not chat_id:
        raise HTTPException(404, "Invito non trovato o già processato")
    action = "accepted" if accept else "declined"
    audit_log(user.user_id, f"group_chat.{action}", f"chat={chat_id} invitation={invitation_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": action, "group_chat_id": chat_id}


@router.delete("/group-chats/{chat_id}/participants/{participant_id}")
async def remove_group_participant(chat_id: int, participant_id: str, request: Request,
                                    user: AuthUser = Depends(jwt_required)):
    chat = _ggc(chat_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    if chat["user_id"] != user.user_id:
        raise HTTPException(403, "Solo il proprietario può rimuovere utenti")
    _rp(chat_id, participant_id)
    audit_log(user.user_id, "group_chat.remove_participant", f"chat={chat_id} user={participant_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "removed": participant_id}


@router.get("/users/search")
async def search_users(q: str, user: AuthUser = Depends(jwt_required)):
    results = _su(q, limit=10)
    return results


@router.post("/group-chats/{chat_id}/message")
async def send_group_message(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    if not is_content_unlocked(user.user_id, "feature", "group_chat"):
        feat = FEATURES["group_chat"]
        raise HTTPException(403, f"Per usare Chat di Gruppo serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.")
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Messaggio vuoto")
    chat = _ggc(chat_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    if chat["user_id"] != user.user_id and not _igp(chat_id, user.user_id):
        raise HTTPException(403, "Non sei autorizzato a scrivere in questa chat")
    _agm(chat_id, "user", user.user_id, "user", text)
    characters = []
    for cid in chat["character_ids"]:
        c = get_character(cid)
        if c:
            characters.append(c)
    if not characters:
        raise HTTPException(400, "Nessun personaggio valido trovato")
    history = _ggm(chat_id, limit=50)

    mentions = re.findall(r'@(\w+)', text, re.IGNORECASE)
    mentioned_chars = []
    for char in characters:
        char_name_lower = char["name"].lower()
        for mention in mentions:
            if mention.lower() in char_name_lower or char_name_lower in mention.lower():
                mentioned_chars.append(char)
                break

    if not mentioned_chars:
        for char in characters:
            char_name_lower = char["name"].lower()
            if re.search(r'(?<![a-zA-Z])' + re.escape(char["name"]) + r'(?![a-zA-Z])', text, re.IGNORECASE):
                mentioned_chars.append(char)

    if mentioned_chars:
        responding_chars = mentioned_chars
        auto_selected = False
    else:
        responding_chars = random.sample(characters, min(2, len(characters)))
        auto_selected = True

    responses = []
    previous_responses = []

    async def _generate_single_char(char, prev_responses, auto_sel):
        from prompt_builder import build_group_messages
        messages = build_group_messages(
            characters, text, history=history,
            username=user.user_id[:8],
            current_character=char["name"],
            previous_responses=prev_responses,
            auto_selected=auto_sel
        )
        from ai_engine import get_ai_response_stream
        def _sync_generate():
            full_response = ""
            for token_data in get_ai_response_stream(messages, user_id=user.user_id):
                if isinstance(token_data, tuple):
                    token = token_data[0]
                else:
                    token = token_data
                full_response += token
            # Blocco lato server garantito anche in chat di gruppo.
            reply, _blocked = moderate_output(full_response.strip())
            return reply
        try:
            loop = asyncio.get_event_loop()
            reply = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_generate),
                timeout=90
            )
            return reply
        except asyncio.TimeoutError:
            logger.warning(f"Group chat: timeout generazione risposta per {char['name']}")
            return ""
        except Exception as e:
            logger.warning(f"Group chat: errore generazione risposta per {char['name']}: {e}")
            return ""

    if len(responding_chars) > 1:
        tasks = []
        for char in responding_chars:
            tasks.append(_generate_single_char(char, [], auto_selected))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue
            reply = result
            if reply:
                char = responding_chars[i]
                _agm(chat_id, "character", char["id"], "assistant", reply)
                responses.append({"character_id": char["id"],
                                  "character_name": char["name"],
                                  "content": reply})
                previous_responses.append({"name": char["name"], "content": reply})
    else:
        for char in responding_chars:
            reply = await _generate_single_char(char, [], auto_selected)
            if reply:
                _agm(chat_id, "character", char["id"], "assistant", reply)
                responses.append({"character_id": char["id"],
                                  "character_name": char["name"],
                                  "content": reply})
                previous_responses.append({"name": char["name"], "content": reply})

    if not responses and responding_chars:
        fallback_char = responding_chars[0]
        reply = await _generate_single_char(fallback_char, [], False)
        if reply:
            _agm(chat_id, "character", fallback_char["id"], "assistant", reply)
            responses.append({"character_id": fallback_char["id"],
                              "character_name": fallback_char["name"],
                              "content": reply})

    return {"responses": responses, "user_message": text}
