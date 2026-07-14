#!/usr/bin/env python3
"""
Importatore massivo di personaggi da HuggingFace (CharacterCodex) nel database ChatAI.

Fonte: NousResearch/CharacterCodex — 16K personaggi da libri, manga, film, giochi.
Formato output: compatibile con CHARACTERS[] in backend/characters.py

Usage:
    python3 import_characters.py --count 500
    python3 import_characters.py --count 2000
    python3 import_characters.py --all
    python3 import_characters.py --count 1000 --genre fantasy
    python3 import_characters.py --count 500 --output json --output-file chars.json
"""

import json
import time
import random
import re
import sys
import os
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

CHARACTERS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "characters", "data")
CHAR_FILES = [
    "amicizia", "anime", "business", "confessioni", "creativi", "cucina",
    "detective", "esperti", "fantasy", "flirt", "gamer", "horror",
    "intrattenimento", "medicina", "motivazione", "premium", "quotidiano",
    "relazioni", "romantici", "sci_fi", "scuola", "seduzione",
    "sopravvivenza", "speciale", "sport", "storia", "supereroi",
    "tecnici", "tecnologia", "viaggi",
]

HUGGINGFACE_ROWS_API = "https://datasets-server.huggingface.co/rows"
HUGGINGFACE_DATASET = "NousResearch/CharacterCodex"


# ── JSON per-categoria helpers ───────────────────────────────────────────────

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


def get_existing_ids_from_json():
    """Legge tutti gli ID dai file JSON per-categoria."""
    existing = set()
    for cat_name in CHAR_FILES:
        for c in _load_category_json(cat_name):
            cid = c.get("id")
            if cid:
                existing.add(cid)
    return existing

