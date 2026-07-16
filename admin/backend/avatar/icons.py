"""Category icon generation."""

import io
import os

from avatar.config import CATEGORY_ICON_PROMPTS, CATEGORY_ICONS_DIR, TOKEN_FILE, MODELS
from avatar.image_gen import generate_image_pollinations


def cmd_generate_category_icons(args):
    """Genera icone PNG per le categorie."""
    import sys
    token = args.token or os.environ.get("HF_TOKEN", "")
    if not token and os.path.isfile(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()

    model_id = MODELS.get(args.model, MODELS["pollinations"])
    is_free_model = model_id == "free" or args.model in ["pollinations", "loremfaces", "testingbot", "avatars-tzador"]

    if not token and not is_free_model:
        print("ERRORE: serve --token o HF_TOKEN o .hf_token per modelli HF")
        sys.exit(1)

    if args.generate_category_icon:
        cat_id = args.generate_category_icon
        if cat_id not in CATEGORY_ICON_PROMPTS:
            print(f"Categoria '{cat_id}' non trovata. Opzioni: {', '.join(CATEGORY_ICON_PROMPTS.keys())}")
            sys.exit(1)
        targets = [cat_id]
    else:
        targets = list(CATEGORY_ICON_PROMPTS.keys())

    os.makedirs(CATEGORY_ICONS_DIR, exist_ok=True)

    print(f"Genero icone per {len(targets)} categorie...")
    for cat_id in targets:
        prompt = CATEGORY_ICON_PROMPTS[cat_id]
        print(f"\n  {cat_id}: {prompt[:60]}...")

        image_data = generate_image_pollinations(prompt, f"cat_{cat_id}")
        if not image_data:
            print(f"  FALLITO: {cat_id}")
            continue

        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            min_dim = min(img.size)
            left = (img.width - min_dim) // 2
            top = (img.height - min_dim) // 2
            square = img.crop((left, top, left + min_dim, top + min_dim))

            square.resize((512, 512), Image.LANCZOS).save(
                os.path.join(CATEGORY_ICONS_DIR, f"{cat_id}.png"), "PNG"
            )
            print(f"  ✅ {cat_id}.png salvato")
        except Exception as e:
            print(f"  ERRORE: {e}")

    print("\nGenerazione icone categorie completata!")
