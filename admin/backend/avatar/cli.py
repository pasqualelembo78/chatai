"""CLI entry points for avatar generation, animation, and status management."""

import argparse
import os
import sys
import time

from avatar.config import STATIC_AVATARS, TOKEN_FILE, MODELS, GEN_TASKS
from avatar.env import groq_rotator, pexels_rotator, llm_provider_rotator
from avatar.status import (
    load_gen_status, is_char_done, mark_char_done, mark_char_done_all, reset_char_status
)
from avatar.characters import parse_characters
from avatar.prompts import get_prompt
from avatar.image_gen import generate_image_free, generate_image
from avatar.biography import generate_italian_biography
from avatar.save import save_avatar, update_characters_py, update_characters_py_full
from avatar.animation import find_avatars, animate_avatar
from avatar.icons import cmd_generate_category_icons


def cmd_generate(args):
    token = args.token or os.environ.get("HF_TOKEN", "")
    if not token and os.path.isfile(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()

    model_id = MODELS.get(args.model, MODELS["pollinations"])
    is_free_model = model_id == "free" or args.model in ["pollinations", "tpde", "pravatar", "dicebear"]

    if not token and not is_free_model:
        print("ERRORE: serve --token o HF_TOKEN o .hf_token per modelli HF")
        sys.exit(1)

    pollinations_key = os.environ.get("POLLINATIONS_API_KEY", "")

    if groq_rotator:
        print(f"  📊 Groq keys: {len(groq_rotator.keys)} caricate, {groq_rotator.available_keys()} disponibili")
    if pexels_rotator:
        print(f"  📊 Pexels keys: {len(pexels_rotator.keys)} caricate, {pexels_rotator.available_keys()} disponibili")
    if llm_provider_rotator.providers:
        provider_names = list(set([p["name"] for p in llm_provider_rotator.providers]))
        print(f"  📊 Provider LLM: {', '.join(provider_names)} ({len(llm_provider_rotator.providers)} totali)")

    chars = parse_characters()

    def avatar_path(char):
        return os.path.join(STATIC_AVATARS, char.get("category", ""), f"{char['id']}.png")

    if args.list_missing:
        missing = [c for c in chars if not c.get("avatar_image") or not os.path.isfile(avatar_path(c))]
        print(f"\nPersonaggi SENZA immagine ({len(missing)}):")
        for c in missing:
            flag = " (no field)" if not c.get("avatar_image") else " (no file)"
            print(f"  {c['id']:25s} {c['name']:20s} [{c.get('category','')}]{flag}")
        return

    force = getattr(args, "force", False)

    if args.generate_all:
        if force:
            targets = list(chars)
            print(f"Modalita FORZATA: rigenero avatar per TUTTI i {len(targets)} personaggi")
        else:
            targets = [c for c in chars
                        if (not c.get("avatar_image") or not os.path.isfile(avatar_path(c)))
                        and not is_char_done(c["id"], tasks=("avatar",))]
            skipped_done = [c for c in chars
                            if is_char_done(c["id"], tasks=("avatar",))
                            and (not c.get("avatar_image") or not os.path.isfile(avatar_path(c)))]
            if skipped_done:
                print(f"⚠️  {len(skipped_done)} personaggi flaggati 'fatto' ma senza file avatar:")
                for c in skipped_done:
                    print(f"    {c['id']} — resetto lo stato per rigenerarli")
                    reset_char_status(c["id"])
                    if c not in targets:
                        targets.append(c)
            if not targets:
                print("Tutti i personaggi hanno già immagine (flag 'fatto' presente).")
                print("  Usa --force per rigenerare tutto.")
                return
        limit = args.avatar_limit if hasattr(args, 'avatar_limit') and args.avatar_limit > 0 else args.limit
        if limit > 0 and len(targets) > limit:
            targets = targets[:limit]
            print(f"Genero avatar per {len(targets)} personaggi (limite: {limit})...")
        else:
            print(f"Genero avatar per {len(targets)} personaggi...")
    elif args.generate:
        matched = [c for c in chars if c["id"] == args.generate]
        if not matched:
            print(f"Personaggio '{args.generate}' non trovato.")
            sys.exit(1)
        targets = matched
        if not force and is_char_done(matched[0]["id"], tasks=("avatar",)):
            print(f"  Personaggio '{args.generate}' già flaggato 'fatto'. Salto.")
            print(f"  Usa --force per rigenerare.")
            return
    else:
        return

    bio_count = 0
    for char in targets:
        print(f"\n{'='*60}")
        print(f"Generazione: {char['name']} ({char['id']})")
        print(f"{'='*60}")

        if model_id in ["free", "pexels", "pollinations", "tpde", "pravatar", "dicebear"]:
            prompt = get_prompt(char, args.prompt)
            print(f"  Uso API gratuita: {model_id}")
            print(f"  Prompt: {prompt[:120]}...")
            image_data = generate_image_free(model_id, char['id'], char['name'], prompt, pollinations_key, char=char, original_model=args.model)
        else:
            prompt = get_prompt(char, args.prompt)
            print(f"  Prompt: {prompt[:120]}...")
            image_data = generate_image(token, model_id, prompt)

        if not image_data:
            print(f"  FALLITO: {char['id']}")
            if model_id in ["pollinations"]:
                time.sleep(5)
            continue
        print(f"  Immagine: {len(image_data)} bytes")
        try:
            save_avatar(char["id"], char.get("category", ""), image_data)
            update_characters_py(char["id"])
            print(f"  ✅ Avatar salvato!")
            mark_char_done(char["id"], "avatar")
        except Exception as e:
            print(f"  ERRORE salvataggio avatar: {e}")

        if model_id in ["pollinations"]:
            print(f"  ⏳ Attesa 5 sec (rate limit Pollinations)...")
            time.sleep(5)
        elif model_id in ["pexels"]:
            print(f"  ⏳ Attesa 3 sec (rate limit Pexels)...")
            time.sleep(3)

        if args.bio and (groq_rotator or args.groq_token):
            bio_limit = args.bio_limit if hasattr(args, 'bio_limit') and args.bio_limit > 0 else 0
            if bio_limit > 0 and bio_count >= bio_limit:
                print(f"  Limite biografie raggiunto ({bio_limit})")
                break
            if not force and is_char_done(char["id"], tasks=("bio", "scenario")):
                print(f"  Biografia già flaggata 'fatto'. Salto (usa --force per rigenerare).")
                continue
            print(f"  Genero biografia italiana...")
            bio = generate_italian_biography(char)
            if bio:
                try:
                    update_characters_py_full(char["id"], bio, force=force)
                    bio_count += 1
                    print(f"  ✅ Biografia salvata! ({bio_count}/{bio_limit if bio_limit > 0 else 'infinito'})")
                    mark_char_done(char["id"], "bio")
                    if bio.get("opening_scenario"):
                        mark_char_done(char["id"], "scenario")
                except Exception as e:
                    print(f"  ERRORE salvataggio biografia: {e}")
            else:
                print(f"  ⚠️  Biografia non generata")
            time.sleep(2)

    print("\nGenerazione completata!")
    if args.generate_all or args.generate:
        status = load_gen_status()
        done_count = sum(1 for c in chars if is_char_done(c["id"]))
        print(f"Personaggi completati (tutti i task flag 'fatto'): {done_count}/{len(chars)}")


def cmd_animate(args):
    avatars = find_avatars()
    if not avatars:
        print("Nessun avatar trovato in", STATIC_AVATARS)
        sys.exit(1)

    if args.list_avatars:
        print(f"\nAvatar trovati ({len(avatars)}):")
        for a in avatars:
            anim_path = os.path.join(STATIC_AVATARS, a["category"], f"{a['id']}_anim.mp4")
            status = "✅" if os.path.isfile(anim_path) else "  "
            print(f"  {status} {a['id']:25s} [{a['category']}]")
        return

    if args.animate_all:
        targets = avatars
    elif args.animate:
        matched = [a for a in avatars if a["id"] == args.animate]
        if not matched:
            print(f"Avatar '{args.animate}' non trovato.")
            sys.exit(1)
        targets = matched
    else:
        return

    ok = 0
    failed = 0
    skipped = 0
    for a in targets:
        result = animate_avatar(a["path"], a["category"], a["id"])
        if result == "ok":
            ok += 1
        elif result == "already_exists":
            skipped += 1
        else:
            failed += 1

    print(f"\nRiepilogo: {ok} animati, {skipped} già presenti, {failed} falliti")


def main():
    parser = argparse.ArgumentParser(description="ChatAI Avatar Tool — genera e anima avatar")
    parser.add_argument("--token", help="Hugging Face token (default: env HF_TOKEN o .hf_token)")
    parser.add_argument("--groq-token", help="Groq API token per biografie (default: env GROQ_API_KEY o .env)")
    parser.add_argument("--model", default="pollinations", choices=list(MODELS.keys()),
                        help="Modello generazione (default: pollinations - full-body, gratis)")
    parser.add_argument("--prompt", help="Prompt personalizzato (solo con --generate)")
    parser.add_argument("--bio", action="store_true",
                        help="Genera biografia italiana automatica con Groq (backstory, personality, opening_scenario)")
    parser.add_argument("--force", action="store_true",
                        help="Forza rigenerazione anche se flag 'fatto' presente o campi esistenti. "
                             "Di default salta i personaggi gia completati.")
    parser.add_argument("--reset-status", metavar="ID", help="Resetta il flag 'fatto' per un personaggio")

    gen = parser.add_argument_group("Generazione immagini")
    gen.add_argument("--generate", metavar="ID", help="Genera avatar per un personaggio")
    gen.add_argument("--generate-all", action="store_true",
                     help="Genera avatar per tutti i personaggi mancanti (o TUTTI con --force)")
    gen.add_argument("--list-missing", action="store_true", help="Elenca personaggi senza avatar")
    gen.add_argument("--limit", type=int, default=0, help="Numero massimo di avatar da generare (0=tutti)")
    gen.add_argument("--avatar-limit", type=int, default=0, help="Limite avatar per modalita both")
    gen.add_argument("--bio-limit", type=int, default=0, help="Limite biografie per modalita both")
    gen.add_argument("--status", action="store_true", help="Mostra statistiche stato generazioni")

    anim = parser.add_argument_group("Animazione avatar")
    anim.add_argument("--animate", metavar="ID", help="Anima un avatar esistente")
    anim.add_argument("--animate-all", action="store_true", help="Anima tutti gli avatar")
    anim.add_argument("--list-avatars", action="store_true", help="Elenca avatar con stato animazione")

    icons = parser.add_argument_group("Icone categorie")
    icons.add_argument("--generate-category-icons", action="store_true",
                       help="Genera icone PNG per tutte le categorie")
    icons.add_argument("--generate-category-icon", metavar="CATEGORY",
                       help="Genera icona PNG per una singola categoria")

    args = parser.parse_args()

    if args.reset_status:
        reset_char_status(args.reset_status)
        print(f"Reset stato per '{args.reset_status}'. Le prossime generazioni non lo salteranno.")
        return

    if args.status:
        chars = parse_characters()
        status = load_gen_status()
        total = len(chars)
        done_all = sum(1 for c in chars if is_char_done(c["id"]))
        done_avatar = sum(1 for c in chars if status.get(c["id"], {}).get("avatar"))
        done_bio = sum(1 for c in chars if status.get(c["id"], {}).get("bio"))
        done_scenario = sum(1 for c in chars if status.get(c["id"], {}).get("scenario"))
        print(f"\n=== Stato generazioni ===")
        print(f"  Personaggi totali: {total}")
        print(f"  Completi (tutti i task): {done_all}/{total}")
        print(f"  Avatar: {done_avatar}/{total}")
        print(f"  Bio: {done_bio}/{total}")
        print(f"  Scenario: {done_scenario}/{total}")
        pending = [c for c in chars if not is_char_done(c["id"])]
        if pending:
            print(f"\n  In attesa ({len(pending)}):")
            for c in pending[:20]:
                tasks = [t for t in GEN_TASKS if not status.get(c["id"], {}).get(t)]
                print(f"    {c['id']:30s} manca: {', '.join(tasks)}")
            if len(pending) > 20:
                print(f"    ... e altri {len(pending) - 20}")
        return

    has_gen = args.generate or args.generate_all or args.list_missing
    has_anim = args.animate or args.animate_all or args.list_avatars
    has_icons = args.generate_category_icons or args.generate_category_icon

    if not has_gen and not has_anim and not has_icons:
        parser.print_help()
        sys.exit(1)

    if has_gen:
        cmd_generate(args)

    if has_anim:
        cmd_animate(args)

    if has_icons:
        cmd_generate_category_icons(args)
