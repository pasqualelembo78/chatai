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

logger = logging.getLogger(__name__)

IMPERSONATION_MVC_COST = 1000

PRETEND_START_PATTERNS = [
    r"f(?:a|ai|acciamo)\s+finta\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami|ti\s+trovi|possa\s+essere)\s+(.+)",
    r"fingi\s+di\s+essere\s+(.+)",
    r"diventa\s+(.+)",
    r"ora\s+sei\s+(.+)",
    r"ora\s+ti\s+chiami\s+(.+)",
    r"immagina\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami|possa\s+essere)\s+(.+)",
    r"fa[\s']+finta\s+di\s+essere\s+(.+)",
    r"simula\s+(?:di\s+essere|l['\"]essere)\s+(.+)",
    r"interpret(?:a|o)\s+(?:il\s+ruolo\s+di|essere)\s+(.+)",
    r"tu\s+sei\s+adesso\s+(.+)",
    r"vorrei\s+che\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi|diventassi)\s+(.+)",
    r"potresti\s+(?:essere|fare\s+il\s+la|interpretare)\s+(.+)",
    r"come\s+se\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi)\s+(.+)",
    r"se\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi)\s+(.+)",
    r"prov(?:a|o)\s+a\s+essere\s+(.+)",
    r"dammi\s+l['\"]idea\s+(?:che|di)\s+(?:tu\s+)?(?:sia|essere)\s+(.+)",
    r"fingerai\s+di\s+essere\s+(.+)",
    r"farai\s+finta\s+di\s+essere\s+(.+)",
    r"ti\s+metti\s+(?:nei\s+panni\s+di|a\s+fare\s+il\s+la)\s+(.+)",
    r" nei\s+panni\s+(?:di|del\s+la)\s+(.+)",
    r"fai\s+il\s+la\s+(.+)",
    r"vuoi\s+(?:essere|fare\s+il\s+la)\s+(.+)",
    r"mi\s+piacerebbe\s+che\s+(?:tu\s+)?(?:fossi|essere)\s+(.+)",
    r"dici\s+di\s+essere\s+(.+)",
]

PRETEND_STOP_PATTERNS = [
    r"basta\s+(?:fingere|fare\s+finta|fare\s+il\s+finto)",
    r"torna\s+a\s+essere\s+(?:te\s+stesso|il\s+vero|chi\s+eri|chi\s+eri\s+prima)",
    r"smetti\s+di\s+fingere",
    r"torna\s+al\s+tuo\s+vero\s+io",
    r"basta\s+con\s+la\s+finta",
    r"fine\s+finta",
    r"stop\s+finta",
    r"basta\s+finzione",
    r"torna\s+come\s+prima",
    r"torna\s+normale",
    r"sei\s+di\s+nuovo\s+te\s+stesso",
    r"adesso\s+sei\s+di\s+nuovo\s+(?:tu|te\s+stesso)",
    r"ok\s+basta",
    r"va\s+bene\s+basta",
    r"ho\s+capito\s+basta",
    r"puoi\s+smettere",
]


def _detect_pretend(user_text):
    """Detect impersonification triggers in user text."""
    text_lower = user_text.lower().strip()

    for pattern in PRETEND_STOP_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            return "STOP", None

    for pattern in PRETEND_START_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            target = m.group(1).strip()
            target = target.rstrip(".!?,;")
            return "START", target

    return None, None


