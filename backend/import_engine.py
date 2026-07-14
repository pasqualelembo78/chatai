"""
Multi-source character import engine with deduplication.

Supports free databases:
  1. HuggingFace CharacterCodex (NousResearch) - 16K chars from books/manga/films
  2. CharacterHub Open Source - character descriptions database
  3. LMSYS Chatbot Conversations - characters from chatbot datasets
  4. OpenDCharacters - open character dataset

Features:
  - Never imports duplicates (ID + name fingerprinting)
  - Maps/converts fields from different schemas
  - Background import with progress tracking
  - Duplicate detection and cleaning
"""

import json
import os
import re
import time
import random
import threading
import urllib.request
import urllib.parse
import logging
from pathlib import Path

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


# ── Existing ID Loader ────────────────────────────────────────────────────────

CHARACTERS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters", "data")
_CHAR_FILES = [
    "amicizia", "anime", "business", "confessioni", "creativi", "cucina",
    "detective", "esperti", "fantasy", "flirt", "gamer", "horror",
    "intrattenimento", "medicina", "motivazione", "premium", "quotidiano",
    "relazioni", "romantici", "sci_fi", "scuola", "seduzione",
    "sopravvivenza", "speciale", "sport", "storia", "supereroi",
    "tecnici", "tecnologia", "viaggi",
]


