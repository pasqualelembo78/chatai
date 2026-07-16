"""ChatAI Avatar Tool — backward-compatible re-exports.

This package replaces the monolithic avatar_tool.py with well-organized modules.
All public symbols are re-exported here for backward compatibility.
"""

from avatar.config import (
    ROOT, CHARACTERS_DATA_DIR, CHAR_FILES, DRAWABLE_DIR, STATIC_AVATARS,
    TOKEN_FILE, STATUS_FILE, GEN_TASKS, MODELS, API_URL,
    CATEGORY_ICONS_DIR, CATEGORY_ICON_PROMPTS, ENV_FILE,
)
from avatar.keys import KeyRotator, ProviderRotator
from avatar.env import (
    get_api_keys, groq_rotator, pexels_rotator, llm_provider_rotator,
    groq_keys, pexels_keys,
)
from avatar.status import (
    load_gen_status, save_gen_status, is_char_done,
    mark_char_done, mark_char_done_all, reset_char_status,
)
from avatar.characters import (
    _load_category_json, _save_category_json, _find_char_in_json,
    parse_characters,
)
from avatar.gender import (
    detect_gender_from_char, detect_gender,
    role_to_pexels_keyword, build_pexels_keyword,
)
from avatar.prompts import get_prompt, get_negative_prompt, translate_description
from avatar.image_gen import (
    generate_image_pollinations, generate_image_pexels,
    generate_image_free, generate_image,
)
from avatar.biography import (
    generate_italian_biography, parse_biography_response,
    generate_italian_description_only,
)
from avatar.save import save_avatar, update_characters_py, update_characters_py_full
from avatar.animation import find_avatars, animate_avatar
from avatar.cli import cmd_generate, cmd_animate, main
from avatar.icons import cmd_generate_category_icons