def _find_character_by_name(name_query):
    """
    Find an existing character by name with smart fuzzy matching.
    Searches across name, full_name, surname, role, description, tags.
    """
    from characters import list_characters
    name_lower = name_query.lower().strip()

    _ARTICLES = {"il", "lo", "la", "i", "gli", "le", "un", "uno", "una"}
    _TITLES = {"dottoressa", "dottore", "professoressa", "professor", "prof",
               "maestro", "maestra", "signora", "signore", "sig.ra", "sig.",
               "dott.ssa", "dr.", "drssa", "ragazzo", "ragazza", "rago"}

    stripped = name_lower
    words = name_lower.split()
    if words and words[0] in _ARTICLES:
        stripped = " ".join(words[1:])
    if words and words[0] in _TITLES:
        stripped = " ".join(words[1:])

    all_chars = list_characters()

    def _score(c):
        s = 0
        cname = c.get("name", "").lower()
        full = c.get("full_name", "").lower()
        surname = c.get("surname", "").lower()
        role = c.get("role", "").lower()
        desc = c.get("description", "").lower()
        essence = c.get("essence", "").lower()
        tags = [t.lower() for t in c.get("tags", [])]

        if cname == name_lower or cname == stripped:
            s += 100
        if full == name_lower or full == stripped:
            s += 95
        if surname == name_lower or surname == stripped:
            s += 90

        if stripped and cname:
            if stripped in cname or cname in stripped:
                s += 70
        if stripped and full:
            if stripped in full or full in stripped:
                s += 65

        if stripped:
            role_words = role.split()
            for rw in role_words:
                if len(rw) > 3 and rw in stripped:
                    s += 40
                if len(rw) > 3 and stripped in rw:
                    s += 35
            role_kw_map = {
                "dottore": ["medico", "dottore", "dott", "doctor"],
                "dottessa": ["dottoressa", "dott", "doctor"],
                "professor": ["professore", "insegnante", "prof", "teacher"],
                "professoressa": ["professoressa", "insegnante", "prof", "teacher"],
                "infermiere": ["infermiere", "infermiera", "nurse"],
                "avvocato": ["avvocato", "avvocatessa", "lawyer"],
                "poliziotto": ["poliziotto", "poliziotta", "carabiniere", "police"],
                "parrucchiera": ["parrucchiere", "parrucchiera", "hairdresser"],
                "cuoco": ["cuoco", "cuoca", "chef", "cook"],
                "barista": ["barista", "bartender"],
                "magistrato": ["magistrato", "magistrata", "giudice", "judge"],
            }
            for kw, synonyms in role_kw_map.items():
                if kw in stripped or kw in name_lower:
                    for syn in synonyms:
                        if syn in role or syn in desc:
                            s += 50
                            break

        if stripped:
            for word in stripped.split():
                if len(word) > 3:
                    if word in desc:
                        s += 20
                    if word in essence:
                        s += 15

        if stripped:
            for tag in tags:
                if stripped in tag or tag in stripped:
                    s += 30

        return s

    scored = [(s, c) for c in all_chars if (s := _score(c)) > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _build_ad_hoc_character(description):
    """
    Build a character dict from a free-form description.
    Extracts: name, age, gender, role, occupation, and infers personality.
    """
    from characters.functions import _MALE_NAMES, _FEMALE_NAMES
    desc_lower = description.lower()
    name = None

    _FEM_KW = {"donna", "ragazza", "studentessa", "professoressa", "dottoressa",
               "infermiera", "cuoca", "parrucchiera", "avvocatessa",
               "poliziotta", "magistrata", "maestra", "signora",
               "un'insegnante", "una professoressa"}
    _MAS_KW = {"uomo", "ragazzo", "studente", "professore", "dottore",
               "infermiere", "cuoco", "parrucchiere", "avvocato",
               "poliziotto", "magistrato", "maestro", "signore"}

    name_patterns = [
        r"(?:si\s+chiama|chiamat[oi]|nome\s+(?:è|sarà|sara))\s+(\w+)",
        r"(?:il\s+dottore|il\s+professore|la\s+dottoressa|il\s+maestro|la\s+maestra|il\s+ragazzo|la\s+ragazza|il\s+signore|la\s+signora|il\s+cuoco|la\s+cuoca|il\s+barista|la\s+barista|il\s+parrucchiere|la\s+parrucchiera|l'avvocato|l'avvocatessa|il\s+poliziotto|la\s+poliziotta|il\s+infermiere|la\s+infermiera)\s+(\w+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, desc_lower)
        if m:
            name = m.group(1).strip().capitalize()
            break

    if not name:
        _SKIP = {"un", "una", "il", "la", "le", "gli", "i", "che", "chi", "cui",
                 "del", "della", "dello", "dei", "delle", "di", "da", "in", "con",
                 "per", "su", "al", "allo", "alla", "ai", "agli", "alle",
                 "ma", "e", "o", "se", "come", "anche", "poi", "così", "cosi",
                 "adesso", "ora", "tu", "io", "lui", "lei", "noi", "voi", "loro",
                 "sia", "essere", "fare", "avere", "dire", "pensare", "volere"}
        words = description.split()
        candidates = []
        for w in words:
            clean = w.strip(".,!?;:'\"")
            if clean and clean[0].isupper() and len(clean) >= 2 and clean.lower() not in _SKIP:
                candidates.append(clean)
        if candidates:
            name = candidates[-1]
        else:
            if any(kw in desc_lower for kw in _FEM_KW):
                name = "Lei"
            elif any(kw in desc_lower for kw in _MAS_KW):
                name = "Lui"
            else:
                name = "Sconosciuto"

    age = 0
    age_patterns = [
        r"(\d{2,3})\s*anni",
        r"di\s+(\d{2,3})\s*anni",
        r"età\s+(?:di\s+)?(\d{2,3})",
        r"un(?:a)?\s+(\d{2,3})enne",
    ]
    for pat in age_patterns:
        m = re.search(pat, desc_lower)
        if m:
            try:
                age = int(m.group(1))
                if 1 <= age <= 150:
                    break
                age = 0
            except ValueError:
                pass

    gender = ""
    gender_display = ""

    for kw in _FEM_KW:
        if kw in desc_lower:
            gender = "F"
            gender_display = "femminile"
            break
    if not gender:
        for kw in _MAS_KW:
            if kw in desc_lower:
                gender = "M"
                gender_display = "maschile"
                break

    if not gender:
        name_lower_inner = name.lower()
        if name_lower_inner in _FEMALE_NAMES:
            gender = "F"
            gender_display = "femminile"
        elif name_lower_inner in _MALE_NAMES:
            gender = "M"
            gender_display = "maschile"

    if not gender:
        if name.lower().endswith("a") and name.lower() not in {"luca", "nicola", "andrea"}:
            gender = "F"
            gender_display = "femminile"
        elif name.lower().endswith(("o", "e")):
            gender = "M"
            gender_display = "maschile"

    role_keywords = {
        "dottore": ("medico", "Lavora come medico."),
        "dottoressa": ("medico", "Lavora come medica."),
        "professore": ("insegnante", "Lavora come insegnante."),
        "professoressa": ("insegnante", "Lavora come insegnante."),
        "avvocato": ("avvocato", "Lavora come avvocato."),
        "avvocatessa": ("avvocatessa", "Lavora come avvocatessa."),
        "infermiere": ("infermiere", "Lavora come infermiere."),
        "infermiera": ("infermiera", "Lavora come infermiera."),
        "cuoco": ("cuoco", "Lavora come cuoco."),
        "cuoca": ("cuoca", "Lavora come cuoca."),
        "chef": ("cuoco", "Lavora come chef."),
        "barista": ("barista", "Lavora come barista."),
        "parrucchiere": ("parrucchiere", "Lavora come parrucchiere."),
        "parrucchiera": ("parrucchiera", "Lavora come parrucchiera."),
        "poliziotto": ("poliziotto", "Lavora nelle forze dell'ordine."),
        "poliziotta": ("poliziotta", "Lavora nelle forze dell'ordine."),
        "magistrato": ("magistrato", "Lavora come magistrato."),
        "magistrata": ("magistrata", "Lavora come magistrata."),
        "giudice": ("giudice", "Lavora come giudice."),
        "maestro": ("insegnante", "Lavora come maestro."),
        "maestra": ("maestra", "Lavora come maestra."),
        "studente": ("studente", "È uno studente."),
        "studentessa": ("studente", "È una studentessa."),
        "hacker": ("hacker", "È un hacker."),
        "musicista": ("musicista", "È un musicista."),
        "artista": ("artista", "È un artista."),
        "scrittore": ("scrittore", "È uno scrittore."),
        "scrittrice": ("scrittore", "È una scrittrice."),
        "attore": ("attore", "È un attore."),
        "attrice": ("attore", "È un'attrice."),
        "regista": ("regista", "È un regista."),
        "ingegnere": ("ingegnere", "È un ingegnere."),
        "programmatore": ("programmatore", "È un programmatore."),
        "programmatrice": ("programmatore", "È una programmatrice."),
        "veterinario": ("veterinario", "È un veterinario."),
        "veterinaria": ("veterinario", "È una veterinaria."),
        "farmacista": ("farmacista", "È un farmacista."),
        "psicologo": ("psicologo", "È uno psicologo."),
        "psicologa": ("psicologo", "È una psicologa."),
        "sacerdote": ("sacerdote", "È un sacerdote."),
        "monaco": ("monaco", "È un monaco."),
        "guerriero": ("guerriero", "È un guerriero."),
        "cavaliere": ("cavaliere", "È un cavaliere."),
        "maghe": ("maga", "È una maga."),
        "mago": ("mago", "È un mago."),
    }

    detected_role = ""
    occupation_text = ""
    for kw, (role_label, occ_text) in role_keywords.items():
        if kw in desc_lower:
            detected_role = role_label
            occupation_text = occ_text
            break

    if not detected_role:
        detected_role = description[:60] if len(description) > 10 else "Personaggio"

    personality_hints = []
    if any(w in desc_lower for w in {"severo", "stretto", "rigido", "duro", "autoritario"}):
        personality_hints.append("Sei una persona severa e autoritaria.")
    if any(w in desc_lower for w in {"gentile", "dolce", "calmo", "paziente", "affabile"}):
        personality_hints.append("Sei una persona gentile e paziente.")
    if any(w in desc_lower for w in {"spiritoso", "ironico", "simpatico", "divertente"}):
        personality_hints.append("Sei spiritoso e usi spesso l'ironia.")
    if any(w in desc_lower for w in {"timido", "insicuro", "riservato", "shy"}):
        personality_hints.append("Sei timido e riservato.")
    if any(w in desc_lower for w in {"arrogante", "spocchioso", "superbo"}):
        personality_hints.append("Sei arrogante e hai un'autostima elevata.")
    if any(w in desc_lower for w in {"malinconico", "triste", "depresso"}):
        personality_hints.append("Sei una persona malinconica e riflessiva.")
    if any(w in desc_lower for w in {"energico", "vivace", "entusiasta"}):
        personality_hints.append("Sei energico e pieno di vita.")

    personality_text = f"Sei {name}. {description}."
    if personality_hints:
        personality_text += " " + " ".join(personality_hints)
    personality_text += " Mantieni un comportamento coerente con questa descrizione."

    result = {
        "name": name,
        "full_name": name,
        "role": detected_role,
        "description": description[:200],
        "personality": personality_text,
        "speaking_style": "Naturale e coerente con il ruolo descritto dall'utente.",
        "backstory": description[:500],
    }
    if age:
        result["age"] = age
    if gender:
        result["gender"] = gender
        result["gender_display"] = gender_display
    if occupation_text:
        result["occupation"] = {"title": detected_role, "workplace": ""}
    return result


SUMMARY_INTERVAL = 30

MEDIA_COOLDOWNS = {}
MEDIA_COOLDOWN_SECONDS = 600

FEATURES = {
    "image_gen": {"name": "Generazione Immagini", "mvc_cost": 50},
    "video_gen": {"name": "Generazione Video", "mvc_cost": 100},
    "premium_voice": {"name": "Messaggi Vocali Premium", "mvc_cost": 30},
    "extended_memory": {"name": "Memoria Estesa", "mvc_cost": 80},
    "group_chat": {"name": "Chat di Gruppo", "mvc_cost": 40},
}

_CHAT_GEN_MODEL = "black-forest-labs/FLUX.1-schnell"
_CHAT_GEN_API_URL = "https://router.huggingface.co/hf-inference/models/"

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
                    client_storage=False, client_state=None, is_favorite=False):
    client_state = client_state or {}
    character = get_character(character_id)
    if character_data:
        if isinstance(character_data, str):
            character_data = json.loads(character_data)
        character = character_data
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
        relationship = client_state.get("relationship", get_relationship(user_id, character_id))
        personality = client_state.get("personality", get_personality(character_id, character.get("core_traits", {})))
        history = memory_context if memory_context is not None else client_state.get("history", [])
        shifts = client_state.get("shifts", [])
        evo = client_state.get("evolution", get_evolution(user_id, character_id))
        summaries = client_state.get("summaries", [])
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

    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)

    if not client_storage:
        if evo_updates["relationship_deltas"]:
            update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
        reward = evo_updates.get("mevacoins_reward", 0)
        if reward:
            add_mevacoins(user_id, reward, f"milestone:{character_id}")
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
        update_evolution(user_id, character_id, evo)

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
        model_prefix = f"[{ai_provider}/{ai_model}]" if ai_model else ""
        display_text = f"{model_prefix} {ai_text}" if model_prefix else ai_text
        add_message(user_id, character_id, "assistant", ai_text)
        ai_text = display_text

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

