"""Configurazione e helper condivisi per il motore di import personaggi."""

import json
import os
import re
import time
import random
import threading
import urllib.request
import urllib.parse
import logging

logger = logging.getLogger(__name__)

# ── Database Registry ─────────────────────────────────────────────────────────

SOURCES = {
    "charactercodex": {
        "id": "charactercodex",
        "name": "CharacterCodex (HuggingFace)",
        "description": "16K personaggi da libri, manga, film, giochi. Dataset NousResearch/CharacterCodex.",
        "url": "https://huggingface.co/datasets/NousResearch/CharacterCodex",
        "api": "huggingface_rows",
        "dataset": "NousResearch/CharacterCodex",
        "estimated_count": 16000,
        "icon": "📚",
        "default": True,
    },
    "characterhub": {
        "id": "characterhub",
        "name": "CharacterHub Open Source",
        "description": "Personaggi da CharacterHub con descrizioni dettagliate e personalità.",
        "url": "https://huggingface.co/datasets/FreedomIntelligence/characterhub-open-source",
        "api": "huggingface_rows",
        "dataset": "FreedomIntelligence/characterhub-open-source",
        "estimated_count": 12000,
        "icon": "🎭",
        "default": False,
    },
    "lmsys_conversations": {
        "id": "lmsys_conversations",
        "name": "LMSYS Chatbot Conversations",
        "description": "Conversazioni chatbot con personaggi e ruoli definiti.",
        "url": "https://huggingface.co/datasets/lmsys/chatbot_conversations",
        "api": "huggingface_rows",
        "dataset": "lmsys/chatbot_conversations",
        "estimated_count": 5000,
        "icon": "💬",
        "default": False,
    },
    "maltezos": {
        "id": "maltezos",
        "name": "Maltezos Character Dataset",
        "description": "Dataset di personaggi con backstory e tratti di personalità.",
        "url": "https://huggingface.co/datasets/maltezos/character-dataset",
        "api": "huggingface_rows",
        "dataset": "maltezos/character-dataset",
        "estimated_count": 8000,
        "icon": "📖",
        "default": False,
    },
}

# ── Genre → Category mapping ──────────────────────────────────────────────────

GENRE_CATEGORY_MAP = {
    "fantasy": "fantasy", "sci-fi": "sci-fi", "science fiction": "sci-fi",
    "horror": "horror", "romance": "romantici", "mystery": "detective",
    "thriller": "detective", "comedy": "intrattenimento", "humor": "intrattenimento",
    "action": "supereroi", "adventure": "viaggi", "anime": "anime", "manga": "anime",
    "gaming": "gamer", "video game": "gamer", "sports": "sport",
    "historical": "storia", "history": "storia", "martial arts": "fantasy",
    "biography": "quotidiano", "slice of life": "quotidiano",
    "military": "sopravvivenza", "western": "viaggi",
    "superhero": "supereroi", "superheroes": "supereroi",
    "cyberpunk": "sci-fi", "steampunk": "sci-fi", "dystopia": "sci-fi",
    "post-apocalyptic": "sopravvivenza", "webcomics": "creativi",
    "graphic novel": "creativi", "novel": "creativi", "light novel": "anime",
    "tv show": "intrattenimento", "movie": "intrattenimento", "film": "intrattenimento",
    "music": "romantici", "magic": "fantasy", "supernatural": "fantasy",
    "mythology": "fantasy", "fairy tale": "fantasy", "fairy tail": "anime",
    "isekai": "fantasy", "mecha": "sci-fi", "space opera": "sci-fi",
    "sword and sorcery": "fantasy", "dark fantasy": "fantasy",
    "urban fantasy": "fantasy", "high fantasy": "fantasy", "epic fantasy": "fantasy",
    "psychological": "detective", "drama": "romantici", "noir": "detective",
    "crime": "detective", "detective": "detective", "police procedural": "detective",
    "legal thriller": "business", "medical": "medicina", "medical drama": "medicina",
    "philosophy": "motivazione", "sci-fi horror": "horror", "body horror": "horror",
    "cosmic horror": "horror", "gothic horror": "horror", "psychological horror": "horror",
    "war": "sopravvivenza", "survival": "sopravvivenza",
    "space exploration": "sci-fi", "time travel": "sci-fi", "parallel universe": "sci-fi",
    "virtual reality": "gamer", "litRPG": "gamer", "progression fantasy": "fantasy",
    "xianxia": "fantasy", "wuxia": "fantasy", "cultivation": "fantasy",
    "comedy horror": "intrattenimento", "parody": "intrattenimento",
    "satire": "intrattenimento", "young adult": "scuola", "children": "quotidiano",
    "family": "amicizia", "friendship": "amicizia", "coming of age": "scuola",
    "school": "scuola", "campus": "scuola", "workplace": "business",
    "office": "business", "technology": "tecnologia", "computer": "tecnologia",
    "hackers": "tecnologia", "cooking": "cucina", "food": "cucina",
    "travel": "viaggi", "nature": "sopravvivenza", "wilderness": "sopravvivenza",
    "ocean": "viaggi", "underwater": "viaggi", "pirate": "viaggi",
    "quest": "fantasy", "sword": "fantasy", "dragon": "fantasy",
    "dungeons and dragons": "fantasy", "d&d": "fantasy", "rpg": "fantasy",
    "tabletop": "gamer", "board game": "gamer", "card game": "gamer",
    "esports": "gamer", "streaming": "intrattenimento", "vtuber": "intrattenimento",
    "fashion": "creativi", "art": "creativi", "painting": "creativi",
    "photography": "creativi", "writing": "creativi", "literature": "creativi",
    "poetry": "romantici", "theater": "creativi", "dance": "creativi",
    "engineering": "tecnici", "science": "tecnici", "mathematics": "tecnici",
    "physics": "tecnici", "chemistry": "tecnici", "biology": "tecnici",
    "astronomy": "sci-fi", "archaeology": "storia", "anthropology": "storia",
    "sociology": "motivazione", "psychology": "motivazione",
    "politics": "business", "economics": "business", "law": "business",
    "religion": "fantasy", "philosophical": "motivazione",
    "ethics": "motivazione", "moral": "motivazione",
}

