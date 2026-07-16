#!/usr/bin/env python3
"""Genera un avatar per categoria con fallback automatico."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avatar import (
    parse_characters, generate_image_free, save_avatar,
    update_characters_py, generate_italian_biography,
    update_characters_py_full, get_prompt
)

# Carica Groq key
GROQ_KEY = ""
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                GROQ_KEY = line.split("=", 1)[1].strip()
                break

chars = parse_characters()

# Prendi un personaggio per categoria (no Luna che ha già avatar)
categories_done = set()
targets = []
for c in chars:
    cat = c.get('category', 'unknown')
    if cat not in categories_done and c['id'] != 'luna':
        categories_done.add(cat)
        targets.append(c)

print(f"Genero {len(targets)} avatar (1 per categoria)...")
print(f"Provider: Pollinations -> ThisPersonDoesNotExist -> PrAvatar -> DiceBear")
print(f"Bio: Groq {'attivo' if GROQ_KEY else 'disattivo'}")
print()

ok = 0
failed = 0
for i, char in enumerate(targets):
    print(f"[{i+1}/{len(targets)}] {char['name']} ({char['id']}) - {char.get('category', '?')}")
    
    prompt = get_prompt(char)
    print(f"  Prompt: {prompt[:80]}...")
    
    # Prova generazione con fallback
    image_data = generate_image_free("pollinations", char['id'], char['name'], prompt)
    
    if image_data:
        try:
            save_avatar(char['id'], char.get('category', ""), image_data)
            update_characters_py(char['id'])
            ok += 1
            print(f"  ✅ Avatar salvato ({len(image_data)} bytes)")
        except Exception as e:
            failed += 1
            print(f"  ❌ Errore salvataggio: {e}")
    else:
        failed += 1
        print(f"  ❌ Nessun provider ha funzionato")
    
    # Biografia italiana
    if GROQ_KEY:
        print(f"  Genero biografia italiana...")
        bio = generate_italian_biography(char, GROQ_KEY)
        if bio:
            try:
                update_characters_py_full(char['id'], bio)
                print(f"  ✅ Biografia salvata!")
            except Exception as e:
                print(f"  ⚠️  Errore biografia: {e}")
        else:
            print(f"  ⚠️  Biografia non generata")
    
    # Delay tra le richieste
    time.sleep(3)
    print()

print(f"{'='*60}")
print(f"Risultato: {ok} successi, {failed} falliti su {len(targets)}")