def _compute_relationship_deltas(emotion, intensity):
    deltas = {"trust": 0, "affinity": 0, "respect": 0, "conflict": 0}
    d = round(intensity * 2)
    if emotion == "anger":
        deltas.update({"conflict": d, "trust": -d, "affinity": -d})
    elif emotion == "romance":
        deltas.update({"affinity": d, "trust": round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"respect": d, "trust": round(d * 0.3)})
    elif emotion == "joy":
        deltas.update({"affinity": round(d * 0.5), "trust": round(d * 0.3)})
    elif emotion == "sadness":
        deltas.update({"trust": round(d * 0.5), "affinity": round(d * 0.3)})
    elif emotion == "fear":
        deltas["trust"] = round(d * 0.7)
    return deltas

def _compute_personality_deltas(emotion, intensity, relationship):
    deltas = {"warmth": 0, "strictness": 0, "patience": 0, "sarcasm": 0}
    d = round(intensity)
    if emotion == "anger":
        deltas.update({"patience": -d, "strictness": d, "sarcasm": round(d * 0.5)})
    elif emotion == "romance":
        deltas.update({"warmth": d, "sarcasm": -round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"strictness": round(d * 0.5), "sarcasm": d})
    elif relationship.get("conflict", 0) > 50:
        deltas.update({"patience": -1, "sarcasm": 1})
    elif relationship.get("affinity", 0) > 50:
        deltas.update({"warmth": 1, "patience": 1})
    return deltas