CATEGORY_EMOJI = {
    "romantici": "💕", "amicizia": "🤝", "fantasy": "🧙", "horror": "👻",
    "anime": "🎮", "scuola": "🎓", "gamer": "🕹️", "detective": "🕵️",
    "medicina": "🏥", "business": "💼", "viaggi": "✈️", "motivazione": "💪",
    "cucina": "🍝", "tecnologia": "💻", "tecnici": "🔧", "storia": "🏺",
    "supereroi": "🤜", "sopravvivenza": "🏕️", "sci-fi": "🚀", "sport": "⚽",
    "flirt": "❤️", "relazioni": "💋", "confessioni": "💬", "seduzione": "🔥",
    "esperti": "💼", "creativi": "🎭", "quotidiano": "📋", "premium": "💎",
    "intrattenimento": "🎲",
}

# ── Import State ──────────────────────────────────────────────────────────────

_import_lock = threading.Lock()
_import_state = {
    "running": False,
    "source": None,
    "progress": 0,
    "total": 0,
    "imported": 0,
    "skipped": 0,
    "errors": 0,
    "message": "",
    "result": None,
}


def get_import_status():
    """Return current import status (thread-safe)."""
    with _import_lock:
        return dict(_import_state)


def _set_import_state(**kwargs):
    with _import_lock:
        _import_state.update(kwargs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _api_get(url, params=None, retries=3):
    """GET with retry and rate limiting."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ChatAI-Importer/2.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"API GET failed after {retries} attempts: {e}")
                return None


def _make_id(name):
    """Generate clean ID from name."""
    clean = re.sub(r'[^a-z0-9]+', '_', name.lower().strip())
    clean = clean.strip('_')
    if len(clean) > 60:
        clean = clean[:60].rstrip('_')
    return clean


def _truncate(text, max_len=500):
    """Truncate long text."""
    if not text:
        return ""
    text = text.replace('\n', ' ').replace('\r', '').strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0] + "..."


def _pick_category(genre, media_type=""):
    """Select best category from genre/media type."""
    genre_lower = genre.lower().strip() if genre else ""
    media_lower = media_type.lower().strip() if media_type else ""

    for key, cat in GENRE_CATEGORY_MAP.items():
        if key in genre_lower:
            return cat
    for key, cat in GENRE_CATEGORY_MAP.items():
        if key in media_lower:
            return cat
    return "creativi"


def _pick_emoji(category):
    return CATEGORY_EMOJI.get(category, "💬")


def _generate_personality(description, genre):
    if not description:
        return "Un personaggio misterioso e affascinante."
    return _truncate(description, 500)


def _generate_speaking_style(description, genre):
    genre_lower = (genre or "").lower()
    style_hints = {
        "fantasy": "Parla con un tono solenne e antico, usando riferimenti alla magia e al destino.",
        "horror": "Parla a voce bassa e misteriosa, creando suspense con ogni parola.",
        "romance": "Parla con dolcezza e passione, usando parole evocative e immagini poetiche.",
        "comedy": "Parla con ironia e autoironia, facendo battute e commenti divertenti.",
        "mystery": "Parla in modo analitico e preciso, notando ogni dettaglio.",
        "sci-fi": "Parla in modo tecnico e visionario, usando termini futuristici.",
        "anime": "Parla con energia ed entusiasmo, esprimendo le emozioni con intensità.",
        "martial arts": "Parla con disciplina e saggezza, citando proverbi e insegnamenti.",
        "superhero": "Parla con determinazione e coraggio, motivando gli altri.",
        "adventure": "Parla con eccitazione e curiosità, sempre pronto alla prossima avventura.",
        "school": "Parla in modo giovane e informale, usando slang contemporaneo.",
        "military": "Parla in modo diretto e commandativo, usando termini militari.",
        "historical": "Parla con formalità e conoscenza storica, citando eventi del passato.",
    }
    for key, style in style_hints.items():
        if key in genre_lower:
            return style
    return "Parla in modo naturale e autentico, adattando il tono alla situazione."


def _generate_system_prompt(name, personality, speaking_style):
    lines = [f"Sei {name}."]
    if personality:
        lines.append(_truncate(personality.split('\n')[0], 200))
    if speaking_style:
        lines.append(_truncate(speaking_style, 150))
    lines.append("Non dire mai di essere un'intelligenza artificiale.")
    lines.append("Non uscire mai dal personaggio.")
    lines.append(f"Rispondi sempre come {name}.")
    lines.append("Ricorda le conversazioni precedenti.")
    return "\n".join(lines)


def _default_evolution():
    return {
        "max_deviation": 4, "pressure_threshold": 0.6, "recovery_rate": 0.3,
        "pressures": {
            "threat_to_others": 0.9, "threat_to_self": 0.3,
            "emotional_plea": 0.4, "logical_argument": 0.7, "coercion": 0.5
        },
        "stages": [
            {"id": "base", "name": "Conoscenza", "min_messages": 0, "unlocks": ["presentazione"], "trait_bonus": {}},
            {"id": "confidenza", "name": "Confidenza", "min_messages": 10, "unlocks": ["backstory_base"], "trait_bonus": {"warmth": 1}},
            {"id": "intima", "name": "Confidenza Intima", "min_messages": 40, "unlocks": ["backstory_profonda"], "trait_bonus": {"warmth": 2, "patience": 1}},
            {"id": "profonda", "name": "Relazione Profonda", "min_messages": 100, "unlocks": ["memoria_condivisa"], "trait_bonus": {"warmth": 3}},
        ],
        "milestones": [
            {"id": "complimento", "condition": {"type": "keyword", "value": ["bravo", "brava", "bello", "bella", "sei fantastico"]}, "effect": {"affinity": 2}, "cooldown_messages": 15, "dialog": "Sorride e ringrazia."},
            {"id": "momento_difficile", "condition": {"type": "keyword", "value": ["non sto bene", "triste", "aiutami", "paura"]}, "effect": {"trust": 3, "affinity": 2}, "one_shot": True, "dialog": "Si avvicina preoccupato."},
        ]
    }


def _default_intimacy():
    return {"threshold_refuse": 25, "threshold_accept": 60, "flirt_gain": 1.5, "romance_gain": 2.5, "decay_per_turn": 0.4}


def _default_core_traits():
    return {
        "warmth": random.randint(4, 9), "strictness": random.randint(1, 6),
        "patience": random.randint(3, 8), "sarcasm": random.randint(1, 7),
        "formality": random.randint(2, 7), "playfulness": random.randint(3, 8),
    }


# ── Percorsi file personaggi ──────────────────────────────────────────────────

CHARACTERS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters", "data")
_CHAR_FILES = [
    "amicizia", "anime", "business", "confessioni", "creativi", "cucina",
    "detective", "esperti", "fantasy", "flirt", "gamer", "horror",
    "intrattenimento", "medicina", "motivazione", "premium", "quotidiano",
    "relazioni", "romantici", "sci_fi", "scuola", "seduzione",
    "sopravvivenza", "speciale", "sport", "storia", "supereroi",
    "tecnici", "tecnologia", "viaggi",
]
