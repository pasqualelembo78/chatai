# Auto-generated - Package characters

import random
import logging

logger = logging.getLogger(__name__)

from .categorical import CATEGORIES

from .amicizia import CHARACTERS_AMICIZIA
from .anime import CHARACTERS_ANIME
from .business import CHARACTERS_BUSINESS
from .confessioni import CHARACTERS_CONFESSIONI
from .creativi import CHARACTERS_CREATIVI
from .cucina import CHARACTERS_CUCINA
from .detective import CHARACTERS_DETECTIVE
from .esperti import CHARACTERS_ESPERTI
from .fantasy import CHARACTERS_FANTASY
from .flirt import CHARACTERS_FLIRT
from .gamer import CHARACTERS_GAMER
from .horror import CHARACTERS_HORROR
from .intrattenimento import CHARACTERS_INTRATTENIMENTO
from .medicina import CHARACTERS_MEDICINA
from .motivazione import CHARACTERS_MOTIVAZIONE
from .premium import CHARACTERS_PREMIUM
from .quotidiano import CHARACTERS_QUOTIDIANO
from .relazioni import CHARACTERS_RELAZIONI
from .romantici import CHARACTERS_ROMANTICI
from .sci_fi import CHARACTERS_SCI_FI
from .scuola import CHARACTERS_SCUOLA
from .seduzione import CHARACTERS_SEDUZIONE
from .sopravvivenza import CHARACTERS_SOPRAVVIVENZA
from .speciale import CHARACTERS_SPECIALE
from .sport import CHARACTERS_SPORT
from .storia import CHARACTERS_STORIA
from .supereroi import CHARACTERS_SUPEREROI
from .tecnici import CHARACTERS_TECNICI
from .tecnologia import CHARACTERS_TECNOLOGIA
from .viaggi import CHARACTERS_VIAGGI

CHARACTERS = []
CHARACTERS.extend(CHARACTERS_AMICIZIA)
CHARACTERS.extend(CHARACTERS_ANIME)
CHARACTERS.extend(CHARACTERS_BUSINESS)
CHARACTERS.extend(CHARACTERS_CONFESSIONI)
CHARACTERS.extend(CHARACTERS_CREATIVI)
CHARACTERS.extend(CHARACTERS_CUCINA)
CHARACTERS.extend(CHARACTERS_DETECTIVE)
CHARACTERS.extend(CHARACTERS_ESPERTI)
CHARACTERS.extend(CHARACTERS_FANTASY)
CHARACTERS.extend(CHARACTERS_FLIRT)
CHARACTERS.extend(CHARACTERS_GAMER)
CHARACTERS.extend(CHARACTERS_HORROR)
CHARACTERS.extend(CHARACTERS_INTRATTENIMENTO)
CHARACTERS.extend(CHARACTERS_MEDICINA)
CHARACTERS.extend(CHARACTERS_MOTIVAZIONE)
CHARACTERS.extend(CHARACTERS_PREMIUM)
CHARACTERS.extend(CHARACTERS_QUOTIDIANO)
CHARACTERS.extend(CHARACTERS_RELAZIONI)
CHARACTERS.extend(CHARACTERS_ROMANTICI)
CHARACTERS.extend(CHARACTERS_SCI_FI)
CHARACTERS.extend(CHARACTERS_SCUOLA)
CHARACTERS.extend(CHARACTERS_SEDUZIONE)
CHARACTERS.extend(CHARACTERS_SOPRAVVIVENZA)
CHARACTERS.extend(CHARACTERS_SPECIALE)
CHARACTERS.extend(CHARACTERS_SPORT)
CHARACTERS.extend(CHARACTERS_STORIA)
CHARACTERS.extend(CHARACTERS_SUPEREROI)
CHARACTERS.extend(CHARACTERS_TECNICI)
CHARACTERS.extend(CHARACTERS_TECNOLOGIA)
CHARACTERS.extend(CHARACTERS_VIAGGI)

CHARACTER_MAP = {c['id']: c for c in CHARACTERS}
CATEGORY_MAP = {c['id']: c['name'] for c in CATEGORIES}

from .functions import (
    _is_english, _quick_translate_desc, _quick_translate_essence,
    _MALE_NAMES, _FEMALE_NAMES, _FEMALE_KEYWORDS, _MALE_KEYWORDS,
    _DEFAULT_EVOLUTION_STAGES, _DEFAULT_EVOLUTION_MILESTONES,
)


# ── Funzioni che dipendono da CHARACTERS/CATEGORIES/CHARACTER_MAP ──────


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

    # Lazy-load ALL demographics in one query (not N+1)
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

    char_id = enriched.get("id", "")
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

    return ensure_evolution_config(enriched)


def get_character(char_id):
    c = CHARACTER_MAP.get(char_id)
    if c:
        return _enrich(c)
    from storage import get_user_character
    uchar = get_user_character(char_id)
    if uchar:
        uchar = ensure_evolution_config(uchar)
    return uchar


def list_characters():
    from storage import get_all_user_characters
    uchars = get_all_user_characters()
    return [_enrich(c) for c in CHARACTERS] + uchars


def get_categories():
    return CATEGORIES


def get_characters_by_category(category_id):
    from storage import get_all_user_characters
    predefined = [_enrich(c) for c in CHARACTERS if c["category"] == category_id]
    user_chars = [c for c in get_all_user_characters() if c.get("category") == category_id]
    return predefined + user_chars


def search_characters(query):
    query = query.lower()
    from storage import get_all_user_characters
    predefined = [_enrich(c) for c in CHARACTERS if query in c["name"].lower() or query in c.get("description", "").lower() or any(query in t.lower() for t in c.get("tags", []))]
    user_chars = [c for c in get_all_user_characters() if query in c["name"].lower() or query in c.get("description", "").lower() or any(query in t.lower() for t in c.get("tags", []))]
    return predefined + user_chars


def get_adult_characters():
    from storage import get_all_user_characters
    predefined = [_enrich(c) for c in CHARACTERS if c.get("is_adult", False)]
    user_chars = [c for c in get_all_user_characters() if c.get("is_adult")]
    return predefined + user_chars


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