# Mappatura generi → nostre categorie
GENRE_CATEGORY_MAP = {
    "fantasy": "fantasy",
    "sci-fi": "sci-fi",
    "science fiction": "sci-fi",
    "horror": "horror",
    "romance": "romantici",
    "mystery": "detective",
    "thriller": "detective",
    "comedy": "intrattenimento",
    "humor": "intrattenimento",
    "action": "supereroi",
    "adventure": "viaggi",
    "anime": "anime",
    "manga": "anime",
    "gaming": "gamer",
    "video game": "gamer",
    "sports": "sport",
    "historical": "storia",
    "history": "storia",
    "martial arts": "fantasy",
    "biography": "quotidiano",
    "slice of life": "quotidiano",
    "military": "sopravvivenza",
    "western": "viaggi",
    "superhero": "supereroi",
    "superheroes": "supereroi",
    "cyberpunk": "sci-fi",
    "steampunk": "sci-fi",
    "dystopia": "sci-fi",
    "post-apocalyptic": "sopravvivenza",
    "webcomics": "creativi",
    "graphic novel": "creativi",
    "novel": "creativi",
    "light novel": "anime",
    "tv show": "intrattenimento",
    "movie": "intrattenimento",
    "film": "intrattenimento",
    "music": "romantici",
    "magic": "fantasy",
    "supernatural": "fantasy",
    "mythology": "fantasy",
    "fairy tale": "fantasy",
    "fairy tail": "anime",
    "isekai": "fantasy",
    "mecha": "sci-fi",
    "military science fiction": "sci-fi",
    "space opera": "sci-fi",
    "sword and sorcery": "fantasy",
    "dark fantasy": "fantasy",
    "urban fantasy": "fantasy",
    "high fantasy": "fantasy",
    "epic fantasy": "fantasy",
    "psychological": "detective",
    "drama": "romantici",
    "noir": "detective",
    "crime": "detective",
    "detective": "detective",
    "police procedural": "detective",
    "legal thriller": "business",
    "medical": "medicina",
    "medical drama": "medicina",
    "philosophy": "motivazione",
    "sci-fi horror": "horror",
    "body horror": "horror",
    "cosmic horror": "horror",
    "gothic horror": "horror",
    "psychological horror": "horror",
    "war": "sopravvivenza",
    "survival": "sopravvivenza",
    "space exploration": "sci-fi",
    "time travel": "sci-fi",
    "parallel universe": "sci-fi",
    "virtual reality": "gamer",
    "litRPG": "gamer",
    "progression fantasy": "fantasy",
    "xianxia": "fantasy",
    "wuxia": "fantasy",
    "cultivation": "fantasy",
    "comedy horror": "intrattenimento",
    "parody": "intrattenimento",
    "satire": "intrattenimento",
    "young adult": "scuola",
    "children": "quotidiano",
    "children's": "quotidiano",
    "family": "amicizia",
    "friendship": "amicizia",
    "coming of age": "scuola",
    "school": "scuola",
    "campus": "scuola",
    "workplace": "business",
    "office": "business",
    "technology": "tecnologia",
    "computer": "tecnologia",
    "hackers": "tecnologia",
    "cooking": "cucina",
    "food": "cucina",
    "travel": "viaggi",
    "nature": "sopravvivenza",
    "wilderness": "sopravvivenza",
    "ocean": "viaggi",
    "underwater": "viaggi",
    "undersea": "viaggi",
    "pirate": "viaggi",
    "naval": "viaggi",
    "airship": "viaggi",
    "steampunk adventure": "viaggi",
    "quest": "fantasy",
    "sword": "fantasy",
    "dragon": "fantasy",
    "magic system": "fantasy",
    "dungeons and dragons": "fantasy",
    "d&d": "fantasy",
    "rpg": "fantasy",
    "tabletop": "gamer",
    "board game": "gamer",
    "card game": "gamer",
    "esports": "gamer",
    "streaming": "intrattenimento",
    "vtuber": "intrattenimento",
    "idol": "intrattenimento",
    "virtual singer": "intrattenimento",
    "fashion": "creativi",
    "art": "creativi",
    "painting": "creativi",
    "sculpture": "creativi",
    "photography": "creativi",
    "writing": "creativi",
    "literature": "creativi",
    "poetry": "romantici",
    "theater": "creativi",
    "dance": "creativi",
    "ceramics": "creativi",
    "textile": "creativi",
    "interior design": "creativi",
    "architecture": "creativi",
    "engineering": "tecnici",
    "science": "tecnici",
    "mathematics": "tecnici",
    "physics": "tecnici",
    "chemistry": "tecnici",
    "biology": "tecnici",
    "astronomy": "sci-fi",
    "archaeology": "storia",
    "anthropology": "storia",
    "sociology": "motivazione",
    "psychology": "motivazione",
    "politics": "business",
    "economics": "business",
    "law": "business",
    "religion": "fantasy",
    "philosophical": "motivazione",
    "ethics": "motivazione",
    "moral": "motivazione",
}

