"""Motore di chat principale (facade).

Le funzioni di supporto pesanti sono state spostate in moduli dedicati per
snellire questo file; qui vengono re-importate così che chi fa
`from chat_engine import process_message, FEATURES` continui a funzionare.
"""
import json
import logging
import re
import os
import time
import base64
import uuid
import random
import asyncio
from datetime import datetime

from storage import (
    get_relationship, update_relationship,
    get_personality, update_personality,
    get_world_state,
    add_message, get_recent_messages, count_messages,
    add_memory, get_memories, get_last_summary_checkpoint,
    get_recent_shifts,
    get_user_memory, update_user_memory,
    get_evolution, update_evolution,
    get_user_preferences,
    add_mevacoins,
    is_content_unlocked,
    credit_referral_first_message,
    count_all_user_messages,
    get_user_personality, update_user_personality as update_user_personality_db,
    get_user_world_state,
    update_user_memory_enhanced, decay_user_memory,
    start_conversation_session, get_temporal_context,
    share_memory_across_characters, get_shared_memories,
    update_conversation_topics, get_recent_topics,
)
from ai_engine import get_ai_response
from prompt_builder import build_messages
from emotion_engine import detect_emotion
from characters import get_character, get_categories
from evolution_engine import evaluate_evolution
import audio_utils
import image_utils

# Implementazioni suddivise per argomento
from chat_pretend import PRETEND_START_PATTERNS, PRETEND_STOP_PATTERNS, _detect_pretend
from chat_characters import _find_character_by_name, _build_ad_hoc_character
from chat_deltas import _compute_relationship_deltas, _compute_personality_deltas, _fallback_response
from chat_memory import (
    _maybe_summarize, _MEMORY_KEYWORDS, _RENAME_PATTERNS, _detect_character_rename,
    _extract_teaching_topic, _mentions_personal_info, _extract_user_facts, _extract_memory_updates,
)
from chat_media import _generate_chat_image, _generate_chat_video

logger = logging.getLogger(__name__)

IMPERSONATION_MVC_COST = 1000

MEDIA_COOLDOWNS = {}
MEDIA_COOLDOWN_SECONDS = 600

FEATURES = {
    "image_gen": {"name": "Generazione Immagini", "mvc_cost": 50},
    "video_gen": {"name": "Generazione Video", "mvc_cost": 100},
    "premium_voice": {"name": "Messaggi Vocali Premium", "mvc_cost": 30},
    "extended_memory": {"name": "Memoria Estesa", "mvc_cost": 80},
    "group_chat": {"name": "Chat di Gruppo", "mvc_cost": 40},
    "no_ads": {"name": "Nessuna pubblicità", "mvc_cost": 120},
}


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