def _load_category_json(cat_name):
    """Carica un file JSON per-categoria."""
    path = os.path.join(CHARACTERS_DATA_DIR, f"{cat_name}.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_category_json(cat_name, chars):
    """Salva la lista di personaggi nel file JSON per-categoria."""
    path = os.path.join(CHARACTERS_DATA_DIR, f"{cat_name}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chars, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _get_existing_ids(filepath=None):
    """Load all existing character IDs from JSON per-categoria files.
    Se filepath è specificato (legacy mode), legge dal monolite."""
    if filepath and filepath.endswith(".py"):
        existing = set()
        if not os.path.exists(filepath):
            return existing
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '        "id":' in line:
                    match = re.search(r'"id"\s*:\s*"([^"]+)"', line)
                    if match:
                        existing.add(match.group(1))
        return existing
    existing = set()
    for cat_name in _CHAR_FILES:
        for c in _load_category_json(cat_name):
            cid = c.get("id")
            if cid:
                existing.add(cid)
    return existing


def _get_existing_name_fingerprints(filepath=None):
    """Load name fingerprints for additional dedup from JSON files.
    Se filepath è specificato (legacy mode), legge dal monolite."""
    if filepath and filepath.endswith(".py"):
        names = set()
        if not os.path.exists(filepath):
            return names
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '        "name":' in line:
                    match = re.search(r'"name"\s*:\s*"([^"]+)"', line)
                    if match:
                        names.add(match.group(1).lower().strip())
        return names
    names = set()
    for cat_name in _CHAR_FILES:
        for c in _load_category_json(cat_name):
            name = c.get("name", "").lower().strip()
            if name:
                names.add(name)
    return names


# ── Source Fetchers ────────────────────────────────────────────────────────────

def _fetch_huggingface(source_key, count, genre_filter=None):
    """Fetch characters from any HuggingFace dataset."""
    source = SOURCES[source_key]
    dataset = source["dataset"]
    api_url = "https://datasets-server.huggingface.co/rows"
    all_chars = []
    offset = 0
    batch_size = 100

    while len(all_chars) < count:
        params = {
            "dataset": dataset,
            "config": "default",
            "split": "train",
            "offset": offset,
            "length": min(batch_size, count - len(all_chars) + 50),
        }

        _set_import_state(message=f"Fetching offset={offset} (have {len(all_chars)}/{count})...")
        data = _api_get(api_url, params)

        if not data:
            break

        rows = data.get("rows", [])
        if not rows:
            break

        for r in rows:
            row = r.get("row", {})
            if not row.get("character_name") and not row.get("name"):
                continue

            if genre_filter:
                genre = (row.get("genre") or row.get("category") or "").lower()
                if genre_filter.lower() not in genre:
                    continue

            all_chars.append(row)

        offset += len(rows)
        time.sleep(0.3)

    return all_chars[:count]


# ── Source-specific Converters ─────────────────────────────────────────────────

def _convert_charactercodex(hf_char, index):
    """Convert from CharacterCodex schema."""
    name = (hf_char.get("character_name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = (hf_char.get("description") or "").strip()
    scenario = (hf_char.get("scenario") or "").strip()
    genre = (hf_char.get("genre") or "").strip()
    media_type = (hf_char.get("media_type") or "").strip()

    category = _pick_category(genre, media_type)
    personality = _generate_personality(description, genre)
    speaking_style = _generate_speaking_style(description, genre)

    first_sentence = description.split('.')[0] if description else ""
    essence = f"Sei {name}. {first_sentence}." if len(first_sentence) < 200 else f"Sei {name}, un personaggio affascinante e memorabile."
    backstory = _truncate(description, 500) if description else _truncate(scenario, 500)

    tags = []
    if genre:
        tags.append(genre.title())
    if media_type:
        tags.append(media_type.title())
    tags = tags[:5] if tags else [category.capitalize()]

    return {
        "id": _make_id(name) + f"_hf{index}",
        "name": _truncate(name, 40),
        "age": random.randint(18, 35),
        "role": _truncate(genre or media_type, 40),
        "category": category,
        "avatar": _pick_emoji(category),
        "description": _truncate(description, 200),
        "tags": tags,
        "conversations": random.randint(500, 15000),
        "is_adult": False,
        "essence": _truncate(essence, 200),
        "personality": _truncate(personality, 500),
        "speaking_style": _truncate(speaking_style, 300),
        "backstory": _truncate(backstory, 500),
        "hobbies": [genre, media_type, "conversare"] if genre else ["conversare"],
        "system_prompt": _generate_system_prompt(name, personality, speaking_style)[:600],
        "core_traits": _default_core_traits(),
        "evolution": _default_evolution(),
        "refusal_style": random.choice(["dolce", "gentile", "diretto"]),
        "intimacy_config": _default_intimacy(),
        "_source": "charactercodex",
    }


def _convert_characterhub(hf_char, index):
    """Convert from CharacterHub schema."""
    name = (hf_char.get("character_name") or hf_char.get("name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = (hf_char.get("description") or hf_char.get("character_description") or "").strip()
    genre = (hf_char.get("genre") or hf_char.get("category") or "").strip()
    media_type = (hf_char.get("media_type") or hf_char.get("source") or "").strip()

    category = _pick_category(genre, media_type)
    personality = _generate_personality(description, genre)
    speaking_style = _generate_speaking_style(description, genre)

    first_sentence = description.split('.')[0] if description else ""
    essence = f"Sei {name}. {first_sentence}." if len(first_sentence) < 200 else f"Sei {name}, un personaggio unico e memorabile."

    tags = []
    if genre:
        tags.append(genre.title())
    if media_type:
        tags.append(media_type.title())
    tags = tags[:5] if tags else [category.capitalize()]

    return {
        "id": _make_id(name) + f"_ch{index}",
        "name": _truncate(name, 40),
        "age": random.randint(18, 35),
        "role": _truncate(genre or media_type, 40),
        "category": category,
        "avatar": _pick_emoji(category),
        "description": _truncate(description, 200),
        "tags": tags,
        "conversations": random.randint(500, 15000),
        "is_adult": False,
        "essence": _truncate(essence, 200),
        "personality": _truncate(personality, 500),
        "speaking_style": _truncate(speaking_style, 300),
        "backstory": _truncate(description, 500),
        "hobbies": [genre, media_type, "conversare"] if genre else ["conversare"],
        "system_prompt": _generate_system_prompt(name, personality, speaking_style)[:600],
        "core_traits": _default_core_traits(),
        "evolution": _default_evolution(),
        "refusal_style": random.choice(["dolce", "gentile", "diretto"]),
        "intimacy_config": _default_intimacy(),
        "_source": "characterhub",
    }


def _convert_lmsys(hf_char, index):
    """Convert from LMSYS chatbot conversations schema."""
    name = (hf_char.get("character_name") or hf_char.get("model_name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = (hf_char.get("description") or hf_char.get("system_prompt") or "").strip()
    genre = (hf_char.get("genre") or hf_char.get("category") or "conversazione").strip()

    category = _pick_category(genre, "")
    personality = _generate_personality(description, genre)
    speaking_style = _generate_speaking_style(description, genre)

    first_sentence = description.split('.')[0] if description else ""
    essence = f"Sei {name}. {first_sentence}." if len(first_sentence) < 200 else f"Sei {name}, un assistente inteligente e cordiale."

    return {
        "id": _make_id(name) + f"_lm{index}",
        "name": _truncate(name, 40),
        "age": random.randint(18, 35),
        "role": _truncate(genre, 40),
        "category": category,
        "avatar": _pick_emoji(category),
        "description": _truncate(description, 200),
        "tags": [genre.title()] if genre else [category.capitalize()],
        "conversations": random.randint(500, 15000),
        "is_adult": False,
        "essence": _truncate(essence, 200),
        "personality": _truncate(personality, 500),
        "speaking_style": _truncate(speaking_style, 300),
        "backstory": _truncate(description, 500),
        "hobbies": [genre, "conversare"],
        "system_prompt": _generate_system_prompt(name, personality, speaking_style)[:600],
        "core_traits": _default_core_traits(),
        "evolution": _default_evolution(),
        "refusal_style": random.choice(["dolce", "gentile", "diretto"]),
        "intimacy_config": _default_intimacy(),
        "_source": "lmsys",
    }


def _convert_maltezos(hf_char, index):
    """Convert from Maltezos character dataset schema."""
    name = (hf_char.get("character_name") or hf_char.get("name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = (hf_char.get("description") or hf_char.get("personality_description") or "").strip()
    genre = (hf_char.get("genre") or hf_char.get("fandom") or "").strip()
    media_type = (hf_char.get("media_type") or hf_char.get("source_fandom") or "").strip()

    category = _pick_category(genre, media_type)
    personality = _generate_personality(description, genre)
    speaking_style = _generate_speaking_style(description, genre)

    first_sentence = description.split('.')[0] if description else ""
    essence = f"Sei {name}. {first_sentence}." if len(first_sentence) < 200 else f"Sei {name}, un personaggio unico e memorabile."

    tags = []
    if genre:
        tags.append(genre.title())
    if media_type:
        tags.append(media_type.title())
    tags = tags[:5] if tags else [category.capitalize()]

    return {
        "id": _make_id(name) + f"_ml{index}",
        "name": _truncate(name, 40),
        "age": random.randint(18, 35),
        "role": _truncate(genre or media_type, 40),
        "category": category,
        "avatar": _pick_emoji(category),
        "description": _truncate(description, 200),
        "tags": tags,
        "conversations": random.randint(500, 15000),
        "is_adult": False,
        "essence": _truncate(essence, 200),
        "personality": _truncate(personality, 500),
        "speaking_style": _truncate(speaking_style, 300),
        "backstory": _truncate(description, 500),
        "hobbies": [genre, media_type, "conversare"] if genre else ["conversare"],
        "system_prompt": _generate_system_prompt(name, personality, speaking_style)[:600],
        "core_traits": _default_core_traits(),
        "evolution": _default_evolution(),
        "refusal_style": random.choice(["dolce", "gentile", "diretto"]),
        "intimacy_config": _default_intimacy(),
        "_source": "maltezos",
    }


SOURCE_CONVERTERS = {
    "charactercodex": _convert_charactercodex,
    "characterhub": _convert_characterhub,
    "lmsys_conversations": _convert_lmsys,
    "maltezos": _convert_maltezos,
}

SOURCE_FETCHERS = {
    "charactercodex": _fetch_huggingface,
    "characterhub": _fetch_huggingface,
    "lmsys_conversations": _fetch_huggingface,
    "maltezos": _fetch_huggingface,
}


# ── Deduplication Engine ──────────────────────────────────────────────────────

def _fingerprint_name(name):
    """Normalize name for similarity comparison."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def find_duplicates(filepath=None):
    """
    Find all duplicate characters across JSON per-categoria files.
    Se filepath è specificato (legacy mode), cerca nel monolite.
    Returns list of {id, name, count, categories}.
    """
    id_occurrences = {}

    if filepath and filepath.endswith(".py"):
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if '        "id":' in line:
                    match = re.search(r'"id"\s*:\s*"([^"]+)"', line)
                    if match:
                        cid = match.group(1)
                        id_occurrences.setdefault(cid, []).append(line_num)
    else:
        for cat_name in _CHAR_FILES:
            chars = _load_category_json(cat_name)
            for c in chars:
                cid = c.get("id")
                if cid:
                    id_occurrences.setdefault(cid, []).append(cat_name)

    duplicates = []
    for cid, locations in id_occurrences.items():
        if len(locations) > 1:
            duplicates.append({
                "type": "id",
                "id": cid,
                "count": len(locations),
                "locations": locations,
            })

    return duplicates


def clean_duplicates(filepath=None):
    """
    Remove duplicate characters from JSON per-categoria files.
    Se filepath è specificato (legacy mode), pulisce il monolite.
    Keeps the FIRST occurrence of each ID.
    Returns {removed: int, remaining: int}.
    """
    if filepath and filepath.endswith(".py"):
        return _clean_duplicates_monolith(filepath)

    removed = 0
    seen_ids = set()
    total_remaining = 0

    for cat_name in _CHAR_FILES:
        chars = _load_category_json(cat_name)
        original_count = len(chars)
        unique = []
        for c in chars:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                unique.append(c)
            elif not cid:
                unique.append(c)
            else:
                removed += 1
        if len(unique) < original_count:
            _save_category_json(cat_name, unique)
        total_remaining += len(unique)

    return {"removed": removed, "remaining": total_remaining}


def _clean_duplicates_monolith(filepath):
    """Legacy: remove duplicates from monolith characters.py."""
    if not os.path.exists(filepath):
        return {"removed": 0, "remaining": 0, "error": "File not found"}

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    char_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("CHARACTERS = ["):
            char_start = i
            break

    if char_start is None:
        return {"removed": 0, "remaining": 0, "error": "CHARACTERS list not found"}

    char_blocks = []
    i = char_start + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "],":
            break
        if line.strip().startswith("{") or (lines[i-1].strip().endswith(",") and line.strip().startswith('"id"')):
            block_start = i
            if not line.strip().startswith("{"):
                block_start = i - 1
            depth = 0
            block_end = block_start
            for j in range(block_start, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0:
                    block_end = j
                    break
            block_text = "".join(lines[block_start:block_end + 1])
            char_blocks.append((block_start, block_end, block_text))
            i = block_end + 1
        else:
            i += 1

    seen_ids = set()
    keep_blocks = []
    removed = 0

    for block_start, block_end, block_text in char_blocks:
        id_match = re.search(r'"id"\s*:\s*"([^"]+)"', block_text)
        if id_match:
            cid = id_match.group(1)
            if cid not in seen_ids:
                seen_ids.add(cid)
                keep_blocks.append((block_start, block_end, block_text))
            else:
                removed += 1
        else:
            keep_blocks.append((block_start, block_end, block_text))

    if removed == 0:
        return {"removed": 0, "remaining": len(char_blocks), "message": "No duplicates found"}

    new_lines = lines[:char_start + 1]
    for i, (_, _, block_text) in enumerate(keep_blocks):
        new_lines.append(block_text)
        if i < len(keep_blocks) - 1:
            new_lines.append(",\n")
        else:
            new_lines.append("\n")

    end_idx = char_start + 1
    depth = 0
    for i in range(char_start + 1, len(lines)):
        depth += lines[i].count("[") - lines[i].count("]")
        if depth <= 0:
            end_idx = i
            break

    new_lines.extend(lines[end_idx:])

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    return {"removed": removed, "remaining": len(keep_blocks)}


# ── Main Import Function ─────────────────────────────────────────────────────

def start_import(source_key, count=500, genre_filter=None, filepath=None):
    """
    Start a background import job.
    Returns immediately; status available via get_import_status().
    """
    if _import_state["running"]:
        return {"error": "An import is already running"}

    if source_key not in SOURCES:
        return {"error": f"Unknown source: {source_key}. Available: {list(SOURCES.keys())}"}

    def _run_import():
        try:
            _set_import_state(
                running=True, source=source_key, progress=0, total=count,
                imported=0, skipped=0, errors=0,
                message=f"Starting import from {SOURCES[source_key]['name']}...",
                result=None,
            )

            # Load existing IDs for dedup
            existing_ids = _get_existing_ids(filepath)
            existing_names = _get_existing_name_fingerprints(filepath)
            _set_import_state(message=f"Loaded {len(existing_ids)} existing characters, fetching from source...")

            # Fetch raw data
            fetcher = SOURCE_FETCHERS[source_key]
            raw_chars = fetcher(source_key, count, genre_filter)
            _set_import_state(total=len(raw_chars), message=f"Fetched {len(raw_chars)} raw characters, converting...")

            # Convert
            converter = SOURCE_CONVERTERS[source_key]
            converted = []
            for i, raw in enumerate(raw_chars):
                try:
                    char = converter(raw, i)
                    if char:
                        converted.append(char)
                except Exception as e:
                    _set_import_state(errors=_import_state["errors"] + 1)

                if (i + 1) % 100 == 0:
                    _set_import_state(
                        progress=i + 1,
                        message=f"Converted {i + 1}/{len(raw_chars)} characters...",
                    )

            # Dedup against existing
            new_chars = []
            skipped = 0
            for char in converted:
                if char["id"] in existing_ids:
                    skipped += 1
                    continue
                name_fp = _fingerprint_name(char["name"])
                if name_fp in existing_names:
                    skipped += 1
                    continue
                new_chars.append(char)
                existing_ids.add(char["id"])
                existing_names.add(name_fp)

            _set_import_state(
                progress=len(raw_chars),
                message=f"Dedup complete: {len(new_chars)} new, {skipped} skipped. Writing to file...",
            )

            # Write to file
            if new_chars:
                success = _write_characters_to_file(new_chars, filepath)
                if success:
                    _set_import_state(
                        running=False,
                        imported=len(new_chars),
                        skipped=skipped,
                        message=f"Import complete! {len(new_chars)} characters added, {skipped} duplicates skipped.",
                        result={
                            "source": source_key,
                            "imported": len(new_chars),
                            "skipped": skipped,
                            "total_fetched": len(raw_chars),
                            "categories": _count_categories(new_chars),
                        },
                    )
                else:
                    _set_import_state(
                        running=False,
                        imported=0,
                        skipped=skipped,
                        message="Import failed: could not write to file.",
                        result={"error": "Write failed"},
                    )
            else:
                _set_import_state(
                    running=False,
                    imported=0,
                    skipped=skipped,
                    message=f"No new characters to import. {skipped} duplicates found.",
                    result={"imported": 0, "skipped": skipped},
                )

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            _set_import_state(
                running=False,
                message=f"Import failed: {str(e)}",
                result={"error": str(e)},
            )

    thread = threading.Thread(target=_run_import, daemon=True)
    thread.start()
    return {"status": "started", "source": source_key, "count": count}


def _write_characters_to_file(new_chars, filepath=None):
    """Scrive i nuovi personaggi nei file JSON per-categoria.
    Se filepath è specificato (legacy mode), scrive nel monolite."""
    if filepath and filepath.endswith(".py"):
        return _write_to_monolith(new_chars, filepath)
    return _write_to_json_dir(new_chars)


def _write_to_json_dir(new_chars):
    """Scrive i personaggi nel file JSON corrispondente alla loro categoria."""
    existing_ids = _get_existing_ids()
    filtered = [c for c in new_chars if c["id"] not in existing_ids]
    if not filtered:
        logger.info("No new characters to add (all duplicates)")
        return True

    by_cat = {}
    for c in filtered:
        cat = c.get("category", "creativi")
        by_cat.setdefault(cat, []).append(c)

    total_added = 0
    for cat, chars in by_cat.items():
        if cat not in _CHAR_FILES:
            logger.warning(f"Unknown category '{cat}', placing in 'creativi'")
            cat = "creativi"
        existing = _load_category_json(cat)
        existing_ids_in_cat = {c["id"] for c in existing}
        to_add = [c for c in chars if c["id"] not in existing_ids_in_cat]
        if to_add:
            existing.extend(to_add)
            _save_category_json(cat, existing)
            logger.info(f"{cat}.json: added {len(to_add)} characters")
            total_added += len(to_add)

    logger.info(f"Total: {total_added} new characters added to JSON files")
    return True


def _write_to_monolith(new_chars, filepath="backend/characters.py"):
    """Legacy: append new characters to the CHARACTERS list in characters.py."""
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    marker = "    },\n]"
    marker_alt = "    }\n]"
    insert_pos = content.rfind(marker)
    if insert_pos == -1:
        insert_pos = content.rfind(marker_alt)
    if insert_pos == -1:
        logger.error(f"Could not find insertion point in {filepath}")
        return False

    if content[insert_pos:insert_pos+len(marker)] == marker:
        insert_pos += len("    },\n")
    else:
        insert_pos += len("    }\n")

    entries = []
    for char in new_chars:
        entries.append(_format_char_python(char))

    new_code = "\n".join(entries) + "\n"
    new_content = content[:insert_pos] + new_code + content[insert_pos:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def _format_char_python(char):
    """Format a character as Python dict entry."""
    def py_str(s):
        if s is None:
            return '""'
        if not isinstance(s, str):
            s = str(s)
        if not s:
            return '""'
        s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
        return f'"{s}"'

    def py_list(lst):
        if not lst:
            return "[]"
        items = []
        for item in lst:
            if isinstance(item, dict):
                items.append(py_dict(item))
            elif isinstance(item, list):
                items.append(py_list(item))
            else:
                items.append(py_str(str(item)))
        return "[" + ", ".join(items) + "]"

    def py_dict(d):
        if not d:
            return "{}"
        items = []
        for k, v in d.items():
            if isinstance(v, str):
                items.append(f'"{k}": {py_str(v)}')
            elif isinstance(v, bool):
                items.append(f'"{k}": {str(v)}')
            elif isinstance(v, (int, float)):
                items.append(f'"{k}": {v}')
            elif isinstance(v, dict):
                items.append(f'"{k}": {py_dict(v)}')
            elif isinstance(v, list):
                items.append(f'"{k}": {py_list(v)}')
            else:
                items.append(f'"{k}": {py_str(str(v))}')
        return "{" + ", ".join(items) + "}"

    # Skip internal fields
    clean = {k: v for k, v in char.items() if not k.startswith("_")}

    return f'''    {{
        "id": {py_str(clean.get("id", ""))},
        "name": {py_str(clean.get("name", ""))},
        "age": {clean.get("age", 22)},
        "role": {py_str(clean.get("role", ""))},
        "category": {py_str(clean.get("category", "creativi"))},
        "avatar": {py_str(clean.get("avatar", "💬"))},
        "description": {py_str(clean.get("description", ""))},
        "tags": {py_list(clean.get("tags", []))},
        "conversations": {clean.get("conversations", 0)},
        "is_adult": {str(clean.get("is_adult", False))},
        "essence": {py_str(clean.get("essence", ""))},
        "personality": {py_str(clean.get("personality", ""))},
        "speaking_style": {py_str(clean.get("speaking_style", ""))},
        "backstory": {py_str(clean.get("backstory", ""))},
        "hobbies": {py_list(clean.get("hobbies", []))},
        "system_prompt": {py_str(clean.get("system_prompt", ""))},
        "core_traits": {py_dict(clean.get("core_traits", {}))},
        "evolution": {py_dict(clean.get("evolution", {}))},
        "refusal_style": {py_str(clean.get("refusal_style", "dolce"))},
        "intimacy_config": {py_dict(clean.get("intimacy_config", {}))},
    }},'''


def _count_categories(chars):
    cats = {}
    for c in chars:
        cat = c.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    return dict(sorted(cats.items(), key=lambda x: -x[1]))