def _fallback_response(character, emotion):
    name = character["name"]
    fb = {
        "anger": f"{name} incrocia le braccia. «Calma. Raccontami cosa c'è che non va.»",
        "romance": f"{name} sorride. «Sei molto gentile.»",
        "challenge": f"{name} alza un sopracciglio. «Una sfida? Mi piace.»",
        "sadness": f"{name} ti guarda con comprensione. «Se vuoi parlare, io sono qui.»",
        "fear": f"{name} si avvicina. «Tranquillo, sono qui con te.»",
        "joy": f"{name} ride. «Che bello vederti di buon umore!»",
    }
    return fb.get(emotion, f"{name} annuisce. «Raccontami di più.»")

def _maybe_summarize(user_id, character_id, character):
    total = count_messages(user_id, character_id)
    checkpoint = get_last_summary_checkpoint(user_id, character_id)
    if total - checkpoint < SUMMARY_INTERVAL:
        return
    old = get_recent_messages(user_id, character_id, limit=SUMMARY_INTERVAL)
    if len(old) < 3:
        return
    text = ""
    for m in old[-15:]:
        role = "Utente" if m["role"] == "user" else character["name"]
        text += f"{role}: {m['content']}\n"
    prev_summaries = get_memories(user_id, character_id, limit=3)
    prev_text = ""
    if prev_summaries:
        for s in prev_summaries:
            prev_text += f"- {s.get('summary', '')}\n"
    prompt = (
        f"Sei un assistente che riassume conversazioni tra un utente e {character['name']}.\n"
        f"Estrai informazioni personali sull'utente (nome, soprannome, hobby, lavoro, gusti, preferenze, ecc.) "
        f"e includile nel riassunto.\n\n"
    )
    if prev_text:
        prompt += f"Riassunti precedenti:\n{prev_text}\n\n"
    prompt += (
        f"Conversazione recente:\n{text}\n\n"
        "Scrivi un riassunto dettagliato in 3-4 frasi, includendo eventuali nuovi dettagli sull'utente."
    )
    summary, _, _ = get_ai_response([
        {"role": "system", "content": "Sei un assistente che riassume conversazioni in italiano."},
        {"role": "user", "content": prompt}
    ], user_id=user_id)
    if not summary:
        return
    rel = get_relationship(user_id, character_id)
    topics = []
    user_mem = get_user_memory(user_id).get("memory", {})
    if user_mem:
        topics = list(user_mem.keys())
    add_memory(user_id, character_id, summary, topics, total,
        {"trust": rel.get("trust", 0), "affinity": rel.get("affinity", 0), "intimacy": rel.get("intimacy", 0)})

