"""Motore di deduplicazione dei personaggi importati."""

import os
import re
import logging

from import_config import _CHAR_FILES
from import_storage import _load_category_json, _save_category_json

logger = logging.getLogger(__name__)


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
