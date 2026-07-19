"""Caricamento e scrittura dei personaggi nei file JSON per-categoria."""

import os
import re
import json
import logging

from import_config import CHARACTERS_DATA_DIR, _CHAR_FILES

logger = logging.getLogger(__name__)


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
