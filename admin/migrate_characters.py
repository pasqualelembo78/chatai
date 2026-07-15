#!/usr/bin/env python3
"""
Migration script: Add biographical depth to existing characters.

Adds to each character:
- full_name (nome + cognome)
- knowledge_domains (expertise, familiarity, ignorance)
- personality_depth (profile, traits, speech patterns)
- family (parents, siblings)
- education (high school, university)
- occupation (job, workplace)
- childhood (birthplace, memories)
- hobbies (with skill levels)
- possessions (owned items)
- Enhanced system_prompt with self-awareness

Usage:
    python3 migrate_characters.py              # Dry run (shows stats)
    python3 migrate_characters.py --apply      # Apply migration
    python3 migrate_characters.py --batch 100  # Process 100 at a time
"""

import sys
import os
import re
import json
import argparse
import random

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

from character_builder import (
    build_full_character, enhance_system_prompt,
    generate_surname, generate_birthplace, generate_education,
    generate_occupation, generate_hobbies, generate_possessions,
    generate_family, generate_childhood, build_knowledge_domains,
    generate_personality_depth, PERSONALITY_PROFILES,
)

# ── Fields to add ─────────────────────────────────────────────────────────────

NEW_FIELDS = [
    "full_name", "surname", "personality_profile",
    "education", "occupation", "hobbies", "possessions",
    "family", "childhood", "knowledge_domains", "personality_depth",
]


def parse_existing_characters(filepath):
    """Parse characters.py and return list of character dicts."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find CHARACTERS list boundaries
    start_marker = "CHARACTERS = ["
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print("Could not find CHARACTERS list")
        return []

    # Find the actual list content (after the opening bracket)
    list_start = content.find('[', start_idx)

    # Find matching closing bracket at top level
    depth = 0
    list_end = list_start
    for i in range(list_start, len(content)):
        if content[i] == '[':
            depth += 1
        elif content[i] == ']':
            depth -= 1
            if depth == 0:
                list_end = i
                break

    list_content = content[list_start:list_end+1]

    # Parse character blocks by tracking brace depth
    # Each top-level character block starts with "    {" and ends with "    },"
    chars = []
    lines = list_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for top-level character block start: "    {"
        # Must be at exactly 4 spaces indentation
        if line == '    {' :
            # Found start of a character block
            block_lines = [line]
            brace_depth = line.count('{') - line.count('}')
            i += 1
            
            # Collect lines until we find the matching closing brace
            while i < len(lines) and brace_depth > 0:
                block_lines.append(lines[i])
                brace_depth += lines[i].count('{') - lines[i].count('}')
                i += 1
            
            # Parse the block
            block_str = '\n'.join(block_lines)
            char_dict = _parse_char_block(block_str)
            if char_dict and char_dict.get("id"):
                chars.append(char_dict)
        else:
            i += 1

    return chars


def _parse_char_block(block_str):
    """Parse a single character block string into a dict using ast.literal_eval."""
    import ast
    block_str = block_str.strip()
    if block_str.endswith(','):
        block_str = block_str[:-1]
    try:
        return ast.literal_eval(block_str)
    except (ValueError, SyntaxError) as e:
        print(f"Warning: Could not parse character block: {e}")
        return {}


def format_char_python(char):
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
        if isinstance(d, str):
            return d
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

    return f'''    {{
        "id": {py_str(char.get("id", ""))},
        "name": {py_str(char.get("name", ""))},
        "full_name": {py_str(char.get("full_name", ""))},
        "surname": {py_str(char.get("surname", ""))},
        "age": {char.get("age", 22)},
        "role": {py_str(char.get("role", ""))},
        "category": {py_str(char.get("category", "creativi"))},
        "avatar": {py_str(char.get("avatar", "💬"))},
        "description": {py_str(char.get("description", ""))},
        "tags": {py_list(char.get("tags", []))},
        "conversations": {char.get("conversations", 0)},
        "is_adult": {str(char.get("is_adult", False))},
        "essence": {py_str(char.get("essence", ""))},
        "personality": {py_str(char.get("personality", ""))},
        "personality_profile": {py_str(char.get("personality_profile", ""))},
        "speaking_style": {py_str(char.get("speaking_style", ""))},
        "backstory": {py_str(char.get("backstory", ""))},
        "hobbies": {py_list(char.get("hobbies", []))},
        "possessions": {py_list(char.get("possessions", []))},
        "system_prompt": {py_str(char.get("system_prompt", ""))},
        "core_traits": {py_dict(char.get("core_traits", {}))},
        "evolution": {py_dict(char.get("evolution", {}))},
        "refusal_style": {py_str(char.get("refusal_style", "dolce"))},
        "intimacy_config": {py_dict(char.get("intimacy_config", {}))},
        "knowledge_domains": {py_dict(char.get("knowledge_domains", {}))},
        "personality_depth": {py_dict(char.get("personality_depth", {}))},
        "family": {py_dict(char.get("family", {}))},
        "education": {py_dict(char.get("education", {}))},
        "occupation": {py_dict(char.get("occupation", {}))},
        "childhood": {py_dict(char.get("childhood", {}))},
    }},'''


def migrate_character(char):
    """Add biographical fields to a character that doesn't have them."""
    # Skip if already migrated
    if char.get("full_name") and char.get("knowledge_domains"):
        return char, False

    category = char.get("category", "creativi")
    name = char.get("name", "")
    description = char.get("description", "")
    genre = char.get("role", "")

    # Build full biographical data
    bio = build_full_character(name, category, description, genre)

    # Apply to character
    char["full_name"] = bio["full_name"]
    char["surname"] = bio["surname"]
    char["personality_profile"] = bio["personality_profile"]
    char["education"] = bio["education"]
    char["occupation"] = bio["occupation"]
    char["hobbies"] = bio["hobbies"]
    char["possessions"] = bio["possessions"]
    char["family"] = bio["family"]
    char["childhood"] = bio["childhood"]
    char["knowledge_domains"] = bio["knowledge_domains"]
    char["personality_depth"] = bio["personality_depth"]

    # Regenerate system_prompt with biographical data
    char["system_prompt"] = enhance_system_prompt(char)

    return char, True


