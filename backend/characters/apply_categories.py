# -*- coding: utf-8 -*-
"""Applica il contesto tematico della stanza a ogni personaggio.

Deterministico e idempotente: conserva identità, carattere e competenze
originali e AGGIUNGE la declinazione della categoria scelta. Non crea né
elimina personaggi.

Uso:
    python3 apply_categories.py --dry-run     # mostra solo un esempio per categoria
    python3 apply_categories.py               # applica (salta chi è già a versione corrente)
    python3 apply_categories.py --force       # riapplica tutto
"""

import glob
import json
import os
import sys
from datetime import datetime

def scrivi_json(path, righe):
    """Scrittura atomica: un crash a metà non lascia il file troncato."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from characters import category_profiles as cp  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VERSION = 2
CATS = json.load(open(os.path.join(DATA, "categories.json"), encoding="utf-8"))
BY_ID = {c["id"]: c for c in CATS}


def pulisci_tags(vecchi, nuovi, limite=12):
    visti, out = set(), []
    for tag in list(nuovi) + list(vecchi or []):
        if not isinstance(tag, str):
            continue
        t = tag.strip()
        if not t or t.lower() in visti:
            continue
        visti.add(t.lower())
        out.append(t)
        if len(out) >= limite:
            break
    return out


def applica(c, force=False):
    slug = c.get("category")
    meta = BY_ID.get(slug)
    prof = cp.profile_for(slug)
    if not prof or not meta:
        return False
    if not force and c.get("category_version") == VERSION:
        return False

    meta_name = meta.get("name", slug)
    c.setdefault("original_role", c.get("role", ""))

    c["role"] = cp.role_for(slug, c.get("gender_display") or c.get("gender"))
    descrizione = cp.description_for(c.get("name", ""), slug, c.get("gender_display") or c.get("gender"), meta_name)
    if descrizione:
        c["description"] = descrizione

    essenza = str(c.get("essence") or "").strip()
    riga = f"Stanza tematica: {meta_name} — {prof['hook']}."
    if "Stanza tematica:" not in essenza:
        c["essence"] = (essenza + "\n" + riga).strip()

    c["tags"] = pulisci_tags(c.get("tags"), prof["tags"])

    conoscenze = c.get("knowledge_domains")
    if not isinstance(conoscenze, dict):
        conoscenze = {}
    esperienze = [e for e in (conoscenze.get("expertise") or []) if isinstance(e, str)]
    conoscenze["expertise"] = pulisci_tags(esperienze, prof["expertise"], limite=8)
    c["knowledge_domains"] = conoscenze

    c["category_context"] = cp.context_block(slug, meta_name, meta.get("icon", ""))
    c["system_prompt"] = cp.system_prompt_for(c, meta_name, meta.get("icon", ""))
    c["category_version"] = VERSION
    c["category_applied_at"] = datetime.now().strftime("%Y-%m-%d")
    return True


def main():
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    toccati = saltati = 0
    esempi = {}

    for path in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        if path.endswith("categories.json"):
            continue
        righe = json.load(open(path, encoding="utf-8"))
        cambiati = 0
        for c in righe:
            if applica(c, force=force):
                cambiati += 1
                esempi.setdefault(c.get("category"), c)
        toccati += cambiati
        saltati += len(righe) - cambiati
        if cambiati and not dry:
            scrivi_json(path, righe)

    print(f"{'DRY RUN' if dry else 'APPLICATO'}: modificati {toccati}, invariati {saltati}")

    for slug in sorted(esempi):
        c = esempi[slug]
        print(f"\n=== {slug} | {c['name']} ===")
        print("role:", c.get("role"))
        print("description:", c.get("description"))
        print("tags:", c.get("tags")[:6])
        print("expertise:", (c.get("knowledge_domains") or {}).get("expertise")[:5])
        print("context:\n" + c.get("category_context", ""))


if __name__ == "__main__":
    main()
