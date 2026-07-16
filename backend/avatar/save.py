"""Avatar saving and character JSON updating."""

import io
import os

from avatar.config import STATIC_AVATARS
from avatar.characters import _load_category_json, _save_category_json, _find_char_in_json


def save_avatar(char_id, category, image_data):
    from PIL import Image
    img = Image.open(io.BytesIO(image_data))
    min_dim = min(img.size)
    left = (img.width - min_dim) // 2
    top = (img.height - min_dim) // 2
    square = img.crop((left, top, left + min_dim, top + min_dim))

    category_dir = os.path.join(STATIC_AVATARS, category)
    os.makedirs(category_dir, exist_ok=True)
    square.resize((512, 512), Image.LANCZOS).save(
        os.path.join(category_dir, f"{char_id}.png"), "PNG"
    )
    print(f"  Server: static/avatars/{category}/{char_id}.png")


def update_characters_py(char_id):
    """Aggiunge il campo 'avatar_image' al personaggio nel file JSON per-categoria."""
    cat_name, char_data, idx = _find_char_in_json(char_id)
    if cat_name is None:
        print(f"  WARNING: '{char_id}' non trovato nei file JSON")
        return False
    if char_data.get("avatar_image"):
        print(f"  avatar_image già presente per '{char_id}'")
        return True
    chars = _load_category_json(cat_name)
    for c in chars:
        if c.get("id") == char_id:
            c["avatar_image"] = char_id
            break
    _save_category_json(cat_name, chars)
    print(f"  {cat_name}.json aggiornato per '{char_id}'")
    return True


def update_characters_py_full(char_id, bio_data, force=False):
    """Aggiorna il file JSON per-categoria con biografia completa italiana."""
    cat_name, char_data, idx = _find_char_in_json(char_id)
    if cat_name is None:
        print(f"  WARNING: '{char_id}' non trovato nei file JSON")
        return False

    if char_data.get("backstory") and not force:
        print(f"  Biografia già presente per '{char_id}', salto (usa --force per sovrascrivere)")
        return True

    chars = _load_category_json(cat_name)
    for c in chars:
        if c.get("id") != char_id:
            continue

        if force:
            for key in ["description", "backstory", "personality",
                        "speaking_style", "hobbies", "opening_scenario"]:
                c.pop(key, None)

        if "description" in bio_data:
            c["description"] = bio_data["description"]
        if "backstory" in bio_data:
            c["backstory"] = bio_data["backstory"]
        if "personality" in bio_data:
            c["personality"] = bio_data["personality"]
        if "speaking_style" in bio_data:
            c["speaking_style"] = bio_data["speaking_style"]
        if "hobbies" in bio_data:
            c["hobbies"] = bio_data["hobbies"]
        if "opening_scenario" in bio_data:
            c["opening_scenario"] = bio_data["opening_scenario"]
        break

    _save_category_json(cat_name, chars)
    suffix = " (FORCED)" if force else ""
    print(f"  {cat_name}.json aggiornato con biografia per '{char_id}'{suffix}")
    return True