def write_characters(filepath, characters):
    """Write characters list back to characters.py."""
    # Read original file to preserve CATEGORIES and footer
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find CATEGORIES block
    cat_match = re.search(r'(CATEGORIES\s*=\s*\[.*?\])', content, re.DOTALL)
    cat_block = cat_match.group(1) if cat_match else "CATEGORIES = []"

    # Find footer (after CHARACTERS list)
    footer_match = re.search(r'\]\s*\n(CHARACTER_MAP\s*=.*)', content, re.DOTALL)
    footer = footer_match.group(1) if footer_match else ""

    # Build new file
    char_entries = []
    for char in characters:
        char_entries.append(format_char_python(char))

    new_content = f"""{cat_block}

CHARACTERS = [
{"".join(char_entries)}
]

{footer}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)


def main():
    parser = argparse.ArgumentParser(description="Migrate characters with biographical depth")
    parser.add_argument("--apply", action="store_true", help="Apply migration (default is dry run)")
    parser.add_argument("--filepath", default="backend/characters.py", help="Path to characters.py (relative to project root)")
    parser.add_argument("--batch", type=int, default=0, help="Process N characters at a time (0=all)")
    parser.add_argument("--force", action="store_true", help="Re-migrate all characters")
    args = parser.parse_args()

    print("=" * 60)
    print("  🧬 Character Biography Migration")
    print("=" * 60)
    print()

    # Parse existing characters
    print(f"📖 Parsing {args.filepath}...")
    characters = parse_existing_characters(args.filepath)
    print(f"  Found {len(characters)} characters")

    if not characters:
        print("  No characters to migrate!")
        return

    # Apply migration
    migrated = 0
    skipped = 0
    to_process = characters[:args.batch] if args.batch > 0 else characters

    print(f"\n🔄 Processing {len(to_process)} characters...")
    for i, char in enumerate(to_process):
        char, was_migrated = migrate_character(char)
        if was_migrated:
            migrated += 1
        else:
            skipped += 1

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(to_process)}...")

    print(f"\n📊 Results:")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped (already migrated): {skipped}")
    print(f"  Total characters: {len(characters)}")

    # Show sample
    if migrated > 0:
        sample = to_process[0]
        print(f"\n📝 Sample migrated character: {sample.get('name', '?')}")
        print(f"  Full name: {sample.get('full_name', '?')}")
        print(f"  Personality: {sample.get('personality_profile', '?')}")
        print(f"  Knowledge: {sample.get('knowledge_domains', {}).get('expertise', [])[:3]}")
        print(f"  Ignorance: {sample.get('knowledge_domains', {}).get('ignorance', [])[:3]}")
        print(f"  Family: father={sample.get('family', {}).get('father', {}).get('name', '?')}")
        print(f"  Occupation: {sample.get('occupation', {}).get('title', '?')}")

    if args.apply:
        print(f"\n💾 Writing to {args.filepath}...")
        write_characters(args.filepath, characters)
        print(f"  ✅ Migration complete!")
    else:
        print(f"\n⚠️  DRY RUN - no changes made. Use --apply to apply migration.")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