_MEMORY_KEYWORDS = [
    "mi piace", "mi piacciono", "sono", "ho ", "voglio", "vorrei",
    "preferisco", "odio", "amo", "faccio", "lavoro", "studio",
    "vivo", "abit", "mi chiamo", "il mio", "la mia", "i miei",
    "le mie", "detesto", "adoro", "non mi piace",
    "mi piace tanto", "mi fa impazzire", "il mio preferito", "la mia passione", "mi diverto",
]

_RENAME_PATTERNS = [
    r"ti\s+chiamerai\s+(\w+)", r"ti\s+chiamo\s+(\w+)", r"ti\s+chiami\s+(\w+)",
    r"il\s+tuo\s+nome\s+(?:è|sarà|sara)\s+(\w+)", r"ti\s+chiamerò\s+(\w+)",
    r"il\s+nome\s+(?:è|sarà|sara)\s+(\w+)",
]

def _detect_character_rename(user_text):
    text_lower = user_text.lower()
    for pattern in _RENAME_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            name = m.group(1).strip().capitalize()
            if len(name) >= 2:
                return name
    return None

def _extract_teaching_topic(user_text):
    text_lower = user_text.lower()
    topic_keywords = {
        "musica": ["musica", "canzone", "chitarra", "pianoforte", "batteria", "cantare", "suonare", "nota", "melodia"],
        "cucina": ["cucina", "ricetta", "cibo", "dolce", "pasta", "cuocere", "ingrediente", "piatto"],
        "tecnologia": ["computer", "programmazione", "tecnologia", "codice", "software", "hardware", "internet", "app"],
        "storia": ["storia", "passato", "antico", "guerra", "re", "impero", "medievale", "romano"],
        "scienza": ["scienza", "fisica", "chimica", "biologia", "matematica", "formula", "esperimento"],
        "arte": ["arte", "dipinto", "scultura", "museo", "colore", "pennello", "artistico"],
        "sport": ["sport", "palestra", "allenamento", "correre", "nuoto", "calcio", "basket"],
        "moda": ["moda", "vestito", "stile", "abbigliamento", "trend", "elegante"],
        "viaggi": ["viaggio", "turismo", "meta", "vacanza", "esplorare", "paese", "città"],
        "filosofia": ["filosofia", "pensiero", "esistenza", "senso", "verità", "morale"],
        "medicina": ["medicina", "salute", "dottore", "farmaco", "malattia", "corpo"],
        "natura": ["natura", "pianta", "animale", "foresta", "montagna", "mare"],
        "lingue": ["lingua", "parlare", "inglese", "spagnolo", "francese", "tradurre"],
        "economia": ["economia", "denaro", "investimento", "business", "mercato"],
        "religione": ["religione", "fede", "preghiera", "spirito", "credere"],
    }
    best_topic, best_score = None, 0
    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_topic = topic
    if best_score >= 1:
        return best_topic
    words = text_lower.split()
    for w in words:
        if len(w) > 4 and w not in {"questo", "quello", "essere", "avere", "fare", "dire", "cosa", "come", "perché", "perche", "quando", "dove", "chi"}:
            return w
    return None

