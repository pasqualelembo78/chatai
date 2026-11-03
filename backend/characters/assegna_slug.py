# -*- coding: utf-8 -*-
"""Assegna uno slug SEO a un sottoinsieme di personaggi (fase 1).

Le pagine personaggio nascono solo per chi riceve uno slug: si parte da 200,
scelti a rotazione tra le categorie e preferendo i dati più completi. Gli altri
restano raggiungibili da ?char= e verranno promossi in fasi successive.

Uso: python3 assegna_slug.py [--per-categoria 9]
"""

import glob
import json
import os
import re
import sys
import unicodedata

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TOTALE_MAX = 200


def slugify(testo):
    t = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return re.sub(r"-{2,}", "-", t)[:70]


def scrivi(path, righe):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def main():
    per_categoria = 9
    if "--per-categoria" in sys.argv:
        per_categoria = int(sys.argv[sys.argv.index("--per-categoria") + 1])
    if "--tutte" in sys.argv:
        per_categoria = 10000
        globals()['TOTALE_MAX'] = 100000

    file_cat = [p for p in sorted(glob.glob(os.path.join(DATA, "*.json"))) if not p.endswith("categories.json")]
    dati = {p: json.load(open(p, encoding="utf-8")) for p in file_cat}
    occupati = {c.get("slug") for righe in dati.values() for c in righe if c.get("slug")}

    # round robin: un personaggio per categoria a ogni giro, così tutte le stanze
    # hanno pagine subito invece di concentrarle in poche categorie
    scelti = 0
    for giro in range(per_categoria):
        for p in file_cat:
            if scelti >= TOTALE_MAX:
                break
            candidati = [c for c in dati[p] if not c.get("slug")]
            # prima i personaggi con più dati utili
            candidati.sort(key=lambda c: (0 if c.get("job") else 1, len(c.get("personality") or "") * -1, c["id"]))
            if not candidati:
                continue
            c = candidati[0]
            base = slugify(c.get("full_name") or c.get("name") or c["id"])
            slug, i = base, 2
            while slug in occupati:
                slug = f"{base}-{i}"
                i += 1
            c["slug"] = slug
            occupati.add(slug)
            scelti += 1

    for p, righe in dati.items():
        scrivi(p, righe)
    print(f"slug assegnati: {scelti} su {sum(len(r) for r in dati.values())} personaggi")


if __name__ == "__main__":
    main()
