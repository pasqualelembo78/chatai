import json
import logging
import re
import uuid
import time
from collections import defaultdict

from characters import get_character, list_characters, get_categories
from emotion_engine import detect_emotion
from storage import (
    get_relationship, update_relationship,
    get_personality, update_personality,
    get_world_state,
    add_message, get_recent_messages, count_messages,
    add_memory, get_memories, get_last_summary_checkpoint,
    get_recent_shifts,
    get_user_memory, update_user_memory,
    get_user_preferences,
    get_evolution, update_evolution,
    is_user_premium,
    is_content_unlocked,
    count_all_user_messages,
    credit_referral_first_message,
)
from evolution_engine import evaluate_evolution
from prompt_builder import build_messages
from ai_engine import get_ai_response
from content_safety import moderate_output
import ai_engine
import image_utils
import security_utils
from auth_fastapi import socket_authenticate
from storage import check_and_count_message, refund_message
from chat_engine import (
    _detect_pretend, _find_character_by_name, _build_ad_hoc_character,
    IMPERSONATION_MVC_COST,
    process_message,
    _check_character_access,
    _compute_relationship_deltas,
    _compute_personality_deltas,
    _fallback_response,
    _maybe_summarize,
    _detect_character_rename,
    _extract_memory_updates,
)

logger = logging.getLogger(__name__)

user_sessions = {}
user_rooms = {}
user_names = {}
greeted_users = set()
socket_auth_map = {}


def _default_character_id():
    """Return the first available character id, or None if no characters exist.

    Avoids `list_characters()[0]['id']` raising IndexError when the character
    catalogue is empty (e.g. data failed to load).
    """
    chars = list_characters()
    return chars[0]["id"] if chars else None


