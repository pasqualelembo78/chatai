# Character data loader — loads from JSON files at import time

import os
import json
import random
import logging
import time

logger = logging.getLogger(__name__)

_ENRICH_CACHE = {}
_ENRICH_CACHE_TTL = 300  # 5 minutes

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_CHAR_FILES = [
    "amicizia", "anime", "business", "creativi", "cucina",
    "detective", "esperti", "fantasy", "gamer", "horror",
    "intrattenimento", "medicina", "motivazione", "premium", "quotidiano",
    "romantici", "sci_fi", "scuola",
    "sopravvivenza", "speciale", "sport", "storia", "supereroi",
    "tecnici", "tecnologia", "viaggi",
]


def _load_all():
    """Load categories and all character JSON files."""
    categories = []
    cat_path = os.path.join(_DATA_DIR, "categories.json")
    if os.path.exists(cat_path):
        with open(cat_path, encoding="utf-8") as f:
            categories = json.load(f)

    chars = []
    for name in _CHAR_FILES:
        path = os.path.join(_DATA_DIR, f"{name}.json")
        if not os.path.exists(path):
            logger.warning(f"Character data file not found: {path}")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            chars.extend(data)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")

    return chars, categories


CHARACTERS, CATEGORIES = _load_all()
CHARACTER_MAP = {c["id"]: c for c in CHARACTERS}
CATEGORY_MAP = {c["id"]: c["name"] for c in CATEGORIES}


from .functions import (
    _is_english, _quick_translate_desc, _quick_translate_essence,
    _MALE_NAMES, _FEMALE_NAMES, _FEMALE_KEYWORDS, _MALE_KEYWORDS,
    _DEFAULT_EVOLUTION_STAGES, _DEFAULT_EVOLUTION_MILESTONES,
)


def infer_character_sex(character):
    name = character.get("name", "").lower().strip()
    essence = character.get("essence", "").lower()
    desc = character.get("description", "").lower()
    full_name = character.get("full_name", "").lower()
    first_name = name.split()[0] if name else ""
    if first_name in _MALE_NAMES:
        return "maschile"
    if first_name in _FEMALE_NAMES:
        return "femminile"
    if full_name:
        fn = full_name.split()[0]
        if fn in _MALE_NAMES:
            return "maschile"
        if fn in _FEMALE_NAMES:
            return "femminile"
    combined = essence + " " + desc
    for kw in _FEMALE_KEYWORDS:
        if kw in combined:
            return "femminile"
    for kw in _MALE_KEYWORDS:
        if kw in combined:
            return "maschile"
    if first_name:
        if first_name.endswith("a") and first_name not in ("luca", "nicola", "andrea"):
            return "femminile"
        if first_name.endswith("o") or first_name.endswith("e"):
            return "maschile"
    return ""


def _infer_species_from_age(age):
    if age is None:
        return "umano"
    if age > 5000:
        return "entita"
    if age > 1000:
        return "maga"
    if age > 300:
        return "elfo"
    if age > 100:
        return "elfo"
    return "umano"


def _generate_birth_date_from_age(age, reference_date=None):
    from datetime import date
    if reference_date is None:
        reference_date = date(2025, 1, 1)
    if age is None or age <= 0:
        return None
    try:
        birth_year = reference_date.year - int(age)
        month = (int(age * 7) % 12) + 1
        day = (int(age * 13) % 28) + 1
        if birth_year < 1:
            return "{:05d}-{:02d}-{:02d}".format(birth_year, month, day)
        return "{:04d}-{:02d}-{:02d}".format(birth_year, month, day)
    except:
        return None