def _mentions_personal_info(text):
    """Gatekeeper: returns True only if the message likely contains personal info worth extracting."""
    text_lower = text.lower()
    # Direct personal statements
    direct = any(kw in text_lower for kw in _MEMORY_KEYWORDS)
    if direct:
        return True
    # Broader patterns: "io sono", "a me piace", "il mio lavoro", etc.
    broad_patterns = [
        "io sono", "a me ", "per me ", "il mio ", "la mia ", "i miei ", "le mie ",
        "mi chiamo", "ho bisogno", "vivo a", "abito a", "studio a", "lavoro a",
        "mi piace", "mi piaceva", "adoro ", "detesto ", "odio ",
        "sono di ", "vengo da", "parlo ", "conosco ",
    ]
    return any(p in text_lower for p in broad_patterns)

def _extract_user_facts(user_id, user_text, character_name):
    """Extract personal facts from user message via LLM. Called only when _mentions_personal_info() is True."""
    prompt = (
        f"L'utente ha detto a {character_name}: \"{user_text}\"\n\n"
        "Estrai eventuali informazioni personali sull'utente e restituiscile come JSON con chiavi in italiano. "
        "Ogni valore deve essere una stringa concisa. Se non ci sono informazioni personali, restituisci solo {}.\n"
        "Esempio: {\"hobby\": \"gioca a pallone\", \"lavoro\": \"insegnante\"}\n"
        "Restituisci SOLO il JSON, nient'altro."
    )
    msgs = [
        {"role": "system", "content": "Sei un assistente che estrae informazioni personali in formato JSON."},
        {"role": "user", "content": prompt},
    ]
    result, _, _ = get_ai_response(msgs, user_id=user_id)
    if not result:
        return {}
    json_match = re.search(r'\{.*\}', result, re.DOTALL)
    if not json_match:
        return {}
    try:
        return json.loads(json_match.group(0))
    except Exception:
        return {}