# Emoji per categoria
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(url, params=None, retries=3):
    """GET con retry e rate limit."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ChatAI-Importer/1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠ Retry {attempt+1}/{retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  ✗ Failed: {e}")
                return None


def make_id(name):
    """Genera ID pulito dal nome."""
    clean = re.sub(r'[^a-z0-9]+', '_', name.lower().strip())
    clean = clean.strip('_')
    if len(clean) > 60:
        clean = clean[:60].rstrip('_')
    return clean


def pick_category(genre, media_type=""):
    """Seleziona la migliore categoria dal genere."""
    genre_lower = genre.lower().strip() if genre else ""
    media_lower = media_type.lower().strip() if media_type else ""

    # Cerca prima nel genere
    for key, cat in GENRE_CATEGORY_MAP.items():
        if key in genre_lower:
            return cat

    # Poi nel media_type
    for key, cat in GENRE_CATEGORY_MAP.items():
        if key in media_lower:
            return cat

    return "creativi"


def pick_emoji(category):
    """Emoji dalla categoria."""
    return CATEGORY_EMOJI.get(category, "💬")


def truncate(text, max_len=500):
    """Tronca testo troppo lungo."""
    if not text:
        return ""
    text = text.replace('\n', ' ').replace('\r', '').strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0] + "..."


def generate_personality(description, genre):
    """Genera personalità dalla descrizione e genere."""
    if not description:
        return "Un personaggio misterioso e affascinante."
    return truncate(description, 500)


def generate_speaking_style(description, genre):
    """Genera stile di conversazione."""
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


def generate_essence(name, description, genre):
    """Genera essence (frase chiave del personaggio)."""
    if description:
        first_sentence = description.split('.')[0]
        if len(first_sentence) < 200:
            return f"Sei {name}. {first_sentence}."
    return f"Sei {name}, un personaggio affascinante e memorabile."


def generate_system_prompt(name, personality, speaking_style):
    """Genera system_prompt compatto."""
    lines = [f"Sei {name}."]
    if personality:
        lines.append(truncate(personality.split('\n')[0], 200))
    if speaking_style:
        lines.append(truncate(speaking_style, 150))
    lines.append("Non dire mai di essere un'intelligenza artificiale.")
    lines.append("Non uscire mai dal personaggio.")
    lines.append(f"Rispondi sempre come {name}.")
    lines.append("Ricorda le conversazioni precedenti.")
    return "\n".join(lines)


def generate_default_evolution():
    """Genera evoluzione di default."""
    return {
        "max_deviation": 4,
        "pressure_threshold": 0.6,
        "recovery_rate": 0.3,
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


def generate_default_intimacy():
    """Config intimità di default."""
    return {"threshold_refuse": 25, "threshold_accept": 60, "flirt_gain": 1.5, "romance_gain": 2.5, "decay_per_turn": 0.4}


def generate_default_core_traits():
    """Tratti di personalità casuali."""
    return {
        "warmth": random.randint(4, 9), "strictness": random.randint(1, 6),
        "patience": random.randint(3, 8), "sarcasm": random.randint(1, 7),
        "formality": random.randint(2, 7), "playfulness": random.randint(3, 8),
    }


# ── HuggingFace Fetcher ──────────────────────────────────────────────────────

def fetch_hf_characters(count=100, genre_filter=None):
    """Scarica personaggi da HuggingFace CharacterCodex."""
    all_chars = []
    offset = 0
    batch_size = 100  # max per request su HF

    while len(all_chars) < count:
        params = {
            "dataset": HUGGINGFACE_DATASET,
            "config": "default",
            "split": "train",
            "offset": offset,
            "length": min(batch_size, count - len(all_chars) + 50),
        }

        print(f"  📡 Fetching offset={offset} (have {len(all_chars)}/{count})...")
        data = api_get(HUGGINGFACE_ROWS_API, params)

        if not data:
            print("  ✗ No data returned, stopping.")
            break

        rows = data.get("rows", [])
        if not rows:
            print("  ✗ No more characters available.")
            break

        for r in rows:
            row = r.get("row", {})
            if not row.get("character_name"):
                continue

            # Filtra per genere se richiesto
            if genre_filter:
                genre = (row.get("genre") or "").lower()
                if genre_filter.lower() not in genre:
                    continue

            all_chars.append(row)

        offset += len(rows)
        time.sleep(0.3)  # Rate limit

    return all_chars[:count]


# ── Converter ────────────────────────────────────────────────────────────────

def convert_hf_character(hf_char, index):
    """Converte un character da HuggingFace nel nostro formato."""
    name = (hf_char.get("character_name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = (hf_char.get("description") or "").strip()
    scenario = (hf_char.get("scenario") or "").strip()
    genre = (hf_char.get("genre") or "").strip()
    media_type = (hf_char.get("media_type") or "").strip()
    media_source = (hf_char.get("media_source") or "").strip()

    category = pick_category(genre, media_type)
    age = random.randint(18, 35)

    # Genera campi mancanti
    personality = generate_personality(description, genre)
    speaking_style = generate_speaking_style(description, genre)
    essence = generate_essence(name, description, genre)
    backstory = truncate(description, 500) if description else truncate(scenario, 500)
    system_prompt = generate_system_prompt(name, personality, speaking_style)

    # Tags
    tags = []
    if genre:
        tags.append(genre.title())
    if media_type:
        tags.append(media_type.title())
    if media_source:
        tags.append(media_source.title())
    tags = tags[:5]
    if not tags:
        tags = [category.capitalize()]

    char_id = make_id(name) + f"_hf{index}"

    return {
        "id": char_id,
        "name": truncate(name, 40),
        "age": age,
        "role": truncate(genre or media_type, 40),
        "category": category,
        "avatar": pick_emoji(category),
        "description": truncate(description, 200),
        "tags": tags,
        "conversations": random.randint(500, 15000),
        "is_adult": False,
        "essence": truncate(essence, 200),
        "personality": truncate(personality, 500),
        "speaking_style": truncate(speaking_style, 300),
        "backstory": truncate(backstory, 500),
        "hobbies": [genre, media_type, "conversare"] if genre else ["conversare"],
        "system_prompt": system_prompt[:600],
        "core_traits": generate_default_core_traits(),
        "evolution": generate_default_evolution(),
        "refusal_style": random.choice(["dolce", "gentile", "diretto"]),
        "intimacy_config": generate_default_intimacy(),
    }


# ── Output Writers ────────────────────────────────────────────────────────────

def get_existing_ids(filepath=None):
    """Legge gli ID esistenti dai file JSON per-categoria.
    Se filepath è specificato (legacy mode), legge dal monolite."""
    if filepath and filepath.endswith(".py"):
        existing = set()
        if not os.path.exists(filepath):
            return existing
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('        "id":'):
                    match = re.search(r'"id"\s*:\s*"([^"]+)"', line)
                    if match:
                        existing.add(match.group(1))
        return existing
    return get_existing_ids_from_json()


def write_to_characters_py(characters, filepath=None):
    """Aggiunge i personaggi ai file JSON per-categoria, saltando i duplicati.
    Se filepath è specificato (legacy mode), scrive nel monolite."""
    if filepath and filepath.endswith(".py"):
        return _write_to_monolith(characters, filepath)
    return _write_to_json_dir(characters)


def _write_to_json_dir(characters):
    """Scrive i personaggi nel file JSON corrispondente alla loro categoria."""
    existing_ids = get_existing_ids_from_json()
    print(f"  📋 Found {len(existing_ids)} existing characters in JSON files")

    new_chars = [c for c in characters if c["id"] not in existing_ids]
    skipped = len(characters) - len(new_chars)
    if skipped > 0:
        print(f"  ⏭ Skipped {skipped} duplicates")
    if not new_chars:
        print(f"  ✓ No new characters to add")
        return True

    # Raggruppa per categoria
    by_cat = {}
    for c in new_chars:
        cat = c.get("category", "creativi")
        by_cat.setdefault(cat, []).append(c)

    total_added = 0
    for cat, chars in by_cat.items():
        if cat not in CHAR_FILES:
            print(f"  ⚠ Unknown category '{cat}', placing in 'creativi'")
            cat = "creativi"
        existing = _load_category_json(cat)
        existing_ids_in_cat = {c["id"] for c in existing}
        to_add = [c for c in chars if c["id"] not in existing_ids_in_cat]
        if to_add:
            existing.extend(to_add)
            _save_category_json(cat, existing)
            print(f"  ✓ {cat}.json: added {len(to_add)} characters")
            total_added += len(to_add)

    print(f"  ✓ Total: {total_added} new characters added to JSON files")
    return True


def _write_to_monolith(characters, filepath="backend/characters.py"):
    """Legacy: aggiunge i personaggi alla lista CHARACTERS nel monolite."""
    existing_ids = get_existing_ids(filepath)
    print(f"  📋 Found {len(existing_ids)} existing characters in {filepath}")

    new_chars = [c for c in characters if c["id"] not in existing_ids]
    skipped = len(characters) - len(new_chars)
    if skipped > 0:
        print(f"  ⏭ Skipped {skipped} duplicates")
    if not new_chars:
        print(f"  ✓ No new characters to add")
        return True

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    marker = "    },\n]"
    marker_alt = "    }\n]"
    insert_pos = content.rfind(marker)
    if insert_pos == -1:
        insert_pos = content.rfind(marker_alt)
    if insert_pos == -1:
        print(f"  ✗ Could not find insertion point in {filepath}")
        return False

    if content[insert_pos:insert_pos+len(marker)] == marker:
        insert_pos += len("    },\n")
    else:
        insert_pos += len("    }\n")

    new_entries = [format_character_as_python(char) for char in new_chars]
    new_code = "\n".join(new_entries) + "\n"

    new_content = content[:insert_pos] + new_code + content[insert_pos:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✓ Added {len(new_chars)} new characters to {filepath}")
    return True


def format_character_as_python(char):
    """Formatta un personaggio come entry Python per characters.py."""
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

    def escape_multiline(s):
        if not s:
            return '""'
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        s = s.replace('\n', '\\n').replace('\r', '')
        return f'"{s}"'

    return f'''    {{
        "id": {py_str(char["id"])},
        "name": {py_str(char["name"])},
        "age": {char.get("age", 22)},
        "role": {py_str(char.get("role", ""))},
        "category": {py_str(char.get("category", "creativi"))},
        "avatar": {py_str(char.get("avatar", "💬"))},
        "description": {py_str(char.get("description", ""))},
        "tags": {py_list(char.get("tags", []))},
        "conversations": {char.get("conversations", random.randint(100, 5000))},
        "is_adult": {str(char.get("is_adult", False))},
        "essence": {escape_multiline(char.get("essence", ""))},
        "personality": {escape_multiline(char.get("personality", ""))},
        "speaking_style": {escape_multiline(char.get("speaking_style", ""))},
        "backstory": {escape_multiline(char.get("backstory", ""))},
        "hobbies": {py_list(char.get("hobbies", []))},
        "system_prompt": {escape_multiline(char.get("system_prompt", ""))},
        "core_traits": {py_dict(char.get("core_traits", {}))},
        "evolution": {py_dict(char.get("evolution", {}))},
        "refusal_style": {py_str(char.get("refusal_style", "dolce"))},
        "intimacy_config": {py_dict(char.get("intimacy_config", {}))},
    }},'''


def write_to_json(characters, filepath):
    """Scrive i personaggi in un file JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(characters, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Written {len(characters)} characters to {filepath}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import characters from HuggingFace into ChatAI")
    parser.add_argument("--count", type=int, default=500, help="Number of characters to import (default: 500)")
    parser.add_argument("--all", action="store_true", help="Import ALL characters (~16K)")
    parser.add_argument("--genre", type=str, help="Filter by genre (e.g., fantasy, anime, romance)")
    parser.add_argument("--output", type=str, default="json_dir", choices=["json_dir", "py", "json"],
                        help="Output: json_dir (JSON per-categoria, default), py (monolite), json (singolo file)")
    parser.add_argument("--output-file", type=str, help="Output file path (solo per --output py/json)")
    args = parser.parse_args()

    count = 16000 if args.all else args.count

    print("=" * 60)
    print("  🎭 ChatAI Character Importer — HuggingFace CharacterCodex")
    print("=" * 60)
    print()

    # Fetch
    print(f"📥 Fetching {count} characters from HuggingFace...")
    raw_chars = fetch_hf_characters(count=count, genre_filter=args.genre)
    print(f"  ✓ Fetched {len(raw_chars)} raw characters")
    print()

    # Convert
    print("🔄 Converting to ChatAI format...")
    converted = []
    seen_ids = set()
    for i, raw in enumerate(raw_chars):
        char = convert_hf_character(raw, i)
        if char and char["id"] not in seen_ids:
            converted.append(char)
            seen_ids.add(char["id"])
    print(f"  ✓ Converted {len(converted)} characters")
    print()

    # Stats
    cats = {}
    for c in converted:
        cat = c["category"]
        cats[cat] = cats.get(cat, 0) + 1

    print("📊 Statistics:")
    print(f"  Total: {len(converted)}")
    print(f"  Categories:")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1])[:15]:
        print(f"    {CATEGORY_EMOJI.get(cat, '?')} {cat}: {cnt}")
    if len(cats) > 15:
        print(f"    ... and {len(cats)-15} more categories")
    print()

    # Output
    if args.output == "json_dir":
        print(f"💾 Writing to JSON per-categoria in {CHARACTERS_DATA_DIR}...")
        write_to_characters_py(converted)  # writes to JSON dir
    elif args.output == "py":
        out_path = args.output_file or "backend/characters.py"
        print(f"💾 Writing to {out_path}...")
        write_to_characters_py(converted, out_path)
    else:
        out_path = args.output_file or "imported_characters.json"
        print(f"💾 Writing to {out_path}...")
        write_to_json(converted, out_path)

    print()
    print("=" * 60)
    print(f"  ✅ Import complete! {len(converted)} characters ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()