def _enrich(c):
    char_id = c.get("id", "")
    now = time.time()
    cached = _ENRICH_CACHE.get(char_id)
    if cached and now - cached["ts"] < _ENRICH_CACHE_TTL:
        return cached["data"]

    enriched = dict(c)
    enriched["category_name"] = CATEGORY_MAP.get(c["category"], c["category"])
    if enriched.get("avatar_url"):
        enriched["avatar_url"] = "/avatars/" + enriched["id"]
    desc = enriched.get("description", "")
    if desc and _is_english(desc):
        enriched["description"] = _quick_translate_desc(desc, enriched.get("name", ""))
    essence = enriched.get("essence", "")
    if essence and _is_english(essence):
        enriched["essence"] = _quick_translate_essence(essence, enriched.get("name", ""))

    _demo_cache = getattr(_enrich, "_demo_cache", None)
    if _demo_cache is None:
        _enrich._demo_cache = {}
        _demo_cache = _enrich._demo_cache
        try:
            from db import get_conn, put_conn
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM character_demographics")
                rows = cur.fetchall()
            finally:
                put_conn(conn)
            for row in rows:
                _demo_cache[row["character_id"]] = dict(row)
        except:
            pass

    db_demo = _demo_cache.get(char_id)

    if db_demo:
        enriched["gender"] = db_demo.get("gender", "")
        enriched["gender_display"] = db_demo.get("gender_display", "")
        enriched["sexual_orientation"] = db_demo.get("sexual_orientation", "etero")
        enriched["sexual_orientation_display"] = db_demo.get("sexual_orientation_display", "eterosessuale")
        enriched["birth_date"] = db_demo.get("birth_date", "")
        enriched["birth_place"] = db_demo.get("birth_place", "")
        enriched["species"] = db_demo.get("species", "umano")
    else:
        if not enriched.get("gender"):
            sex = infer_character_sex(enriched)
            if sex == "maschile":
                enriched["gender"] = "M"
                enriched["gender_display"] = "maschile"
            elif sex == "femminile":
                enriched["gender"] = "F"
                enriched["gender_display"] = "femminile"
            else:
                enriched["gender"] = "NB"
                enriched["gender_display"] = "non binario"
        if not enriched.get("sexual_orientation"):
            enriched["sexual_orientation"] = "etero"
            enriched["sexual_orientation_display"] = "eterosessuale"
        if not enriched.get("species"):
            enriched["species"] = _infer_species_from_age(enriched.get("age", 0))
        if not enriched.get("birth_date"):
            enriched["birth_date"] = _generate_birth_date_from_age(enriched.get("age", 0))

    result = ensure_evolution_config(enriched)
    _ENRICH_CACHE[char_id] = {"data": result, "ts": now}
    return result


def get_character(char_id):
    c = CHARACTER_MAP.get(char_id)
    if c:
        return _enrich(c)
    from storage import get_user_character
    uchar = get_user_character(char_id)
    if uchar:
        uchar = ensure_evolution_config(uchar)
    return uchar


_LIST_CACHE = {"data": None, "ts": 0}
_LIST_CACHE_TTL = 60  # 1 minute


def list_characters(include_adult=False):
    now = time.time()
    if _LIST_CACHE["data"] and now - _LIST_CACHE["ts"] < _LIST_CACHE_TTL:
        cached = _LIST_CACHE["data"]
    else:
        from storage import get_all_user_characters
        uchars = get_all_user_characters()
        cached = [_enrich(c) for c in CHARACTERS] + uchars
        _LIST_CACHE["data"] = cached
        _LIST_CACHE["ts"] = now
    if include_adult:
        return cached
    return [c for c in cached if not c.get("is_adult")]


def get_categories():
    return [c for c in CATEGORIES if not c.get("adult")]


_CAT_CACHE = {}
_CAT_CACHE_TTL = 60


def get_characters_by_category(category_id, include_adult=False):
    now = time.time()
    cached = _CAT_CACHE.get(category_id)
    if cached and now - cached["ts"] < _CAT_CACHE_TTL:
        result = cached["data"]
    else:
        from storage import get_all_user_characters
        predefined = [_enrich(c) for c in CHARACTERS if c["category"] == category_id]
        user_chars = [c for c in get_all_user_characters() if c.get("category") == category_id]
        result = predefined + user_chars
        _CAT_CACHE[category_id] = {"data": result, "ts": now}
    if include_adult:
        return result
    return [c for c in result if not c.get("is_adult")]


def search_characters(query):
    query = query.lower()
    from storage import get_all_user_characters
    predefined = [_enrich(c) for c in CHARACTERS if query in c["name"].lower() or query in c.get("description", "").lower() or any(query in t.lower() for t in c.get("tags", []))]
    user_chars = [c for c in get_all_user_characters() if query in c["name"].lower() or query in c.get("description", "").lower() or any(query in t.lower() for t in c.get("tags", []))]
    return [c for c in (predefined + user_chars) if not c.get("is_adult")]


def get_adult_characters():
    # Contenuti adulti rimossi dall'app: non esposti piu'.
    return []


def filter_characters_by_gender(characters, gender_interest):
    if not gender_interest or gender_interest == "non binario":
        return characters
    return [c for c in characters if infer_character_sex(c) == gender_interest or infer_character_sex(c) == ""]


def ensure_evolution_config(character):
    evo = character.get("evolution", {})
    if not isinstance(evo, dict):
        evo = {}
    changed = False
    if "stages" not in evo:
        evo["stages"] = _DEFAULT_EVOLUTION_STAGES
        changed = True
    if "milestones" not in evo:
        evo["milestones"] = _DEFAULT_EVOLUTION_MILESTONES
        changed = True
    if changed:
        character["evolution"] = evo
    return character