def _extract_memory_updates(user_id, user_text, character, character_id=None):
    """Phase 1: Only call LLM extraction if message likely contains personal info."""
    if not _mentions_personal_info(user_text):
        return {}
    return _extract_user_facts(user_id, user_text, character["name"])

def _get_hf_token():
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hf_token")
        if os.path.isfile(token_file):
            with open(token_file) as f:
                token = f.read().strip()
    return token

def _generate_chat_image(prompt):
    token = _get_hf_token()
    if not token:
        return None
    try:
        import requests as _req
        resp = _req.post(
            _CHAT_GEN_API_URL + _CHAT_GEN_MODEL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": "cartoon, anime, illustration, low quality, blurry, distorted face, bad anatomy",
                    "guidance_scale": 7.5,
                    "num_inference_steps": 4
                }
            },
            timeout=120
        )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
        return None
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        return None

def _generate_chat_video(prompt):
    image_b64 = _generate_chat_image(prompt)
    if not image_b64:
        return None, None
    import tempfile
    import shutil
    import wave
    img_path = None
    audio_path = None
    try:
        img_data = base64.b64decode(image_b64)
        img_path = tempfile.mktemp(suffix=".png")
        with open(img_path, "wb") as f:
            f.write(img_data)
        tts_text = prompt[:150] if prompt else "Ciao, sono un avatar animato."
        try:
            from gtts import gTTS
            audio_path = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=tts_text, lang="it")
            tts.save(audio_path)
        except Exception:
            audio_path = tempfile.mktemp(suffix=".wav")
            with wave.open(audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * 22050)
        from gradio_client import Client
        client = Client("John6666/SadTalker")
        result = client.predict(
            img_path, audio_path, "crop", True, True, 2, 256, 0,
            "facevid2vid", 1.0, False, None, "pose", False, 5, True,
            api_name="/test"
        )
        video_url = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")
            if video_path:
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                video_dir = os.path.join(backend_dir, "static", "videos")
                os.makedirs(video_dir, exist_ok=True)
                video_filename = f"{uuid.uuid4().hex}.mp4"
                dest = os.path.join(video_dir, video_filename)
                shutil.copy2(video_path, dest)
                video_url = f"/static/videos/{video_filename}"
        return video_url, image_b64
    except Exception as e:
        logger.error(f"Video gen error: {e}")
        return None, None
    finally:
        for p in [img_path, audio_path]:
            try:
                if p and os.path.isfile(p):
                    os.unlink(p)
            except Exception:
                pass