def register_socket_handlers(sio):

    @sio.event
    async def connect(sid, environ, auth):
        token = None
        user_id = None
        role = "user"
        if auth and isinstance(auth, dict):
            token = auth.get("token", "")
        if token and token != "local_session":
            payload = socket_authenticate(token)
            if payload:
                user_id = payload["user_id"]
                role = payload.get("role", "user")
        if not user_id:
            user_id = "anon_" + uuid.uuid4().hex[:12]
        socket_auth_map[sid] = {"user_id": user_id, "role": role}
        user_sessions[user_id] = sid

    @sio.event
    async def disconnect(sid):
        auth_info = socket_auth_map.pop(sid, None)
        if auth_info:
            uid = auth_info.get("user_id", "")
            greeted_users.discard((uid, None))
            for key in list(greeted_users):
                if key[0] == uid:
                    greeted_users.discard(key)
        for uid, _sid in list(user_sessions.items()):
            if _sid == sid:
                del user_sessions[uid]
                break
        user_names.pop(sid, None)
        user_rooms.pop(sid, None)

    @sio.on("add user")
    async def on_add_user(sid, data):
        auth_data = socket_auth_map.get(sid)
        if not auth_data:
            await sio.emit("error", {"message": "Non autenticato"}, room=sid)
            return
        user_id = auth_data["user_id"]
        username = data.get("username", "Utente")
        character_id = data.get("character", _default_character_id())
        user_rooms[sid] = user_id
        user_names[sid] = username
        character = get_character(character_id)
        character_name = character["name"] if character else "AI"
        await sio.enter_room(sid, user_id)
        if not character:
            await sio.emit("login", {
                "numUsers": len(user_sessions),
                "username": username,
                "user_id": user_id,
                "character_id": character_id,
                "character_name": character_name
            }, room=sid)
            return
        await sio.emit("login", {
            "numUsers": len(user_sessions),
            "username": username,
            "user_id": user_id,
            "character_id": character_id,
            "character_name": character_name
        }, room=sid)
        greet_key = (user_id, character_id)
        if greet_key in greeted_users:
            return
        greeted_users.add(greet_key)

        total_msgs = count_messages(user_id, character_id)

        if total_msgs == 0:
            greeting = _generate_greeting(character, character_name, username, user_id=user_id)
            add_message(user_id, character_id, "assistant", greeting)
            await sio.emit("new message", {
                "username": character_name, "message": greeting, "is_roleplay": True
            }, room=sid)

    @sio.on("new message")
    async def on_new_message(sid, data):
        user_id = user_rooms.get(sid)
        if not user_id:
            await sio.emit("error", {"message": "Not logged in"}, room=sid)
            return
        allowed, status = check_and_count_message(user_id)
        if not allowed:
            await sio.emit("daily_limit_reached", status, room=sid)
            await sio.emit("error", {
                "message": f"Limite giornaliero di messaggi raggiunto ({status['limit']}). "
                           f"Sblocca messaggi illimitati con {status['unlock_cost']} MVC."
            }, room=sid)
            return
        text = data.get("message", "")
        character_id = data.get("character", _default_character_id())
        image_b64 = data.get("image", "")
        image_mime = data.get("image_mime", "image/jpeg")
        if not text and not image_b64:
            return
        if text:
            ok, msg = security_utils.nsfw_check_text(text)
            if not ok:
                await sio.emit("error", {"message": msg}, room=sid)
                return
        username = user_names.get(sid, "Utente")
        result = process_message(user_id, character_id, text, username,
                                 memory_context=data.get("memory_context"),
                                 user_memory=data.get("user_memory"),
                                 character_data=data.get("character_data"),
                                 image_base64=image_b64, image_mime=image_mime,
                                 is_favorite=data.get("is_favorite", False))
        if not result:
            refund_message(user_id)
            await sio.emit("error", {"message": "Character not found"}, room=sid)
            return
        await sio.emit("new message", {
            "username": username, "message": text, "is_roleplay": False
        }, room=sid)
        mem_updates = result.get("memory_updates", {})
        evo_updates = result.get("evo_updates", {})
        result["ai_text"] = moderate_output(result.get("ai_text", ""))[0]
        response_data = {
            "username": result["character"].get("name", "AI"),
            "message": result["ai_text"],
            "emotion": result["emotion"],
            "ai_provider": result.get("ai_provider", ""),
            "ai_model": result.get("ai_model", ""),
            "is_roleplay": True,
            "is_fallback": result.get("is_fallback", False),
            "impersonating": result.get("impersonating", False),
            "impersonate_target": result.get("impersonate_target", ""),
        }
        if mem_updates:
            response_data["memory_updates"] = mem_updates
        if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
            response_data["evo_updates"] = evo_updates
        if result.get("generated_image"):
            response_data["generated_image"] = result["generated_image"]
        if result.get("generated_video"):
            response_data["generated_video"] = result["generated_video"]
        await sio.emit("new message", response_data, room=sid)

    @sio.on("get scenario")
    async def on_get_scenario(sid, data):
        user_id = user_rooms.get(sid)
        if not user_id:
            await sio.emit("error", {"message": "Not logged in"}, room=sid)
            return
        character_id = data.get("character", "")
        character = get_character(character_id)
        if not character:
            await sio.emit("error", {"message": "Character not found"}, room=sid)
            return
        from scenario_engine import get_opening_scenario
        total_msgs = count_messages(user_id, character_id)
        user_gender = user_age = sexual_orientation = None
        prefs = get_user_preferences(user_id)
        user_gender = prefs.get("user_gender") or None
        user_age = prefs.get("user_age") or None
        sexual_orientation = prefs.get("sexual_orientation") or None
        scenario_text = get_opening_scenario(character, total_msgs,
                                              user_gender=user_gender,
                                              user_age=user_age,
                                              sexual_orientation=sexual_orientation)
        if scenario_text:
            await sio.emit("scenario content", {
                "character": character_id,
                "message": scenario_text
            }, room=sid)
        else:
            await sio.emit("scenario content", {
                "character": character_id,
                "message": ""
            }, room=sid)

    @sio.on("stream message")
    async def on_stream_message(sid, data):
        user_id = user_rooms.get(sid)
        if not user_id:
            await sio.emit("stream error", {"message": "Not logged in"}, room=sid)
            return
        text = data.get("message", "")
        character_id = data.get("character", _default_character_id())
        image_b64 = data.get("image", "")
        image_mime = data.get("image_mime", "image/jpeg")
        if not text and not image_b64:
            return
        if text:
            ok, msg = security_utils.nsfw_check_text(text)
            if not ok:
                await sio.emit("stream error", {"message": msg}, room=sid)
                return
        username = user_names.get(sid, "Utente")
        character = get_character(character_id)
        if not character:
            await sio.emit("stream error", {"message": "Character not found"}, room=sid)
            return
        if not _check_character_access(user_id, character):
            await sio.emit("stream error", {"message": "premium_required"}, room=sid)
            return

        allowed, status = check_and_count_message(user_id)
        if not allowed:
            await sio.emit("daily_limit_reached", status, room=sid)
            await sio.emit("stream error", {
                "message": f"Limite giornaliero di messaggi raggiunto ({status['limit']}). "
                           f"Sblocca messaggi illimitati con {status['unlock_cost']} MVC."
            }, room=sid)
            return

        await sio.emit("typing", {"username": character["name"]}, room=sid)

        stripped = text.strip()
        if stripped.startswith("/genera") or stripped.startswith("/muovi"):
            result = process_message(user_id, character_id, text, username,
                                     memory_context=data.get("memory_context"),
                                     user_memory=data.get("user_memory"),
                                     character_data=data.get("character_data"),
                                     image_base64=image_b64, image_mime=image_mime,
                                     is_favorite=data.get("is_favorite", False),
                                     tone=data.get("tone"))
            if result:
                result["ai_text"] = moderate_output(result.get("ai_text", ""))[0]
                payload = {
                    "username": character["name"],
                    "message": result["ai_text"],
                    "emotion": result.get("emotion", "neutro"),
                    "ai_provider": result.get("ai_provider", "system"),
                    "ai_model": result.get("ai_model", ""),
                    "is_roleplay": True,
                    "is_fallback": result.get("is_fallback", False),
                }
                if result.get("generated_image"):
                    payload["generated_image"] = result["generated_image"]
                if result.get("generated_video"):
                    payload["generated_video"] = result["generated_video"]
                await sio.emit("new message", payload, room=sid)
            return

        emotion, intensity, emotions = detect_emotion(text)
        relationship = get_relationship(user_id, character_id)
        personality = get_personality(character_id, character.get("core_traits", {}))
        world_state = get_world_state()
        memory_context = data.get("memory_context")
        user_memory = data.get("user_memory")
        _msg_limit = 50 if is_content_unlocked(user_id, "feature", "extended_memory") else 20
        history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=_msg_limit)
        shifts = get_recent_shifts(user_id, character_id)
        user_prefs = get_user_preferences(user_id)
        user_gender = user_prefs.get("user_gender") or None
        user_age = user_prefs.get("user_age") or None
        sexual_orientation = user_prefs.get("sexual_orientation") or None

        image_desc = None
        if image_b64:
            image_desc = image_utils.describe_image(image_b64, image_mime)
            if image_desc:
                text = (text + "\n\n[IMAGE: " + image_desc + "]") if text else "[IMAGE: " + image_desc + "]"

        is_first = count_all_user_messages(user_id) == 0
        add_message(user_id, character_id, "user", text)
        if is_first:
            credit_referral_first_message(user_id)

        evo = get_evolution(user_id, character_id)

        impersonate_override = None
        pretend_action, pretend_target = _detect_pretend(text) if text else (None, None)
        logger.info(f"Stream Pretend detect: action={pretend_action} target={pretend_target} user={user_id}")

        if pretend_action == "STOP":
            evo["flags"]["impersonating"] = False
            evo["flags"]["impersonate_target"] = ""
            evo["flags"].pop("impersonate_data", None)
            update_evolution(user_id, character_id, evo)
        elif pretend_action == "START" and pretend_target:
            if not is_content_unlocked(user_id, "feature", "impersonation"):
                char_name = character.get("name", "io")
                premium_msg = (
                    f"*{char_name} scuote la testa.* "
                    f"Mi dispiace, ma questa è una funzionalità premium. "
                    f"Per finta di essere qualcun altro devi sbloccarla con {IMPERSONATION_MVC_COST} MevaCoins. "
                    f"Vai nelle impostazioni per sbloccarla!"
                )
                await sio.emit("stream start", {
                    "username": character["name"],
                    "user_message": data.get("message", ""),
                    "emotion": "neutro", "intensity": 0.0,
                }, room=sid)
                await sio.emit("stream token", {"token": premium_msg, "text": premium_msg}, room=sid)
                await sio.emit("stream complete", {
                    "text": premium_msg, "username": character["name"],
                    "emotion": "neutro", "ai_provider": "system", "ai_model": "",
                    "impersonating": False, "impersonate_target": "",
                    "premium_required": True, "unlock_cost": IMPERSONATION_MVC_COST,
                }, room=sid)
                refund_message(user_id)
                return
            target_char = _find_character_by_name(pretend_target)
            if not target_char:
                target_char = _build_ad_hoc_character(pretend_target)
            evo["flags"]["impersonating"] = True
            evo["flags"]["impersonate_target"] = pretend_target
            evo["flags"]["impersonate_data"] = target_char
            evo["flags"]["original_character_id"] = character_id
            update_evolution(user_id, character_id, evo)
            impersonate_override = target_char
            character = {**character, **target_char}
        elif evo.get("flags", {}).get("impersonating"):
            saved_target = evo["flags"].get("impersonate_target", "")
            saved_data = evo["flags"].get("impersonate_data")
            if saved_data:
                impersonate_override = saved_data
                character = {**character, **saved_data}
            elif saved_target:
                target_char = _find_character_by_name(saved_target)
                if target_char:
                    impersonate_override = target_char
                    character = {**character, **target_char}
                    evo["flags"]["impersonate_data"] = target_char
                    update_evolution(user_id, character_id, evo)

        if impersonate_override and impersonate_override.get("core_traits"):
            personality = {**impersonate_override["core_traits"]}

        evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)
        if evo_updates["relationship_deltas"]:
            update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
        if evo_updates["trait_modifiers"]:
            pers = get_personality(character_id, character.get("core_traits", {}))
            for trait, delta in evo_updates["trait_modifiers"].items():
                pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
            update_personality(character_id, pers)

        if not character.get("evolution"):
            rel_deltas = _compute_relationship_deltas(emotion, intensity)
            if any(v != 0 for v in rel_deltas.values()):
                update_relationship(user_id, character_id, rel_deltas)
            pers_deltas = _compute_personality_deltas(emotion, intensity, relationship)
            if any(v != 0 for v in pers_deltas.values()):
                pers = get_personality(character_id, character.get("core_traits", {}))
                for trait, delta in pers_deltas.items():
                    pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
                update_personality(character_id, pers)

        learned = evo.setdefault("learned", {"topics": [], "personality_drift": {}, "new_skills": []})
        knowledge = character.get("knowledge_domains", {})
        ignorance_list = knowledge.get("ignorance", [])
        text_lower = text.lower()
        for topic in ignorance_list:
            if not isinstance(topic, str):
                continue
            keywords = [w for w in topic.lower().split() if len(w) > 3]
            if not keywords:
                keywords = [topic.lower()]
            matched = sum(1 for kw in keywords if kw in text_lower)
            if matched >= 1 and matched >= len(keywords) * 0.5:
                topic_key = f"teaching:{topic}"
                evo["flags"][topic_key] = evo["flags"].get(topic_key, 0) + 1
                if evo["flags"][topic_key] >= 3 and topic not in learned["topics"]:
                    learned["topics"].append(topic)

        emotion_drift = {
            "joy": {"warmth": 0.02, "playfulness": 0.03},
            "anger": {"warmth": -0.03, "strictness": 0.02, "sarcasm": 0.03},
            "romance": {"warmth": 0.03, "playfulness": 0.02},
            "sadness": {"warmth": 0.01, "patience": 0.02},
            "challenge": {"strictness": 0.02, "sarcasm": 0.03},
        }
        drift = emotion_drift.get(emotion, {})
        for trait, delta in drift.items():
            current = learned["personality_drift"].get(trait, 0.0)
            clamped = max(-3.0, min(3.0, current + delta))
            learned["personality_drift"][trait] = round(clamped, 2)

        update_evolution(user_id, character_id, evo)

        # Grant the MevaCoins milestone reward only after the evolution flags
        # (one_shot / cooldown) have been persisted, so a later failure can't
        # re-trigger the same reward.
        reward = evo_updates.get("mevacoins_reward", 0)
        if reward:
            from storage import add_mevacoins
            add_mevacoins(user_id, reward, f"milestone:{character_id}")

        new_name = _detect_character_rename(text)
        if new_name:
            evo["flags"]["custom_name"] = new_name
            update_evolution(user_id, character_id, evo)

        if evo.get("flags", {}).get("custom_name"):
            character = {**character, "name": evo["flags"]["custom_name"]}

        memory_updates = _extract_memory_updates(user_id, text, character, character_id)
        if memory_updates:
            wrapped = {}
            for key, val in memory_updates.items():
                wrapped[key] = {"value": val, "source": character_id, "source_name": character["name"]}
            update_user_memory(user_id, wrapped)

        stored = get_user_memory(user_id).get("memory", {})
        if stored:
            user_memory = stored

        summaries = get_memories(user_id, character_id, limit=5)
        evo["dialog_hints"] = evo_updates.get("dialog_hints", [])
        evo["_just_unlocked"] = evo_updates.get("unlocked", [])
        user_is_favorite = data.get("is_favorite", False)
        _total_msgs = count_messages(user_id, character_id)
        messages = build_messages(
            character, {"emotion": emotion, "intensity": intensity},
            relationship, personality, world_state, text, user_id, history,
            shifts, username, user_memory=user_memory, summaries=summaries,
            evolution=evo, is_favorite=user_is_favorite, total_messages=_total_msgs,
            user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
            impersonate_override=impersonate_override,
        )

        await sio.emit("stream start", {
            "username": character["name"],
            "user_message": data.get("message", ""),
            "emotion": emotion,
            "intensity": intensity,
        }, room=sid)

        ai_text = ""
        ai_provider = ""
        ai_model = ""
        is_fallback = False

        try:
            for token, pid, model in ai_engine.get_ai_response_stream(messages, user_id=user_id):
                ai_text += token
                await sio.emit("stream token", {"token": token, "text": ai_text}, room=sid)
                ai_provider = pid
                ai_model = model
        except Exception as e:
            await sio.emit("stream error", {"message": str(e)}, room=sid)
            return

        if not ai_text:
            ai_text = _fallback_response(character, emotion)
            ai_provider = "fallback"
            is_fallback = True
            await sio.emit("stream token", {"token": f"[fallback] {ai_text}", "text": f"[fallback] {ai_text}"}, room=sid)

        ai_text, _blocked = moderate_output(ai_text)

        add_message(user_id, character_id, "assistant", ai_text)

        try:
            _maybe_summarize(user_id, character_id, character)
        except Exception:
            pass

        await sio.emit("stream complete", {
            "username": character["name"],
            "message": ai_text,
            "emotion": emotion,
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "is_roleplay": True,
            "is_fallback": is_fallback,
            "memory_updates": memory_updates or {},
            "evo_updates": {"new_stage": evo_updates.get("new_stage"), "unlocked": evo_updates.get("unlocked", [])},
            "impersonating": evo.get("flags", {}).get("impersonating", False),
            "impersonate_target": evo.get("flags", {}).get("impersonate_target", ""),
        }, room=sid)

    @sio.on("stream stop")
    async def on_stream_stop(sid, data):
        user_id = user_rooms.get(sid)
        if user_id:
            ai_engine.STREAM_STOP_FLAGS[user_id] = True

    @sio.on("typing")
    async def on_typing(sid, data):
        user_id = user_rooms.get(sid)
        if not user_id:
            return
        character_id = data.get("character", _default_character_id())
        character = get_character(character_id)
        if character:
            await sio.emit("typing", {"username": character["name"]}, room=sid)

    @sio.on("stop typing")
    async def on_stop_typing(sid, data):
        user_id = user_rooms.get(sid)
        if not user_id:
            return
        character_id = data.get("character", _default_character_id())
        character = get_character(character_id)
        if character:
            await sio.emit("stop typing", {"username": character["name"]}, room=sid)