def process_message(user_id, character_id, text, username="Utente",
                     memory_context=None, user_memory=None,
                     character_data=None, image_base64="", image_mime="image/jpeg",
                     client_storage=False, client_state=None, is_favorite=False,
                     tone=None):
    client_state = client_state or {}
    character = get_character(character_id)
    if character_data:
        if isinstance(character_data, str):
            character_data = json.loads(character_data)
        # SECURITY: Only allow safe fields to be overridden from client.
        # Never allow system_prompt, core_traits, knowledge_domains, or other
        # prompt-injection vectors to be replaced by client-provided data.
        SAFE_CHARACTER_FIELDS = {
            "name", "description", "avatar", "category", "tags",
            "visibility", "is_adult", "is_favorite", "rating", "stats"
        }
        # Merge safe fields only
        for key, value in character_data.items():
            if key in SAFE_CHARACTER_FIELDS:
                character[key] = value
    if not character:
        return None
    if not _check_character_access(user_id, character):
        return None

    def _check_cooldown():
        now = time.time()
        last = MEDIA_COOLDOWNS.get(user_id, 0)
        remaining = MEDIA_COOLDOWN_SECONDS - (now - last)
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            return f"⏳ Devi aspettare {mins}m {secs}s prima di generare altro contenuto."
        return None

    GEN_PREFIX = "/genera"
    MOVE_PREFIX = "/muovi"

    stripped = text.strip()
    if stripped.startswith(GEN_PREFIX) or stripped.startswith(MOVE_PREFIX):
        is_video = stripped.startswith(MOVE_PREFIX)
        feature_id = "video_gen" if is_video else "image_gen"
        if not is_content_unlocked(user_id, "feature", feature_id):
            feat = FEATURES[feature_id]
            return {
                "ai_text": f"🔒 Per usare {feat['name']} serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.",
                "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "neutro", "intensity": 0.0,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }
        cooldown_msg = _check_cooldown()
        if cooldown_msg:
            return {
                "ai_text": cooldown_msg, "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "neutro", "intensity": 0.0,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }

        prefix_len = len(MOVE_PREFIX) if is_video else len(GEN_PREFIX)
        prompt = stripped[prefix_len:].strip()
        if not prompt:
            prompt = f"Ritratto fotorealistico di {character.get('name', 'una persona')}, {character.get('description', '')}"
        else:
            prompt = f"Photorealistic portrait of {prompt}, cinematic lighting, detailed face, natural skin texture, 4K"

        now = time.time()
        if is_video:
            video_url, image_b64 = _generate_chat_video(prompt)
            if video_url:
                MEDIA_COOLDOWNS[user_id] = now
                return {
                    "ai_text": "🎬 Video animato generato con SadTalker!",
                    "ai_provider": "flux+sadtalker", "ai_model": "FLUX.1-schnell+SadTalker",
                    "is_fallback": False, "emotion": "felice", "intensity": 0.5,
                    "character": character, "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                    "generated_image": image_b64, "generated_video": video_url,
                }
            else:
                image_b64 = _generate_chat_image(prompt)
                if image_b64:
                    MEDIA_COOLDOWNS[user_id] = now
                    return {
                        "ai_text": "⚠️ Animazione non riuscita, ma ecco l'immagine generata.",
                        "ai_provider": "flux", "ai_model": "FLUX.1-schnell",
                        "is_fallback": False, "emotion": "neutro", "intensity": 0.3,
                        "character": character, "memory_updates": None,
                        "evo_updates": {"new_stage": None, "unlocked": []},
                        "generated_image": image_b64,
                    }
                return {
                    "ai_text": "❌ Errore nella generazione. Riprova più tardi.",
                    "ai_provider": "system", "ai_model": "",
                    "is_fallback": False, "emotion": "triste", "intensity": 0.3,
                    "character": character, "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                }

        image_b64 = _generate_chat_image(prompt)
        if image_b64:
            MEDIA_COOLDOWNS[user_id] = now
            return {
                "ai_text": "✨ Ecco l'immagine generata con FLUX.1-schnell!",
                "ai_provider": "flux", "ai_model": "FLUX.1-schnell",
                "is_fallback": False, "emotion": "felice", "intensity": 0.5,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
                "generated_image": image_b64,
            }
        else:
            return {
                "ai_text": "❌ Errore nella generazione dell'immagine. Riprova più tardi.",
                "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "triste", "intensity": 0.3,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }

    image_desc = None
    if image_base64:
        image_desc = image_utils.describe_image(image_base64, image_mime)
        if image_desc:
            text = (text + "\n\n[IMAGE: " + image_desc + "]") if text else "[IMAGE: " + image_desc + "]"

    emotion, intensity, emotions = detect_emotion(text)

    if client_storage:
        _cs_rel = client_state.get("relationship")
        relationship = _cs_rel if isinstance(_cs_rel, dict) else get_relationship(user_id, character_id, character.get("core_traits", {}))
        _cs_per = client_state.get("personality")
        personality = _cs_per if isinstance(_cs_per, dict) else get_user_personality(user_id, character_id, character.get("core_traits", {}))
        history = memory_context if memory_context is not None else (client_state.get("history") or [])
        shifts = client_state.get("shifts") or []
        _cs_evo = client_state.get("evolution")
        evo = _cs_evo if isinstance(_cs_evo, dict) and "flags" in _cs_evo else get_evolution(user_id, character_id)
        summaries = client_state.get("summaries") or []
        # SECURITY: Client-provided state is used as-is but never replaces server-side
        # critical data. Log a warning if client state differs significantly.
        if history and len(history) > 100:
            logger.warning(f"Client provided excessive history length: {len(history)}")
            history = history[-100:]  # Cap to reasonable limit
    else:
        relationship = get_relationship(user_id, character_id)
        # Phase 2: Use per-user personality (falls back to shared if not yet personalized)
        personality = get_user_personality(user_id, character_id, character.get("core_traits", {}))
        _msg_limit = 50 if is_content_unlocked(user_id, "feature", "extended_memory") else 20
        history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=_msg_limit)
        shifts = get_recent_shifts(user_id, character_id)
        evo = get_evolution(user_id, character_id)
        summaries = get_memories(user_id, character_id, limit=5)

    # ─── Impersonification detection ─────────────────────────────
    impersonate_override = None
    pretend_action, pretend_target = _detect_pretend(text) if text else (None, None)
    logger.info(f"Pretend detect: action={pretend_action} target={pretend_target} user={user_id} char={character_id}")

    if pretend_action == "STOP":
        evo["flags"]["impersonating"] = False
        evo["flags"]["impersonate_target"] = ""
        evo["flags"].pop("impersonate_data", None)
        if not client_storage:
            update_evolution(user_id, character_id, evo)
        logger.info(f"Pretend stop: user={user_id} char={character_id}")
    elif pretend_action == "START" and pretend_target:
        if not is_content_unlocked(user_id, "feature", "impersonation"):
            char_name = character.get("name", "io")
            premium_msg = (
                f"*{char_name} scuote la testa.* "
                f"Mi dispiace, ma questa è una funzionalità premium. "
                f"Per finta di essere qualcun altro devi sbloccarla con {IMPERSONATION_MVC_COST} MevaCoins. "
                f"Vai nelle impostazioni per sbloccarla!"
            )
            return {
                "ai_text": premium_msg,
                "ai_provider": "system",
                "ai_model": "",
                "is_fallback": False,
                "emotion": "neutro",
                "intensity": 0.0,
                "character": character,
                "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
                "impersonating": False,
                "impersonate_target": "",
                "premium_required": True,
                "unlock_cost": IMPERSONATION_MVC_COST,
            }
        target_char = _find_character_by_name(pretend_target)
        if not target_char:
            target_char = _build_ad_hoc_character(pretend_target)
        evo["flags"]["impersonating"] = True
        evo["flags"]["impersonate_target"] = pretend_target
        evo["flags"]["impersonate_data"] = target_char
        evo["flags"]["original_character_id"] = character_id
        if not client_storage:
            update_evolution(user_id, character_id, evo)
        impersonate_override = target_char
        character = {**character, **target_char}
        logger.info(f"Pretend start: user={user_id} char={character_id} target={pretend_target}")
    elif evo.get("flags", {}).get("impersonating"):
        saved_target = evo["flags"].get("impersonate_target", "")
        saved_data = evo["flags"].get("impersonate_data")
        if saved_data:
            impersonate_override = saved_data
            character = {**character, **saved_data}
            logger.info(f"Pretend restore: user={user_id} target={saved_target}")
        elif saved_target:
            target_char = _find_character_by_name(saved_target)
            if target_char:
                impersonate_override = target_char
                character = {**character, **target_char}
                evo["flags"]["impersonate_data"] = target_char
                if not client_storage:
                    update_evolution(user_id, character_id, evo)
                logger.info(f"Pretend re-lookup: user={user_id} target={saved_target}")

    if impersonate_override and impersonate_override.get("core_traits"):
        personality = {**impersonate_override["core_traits"]}

    # Phase 2: Per-user world state
    if client_storage:
        world_state = get_world_state()
    else:
        world_state = get_user_world_state(user_id)
    user_prefs = get_user_preferences(user_id)
    user_gender = user_prefs.get("user_gender") or None
    user_age = user_prefs.get("user_age") or None
    sexual_orientation = user_prefs.get("sexual_orientation") or None

    if not client_storage:
        is_first = count_all_user_messages(user_id) == 0
        add_message(user_id, character_id, "user", text)
        if is_first:
            credit_referral_first_message(user_id)
        # Phase 5: Track conversation session
        start_conversation_session(user_id, character_id)
        # Phase 8: Track conversation topics
        update_conversation_topics(user_id, character_id, text)
        # Missioni MVC: assegna ricompense se una missione odierna/settimanale
        # è stata completata. Fail-safe: un errore qui non deve mai bloccare
        # la chat dell'utente.
        try:
            from storage.missions import award_missions
            award_missions(user_id)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("award_missions skipped", exc_info=True)

    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)

    if not client_storage:
        if evo_updates["relationship_deltas"]:
            update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
        if evo_updates["trait_modifiers"]:
            # Phase 2: Update per-user personality
            update_user_personality_db(user_id, character_id, evo_updates["trait_modifiers"])
        if not character.get("evolution"):
            rel_deltas = _compute_relationship_deltas(emotion, intensity)
            if any(v != 0 for v in rel_deltas.values()):
                update_relationship(user_id, character_id, rel_deltas)
            pers_deltas = _compute_personality_deltas(emotion, intensity, relationship)
            if any(v != 0 for v in pers_deltas.values()):
                # Phase 2: Update per-user personality
                update_user_personality_db(user_id, character_id, pers_deltas)
        # Persist the evolution flags (one_shot / cooldown) BEFORE granting the
        # MevaCoins reward, so a failure after payout can't re-trigger it.
        update_evolution(user_id, character_id, evo)
        reward = evo_updates.get("mevacoins_reward", 0)
        if reward:
            add_mevacoins(user_id, reward, f"milestone:{character_id}")

    learned = evo.setdefault("learned", {"topics": [], "personality_drift": {}, "new_skills": []})
    knowledge = character.get("knowledge_domains", {})
    ignorance_list = knowledge.get("ignorance", [])
    text_lower = text.lower()

    is_blank = character.get("id") == "blank" or (
        not character.get("full_name") and
        not character.get("knowledge_domains", {}).get("expertise") and
        not character.get("knowledge_domains", {}).get("familiarity")
    )
    if is_blank:
        teaching_patterns = [
            "ti insegno", "ti spiego", "il che significa", "in pratica",
            "come funziona", "la regola è", "devi sapere", "è importante",
            "impara che", "sappi che", "cos'è", "significa che",
            "per esempio", "in altre parole", "in sintesi",
        ]
        teaching_detected = any(p in text_lower for p in teaching_patterns)
        topic_indicators = [
            "la musica è", "la scienza è", "la storia è", "la matematica",
            "il computing", "la programmazione", "la cucina è", "lo sport",
            "l'arte è", "la filosofia", "la letteratura", "la medicina",
        ]
        topic_detected = any(t in text_lower for t in topic_indicators)
        if teaching_detected or topic_detected:
            topic_label = _extract_teaching_topic(text)
            if topic_label and topic_label not in learned.get("topics", []):
                learned.setdefault("topics", []).append(topic_label)
                learned.setdefault("new_skills", []).append(topic_label)
                if topic_label not in knowledge.get("expertise", []):
                    knowledge.setdefault("expertise", []).append(topic_label)
                    character["knowledge_domains"] = knowledge
        personality_labels = {
            "joy": "allegro", "romance": "affettuoso", "challenge": "curioso",
            "sadness": "empatico", "anger": "passionale",
        }
        p_label = personality_labels.get(emotion)
        if p_label:
            learned.setdefault("personality_drift", {})
            current = learned["personality_drift"].get(p_label, 0.0)
            learned["personality_drift"][p_label] = round(min(3.0, current + 0.05), 2)

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

    if not client_storage:
        update_evolution(user_id, character_id, evo)

    new_name = _detect_character_rename(text)
    if new_name:
        evo["flags"]["custom_name"] = new_name
        if not client_storage:
            update_evolution(user_id, character_id, evo)

    if evo.get("flags", {}).get("custom_name"):
        character = {**character, "name": evo["flags"]["custom_name"]}

    memory_updates = _extract_memory_updates(user_id, text, character, character_id)
    if not client_storage:
        if memory_updates:
            wrapped = {}
            for key, val in memory_updates.items():
                wrapped[key] = {"value": val, "source": character_id, "source_name": character["name"]}
            # Phase 3: Use enhanced memory update with importance scoring
            update_user_memory_enhanced(user_id, wrapped, source_character=character_id, source_name=character["name"])
            # Phase 7: Share important facts across all characters
            for key, val in memory_updates.items():
                val_str = val if isinstance(val, str) else val.get("value", str(val)) if isinstance(val, dict) else str(val)
                if len(val_str) > 3:
                    share_memory_across_characters(user_id, key, val_str, character_id, character["name"])
        # Phase 3: Apply temporal decay (run periodically, cheap check)
        if random.random() < 0.05:  # 5% chance per message
            try:
                decay_user_memory(user_id)
            except Exception as e:
                logger.warning(f"Memory decay failed: {e}")
        stored = get_user_memory(user_id).get("memory", {})
        if stored:
            # Phase 3: Get most relevant memories, not all
            user_memory = stored

    evo["dialog_hints"] = evo_updates.get("dialog_hints", [])
    evo["_just_unlocked"] = evo_updates.get("unlocked", [])

    _total_msgs = count_messages(user_id, character_id)

    # Phase 5: Get temporal context for prompt
    temporal_context = {}
    recent_topics = []
    shared_mems = []
    if not client_storage:
        try:
            temporal_context = get_temporal_context(user_id, character_id)
            recent_topics = get_recent_topics(user_id, character_id, days=7, limit=5)
            shared_mems = get_shared_memories(user_id, limit=5)
        except Exception as e:
            logger.warning(f"Memory context failed: {e}")

    messages = build_messages(
        character, {"emotion": emotion, "intensity": intensity},
        relationship, personality, world_state, text, user_id, history,
        shifts, username, user_memory=user_memory, summaries=summaries,
        evolution=evo, is_favorite=is_favorite, total_messages=_total_msgs,
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
        temporal_context=temporal_context, recent_topics=recent_topics,
        shared_memories=shared_mems,
        impersonate_override=impersonate_override,
    )

    TONE_HINTS = {
        "divertente": "ISTRUZIONE DI TONO: mantieni un tono scherzoso e divertente, usa battute leggere.",
        "romantico": "ISTRUZIONE DI TONO: mantieni un tono romantico e dolce, con parole affettuose.",
        "protettivo": "ISTRUZIONE DI TONO: mantieni un tono protettivo e rassicurante, come chi veglia sull'utente.",
        "energico": "ISTRUZIONE DI TONO: mantieni un tono energico e vivace.",
    }
    if tone and tone in TONE_HINTS and messages:
        # Inserisce subito dopo il system prompt iniziale.
        messages.insert(1, {"role": "system", "content": TONE_HINTS[tone]})

    logger.info(f"get_ai_response: impersonate={impersonate_override is not None}")
    ai_text, ai_provider, ai_model = get_ai_response(messages, user_id=user_id)
    logger.info(f"AI response: provider={ai_provider} model={ai_model} len={len(ai_text) if ai_text else 0}")
    if not ai_text:
        ai_text = _fallback_response(character, emotion)
        ai_provider = "fallback"
        ai_model = ""
        is_fallback = True
    else:
        is_fallback = False

    if not is_fallback and not client_storage:
        # Keep ai_text as-is (no provider/model prefix for users)
        add_message(user_id, character_id, "assistant", ai_text)

    if not client_storage:
        try:
            _maybe_summarize(user_id, character_id, character)
        except Exception as e:
            logger.warning(f"Summarize failed: {e}")

    result = {
        "ai_text": ai_text, "ai_provider": ai_provider, "ai_model": ai_model,
        "is_fallback": is_fallback, "emotion": emotion, "intensity": intensity,
        "character": character, "memory_updates": memory_updates,
        "evo_updates": {"new_stage": evo_updates.get("new_stage"), "unlocked": evo_updates.get("unlocked", [])},
        "impersonating": evo.get("flags", {}).get("impersonating", False),
        "impersonate_target": evo.get("flags", {}).get("impersonate_target", ""),
    }

    if client_storage:
        if evo_updates.get("relationship_deltas"):
            for k, v in evo_updates["relationship_deltas"].items():
                relationship[k] = max(0, min(100, relationship.get(k, 0) + v))
        if evo_updates.get("trait_modifiers"):
            for trait, delta in evo_updates["trait_modifiers"].items():
                personality[trait] = max(0, min(10, personality.get(trait, 5) + delta))
        result["client_state"] = {
            "relationship": relationship, "personality": personality,
            "evolution": evo, "shifts": shifts, "summaries": summaries,
            "memory_updates": memory_updates,
            "learned": evo.get("learned", {"topics": [], "personality_drift": {}, "new_skills": []}),
        }

    return result
