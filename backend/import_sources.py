"""Fetch e conversione dei personaggi dalle varie sorgenti HuggingFace."""

import time
import random
import logging

from import_config import (
    SOURCES, _set_import_state, _api_get,
    _pick_category, _generate_personality, _generate_speaking_style,
    _generate_system_prompt, _make_id, _truncate, _pick_emoji,
    _default_core_traits, _default_evolution, _default_intimacy,
)

logger = logging.getLogger(__name__)


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
        "age": random.randint(15, 35),
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
        "age": random.randint(15, 35),
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
        "age": random.randint(15, 35),
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
        "age": random.randint(15, 35),
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
