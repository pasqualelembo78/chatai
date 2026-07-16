"""Character JSON loading, saving, and searching."""

import json
import os

from avatar.config import CHARACTERS_DATA_DIR, CHAR_FILES


def _load_category_json(cat_name):
    """Carica un file JSON per-categoria e restituisce la lista di personaggi."""
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


def _find_char_in_json(char_id):
    """Trova un personaggio per ID nei file JSON per-categoria.
    Restituisce (cat_name, char_dict, index) o (None, None, -1)."""
    for cat_name in CHAR_FILES:
        chars = _load_category_json(cat_name)
        for i, c in enumerate(chars):
            if c.get("id") == char_id:
                return cat_name, c, i
    return None, None, -1


def parse_characters():
    """Carica tutti i personaggi dai file JSON per-categoria."""
    chars = []
    for cat_name in CHAR_FILES:
        chars.extend(_load_category_json(cat_name))
    return chars
