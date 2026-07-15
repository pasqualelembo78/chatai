#!/usr/bin/env python3
"""Convert character Python data files to JSON format."""
import os
import sys
import json
import importlib.util

CHAR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CHAR_DIR, "data")

# Files to convert (skip functions.py, categorical.py, __init__.py)
CHAR_FILES = {
    "amicizia": "CHARACTERS_AMICIZIA",
    "anime": "CHARACTERS_ANIME",
    "business": "CHARACTERS_BUSINESS",
    "confessioni": "CHARACTERS_CONFESSIONI",
    "creativi": "CHARACTERS_CREATIVI",
    "cucina": "CHARACTERS_CUCINA",
    "detective": "CHARACTERS_DETECTIVE",
    "esperti": "CHARACTERS_ESPERTI",
    "fantasy": "CHARACTERS_FANTASY",
    "flirt": "CHARACTERS_FLIRT",
    "gamer": "CHARACTERS_GAMER",
    "horror": "CHARACTERS_HORROR",
    "intrattenimento": "CHARACTERS_INTRATTENIMENTO",
    "medicina": "CHARACTERS_MEDICINA",
    "motivazione": "CHARACTERS_MOTIVAZIONE",
    "premium": "CHARACTERS_PREMIUM",
    "quotidiano": "CHARACTERS_QUOTIDIANO",
    "relazioni": "CHARACTERS_RELAZIONI",
    "romantici": "CHARACTERS_ROMANTICI",
    "sci_fi": "CHARACTERS_SCI_FI",
    "scuola": "CHARACTERS_SCUOLA",
    "seduzione": "CHARACTERS_SEDUZIONE",
    "sopravvivenza": "CHARACTERS_SOPRAVVIVENZA",
    "speciale": "CHARACTERS_SPECIALE",
    "sport": "CHARACTERS_SPORT",
    "storia": "CHARACTERS_STORIA",
    "supereroi": "CHARACTERS_SUPEREROI",
    "tecnici": "CHARACTERS_TECNICI",
    "tecnologia": "CHARACTERS_TECNOLOGIA",
    "viaggi": "CHARACTERS_VIAGGI",
}


def convert_file(filename, varname):
    """Import a Python module and extract its character list as JSON-serializable data."""
    filepath = os.path.join(CHAR_DIR, f"{filename}.py")
    if not os.path.exists(filepath):
        print(f"  SKIP: {filepath} not found")
        return None

    spec = importlib.util.spec_from_file_location(filename, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    data = getattr(mod, varname, None)
    if data is None:
        print(f"  ERROR: variable {varname} not found in {filename}.py")
        return None

    # Validate it's a list of dicts
    if not isinstance(data, list):
        print(f"  ERROR: {varname} is not a list (type={type(data).__name__})")
        return None

    return data


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    total_chars = 0
    total_files = 0

    for filename, varname in sorted(CHAR_FILES.items()):
        print(f"Converting {filename}.py...")
        data = convert_file(filename, varname)
        if data is None:
            continue

        outpath = os.path.join(DATA_DIR, f"{filename}.json")
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"  -> {len(data)} chars, {size_mb:.1f} MB")
        total_chars += len(data)
        total_files += 1

    # Also convert categories
    print("Converting categorical.py...")
    cat_path = os.path.join(CHAR_DIR, "categorical.py")
    spec = importlib.util.spec_from_file_location("categorical", cat_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cat_data = getattr(mod, "CATEGORIES", [])
    outpath = os.path.join(DATA_DIR, "categories.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(cat_data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  -> {len(cat_data)} categories")
    total_files += 1

    print(f"\nDone: {total_chars} characters in {total_files} JSON files")
    print(f"Output: {DATA_DIR}/")


if __name__ == "__main__":
    main()