def _generate_greeting(character, character_name, username=None, user_id=None):
    from prompt_builder import build_system_prompt
    rel = get_relationship("new_user", character["id"])
    pers = get_personality(character["id"], character["core_traits"])
    ws = get_world_state()
    user_gender = user_age = sexual_orientation = None
    if user_id:
        prefs = get_user_preferences(user_id)
        user_gender = prefs.get("user_gender") or None
        user_age = prefs.get("user_age") or None
        sexual_orientation = prefs.get("sexual_orientation") or None
    sp = build_system_prompt(character, {"emotion": "neutral", "intensity": 0}, rel, pers, ws,
                             username=username, user_gender=user_gender, user_age=user_age,
                             sexual_orientation=sexual_orientation)

    msg_count = count_messages(user_id, character["id"]) if user_id else 0
    if msg_count == 0:
        warmth = "stranger"
        warmth_desc = "Non hai mai parlato con questa persona. Fai una prima presentazione breve e naturale."
    elif msg_count <= 10:
        warmth = "acquaintance"
        warmth_desc = f"Conosci appena {username}. Saluta in modo cordiale ma non eccessivo."
    elif msg_count <= 50:
        warmth = "friend"
        warmth_desc = f"Sei abbastanza in confidenza con {username}. Saluta con calore, mostra che sei contento di rivederlo/a."
    elif msg_count <= 100:
        warmth = "close_friend"
        warmth_desc = f"Tu e {username} avete una bella amicizia. Saluta con affetto genuino, come faresti con un amico caro."
    else:
        warmth = "best_friend"
        warmth_desc = f"Tu e {username} siete molto legati. Saluta con grande affetto e intimità, come una persona cara che non vedi da tempo."

    prompt = (
        f"Livello di familiarità: {warmth}. {warmth_desc}\n"
        f"Saluta {username} in modo naturale e coerente con il tuo personaggio. "
        f"Non usare frasi fatte. Sii creativo. Massimo 1-2 frasi."
    )
    msgs = [{"role": "system", "content": sp}, {"role": "user", "content": prompt}]
    ai_text, _, _ = get_ai_response(msgs, user_id=user_id)
    if ai_text:
        return ai_text
    return _greeting_fallback(character_name, character)


def _greeting_fallback(name, character):
    cid = character["id"]
    g = {
        "ginecologa": f"*{name} ti guarda da sopra la scrivania.* Buongiorno. Sono la dottoressa Elena. Prego, si accomodi.",
        "insegnante_matematica": f"*{name} è alla lavagna e si gira.* Buongiorno. Sono il professor Marco. Prendi posto.",
        "prof_italiano": f"*{name} chiude il libro con un sorriso.* Buongiorno, giovane amico. Che piacere conoscerti.",
        "insegnante_nuoto": f"*{name} sorride raggiante.* Ciao! Benvenuto! Pronto per tuffarti?",
    }
    return g.get(cid, f"*{name} ti sorride.* Ciao! Sono {name}.")
