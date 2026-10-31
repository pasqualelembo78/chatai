"""Configuration constants, paths, and model definitions."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHARACTERS_DATA_DIR = os.path.join(ROOT, "backend", "characters", "data")
CHAR_FILES = [
    "amicizia", "anime", "business", "confessioni", "creativi", "cucina",
    "detective", "esperti", "fantasy", "flirt", "gamer", "horror",
    "intrattenimento", "medicina", "motivazione", "premium", "quotidiano",
    "relazioni", "romantici", "sci_fi", "scuola", "seduzione",
    "sopravvivenza", "speciale", "sport", "storia", "supereroi",
    "tecnici", "tecnologia", "viaggi",
]
DRAWABLE_DIR = os.path.join(ROOT, "app", "src", "main", "res")
STATIC_AVATARS = os.path.join(ROOT, "backend", "static", "avatars")
TOKEN_FILE = os.path.join(ROOT, "backend", ".hf_token")
STATUS_FILE = os.path.join(ROOT, "backend", ".gen_status.json")
GEN_TASKS = ("avatar", "bio", "scenario")

ENV_FILE = os.path.join(ROOT, "backend", ".env")

MODELS = {
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",
    "sd3-medium": "stabilityai/stable-diffusion-3-medium-diffusers",
    "pexels": "free",
    "pollinations": "free",
    "tpde": "free",
    "pravatar": "free",
    "dicebear": "free",
}

API_URL = "https://router.huggingface.co/hf-inference/models/"

CATEGORY_ICONS_DIR = os.path.join(ROOT, "backend", "static", "category_icons")

CATEGORY_ICON_PROMPTS = {
    "romantici": "Minimalist flat icon of two hearts intertwined, romantic style, soft pink and red colors, clean design, white background, vector art style",
    "amicizia": "Minimalist flat icon of two hands shaking, friendship symbol, warm orange and yellow colors, clean design, white background, vector art style",
    "fantasy": "Minimalist flat icon of a magic wand with stars, fantasy theme, purple and gold colors, clean design, white background, vector art style",
    "horror": "Minimalist flat icon of a haunted house silhouette, horror theme, dark purple and black colors, clean design, white background, vector art style",
    "anime": "Minimalist flat icon of a game controller, anime gaming theme, bright colors, clean design, white background, vector art style",
    "scuola": "Minimalist flat icon of a graduation cap, education theme, blue and gold colors, clean design, white background, vector art style",
    "gamer": "Minimalist flat icon of a joystick, gaming theme, neon green and black colors, clean design, white background, vector art style",
    "detective": "Minimalist flat icon of a magnifying glass, detective mystery theme, brown and gold colors, clean design, white background, vector art style",
    "medicina": "Minimalist flat icon of a medical cross, healthcare theme, green and white colors, clean design, white background, vector art style",
    "business": "Minimalist flat icon of a briefcase, business professional theme, dark blue and silver colors, clean design, white background, vector art style",
    "viaggi": "Minimalist flat icon of an airplane, travel theme, sky blue and white colors, clean design, white background, vector art style",
    "motivazione": "Minimalist flat icon of a rising sun with arrow, motivation theme, orange and yellow colors, clean design, white background, vector art style",
    "cucina": "Minimalist flat icon of a chef hat and fork, cooking theme, red and white colors, clean design, white background, vector art style",
    "tecnologia": "Minimalist flat icon of a circuit board chip, technology theme, blue and green colors, clean design, white background, vector art style",
    "tecnici": "Minimalist flat icon of a wrench and screwdriver, technical theme, grey and orange colors, clean design, white background, vector art style",
    "storia": "Minimalist flat icon of an ancient column, history theme, brown and gold colors, clean design, white background, vector art style",
    "supereroi": "Minimalist flat icon of a shield with lightning bolt, superhero theme, red and gold colors, clean design, white background, vector art style",
    "sopravvivenza": "Minimalist flat icon of a tent and campfire, survival outdoor theme, green and orange colors, clean design, white background, vector art style",
    "sci-fi": "Minimalist flat icon of a rocket ship, science fiction theme, metallic silver and blue colors, clean design, white background, vector art style",
    "sport": "Minimalist flat icon of a soccer ball, sports theme, green and white colors, clean design, white background, vector art style",
    "flirt": "Minimalist flat icon of lips with a kiss mark, flirt theme, red and pink colors, clean design, white background, vector art style",
    "relazioni": "Minimalist flat icon of two interlocked rings, relationships theme, pink and gold colors, clean design, white background, vector art style",
    "confessioni": "Minimalist flat icon of a speech bubble with heart, confession theme, soft purple and pink colors, clean design, white background, vector art style",
    "seduzione": "Minimalist flat icon of a rose with thorns, seduction theme, deep red and black colors, clean design, white background, vector art style",
    "esperti": "Minimalist flat icon of a professional badge, experts theme, navy blue and gold colors, clean design, white background, vector art style",
    "creativi": "Minimalist flat icon of a paint palette and brush, creative arts theme, rainbow colors, clean design, white background, vector art style",
    "quotidiano": "Minimalist flat icon of a coffee cup, daily life theme, warm brown and white colors, clean design, white background, vector art style",
    "premium": "Minimalist flat icon of a diamond gem, premium luxury theme, gold and crystal colors, clean design, white background, vector art style",
    "intrattenimento": "Minimalist flat icon of a dice and cards, entertainment theme, bright colors, clean design, white background, vector art style",
    "speciale": "Minimalist flat icon of a star with sparkles, special theme, golden and silver colors, clean design, white background, vector art style",
    "per_te": "Minimalist flat icon of a person with a heart, for you personal theme, warm colors, clean design, white background, vector art style",
}
