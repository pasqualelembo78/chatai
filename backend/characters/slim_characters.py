# -*- coding: utf-8 -*-
"""Asciuga i personaggi: via tutto ciò che in una chat erotica non serve.

Il costo di ogni risposta è la LETTURA del prompt: ogni campo che finisce nel
system prompt si paga in secondi. Qui si tengono solo identità, stanza e i pochi
dati che il motore usa davvero.

Uso:
    python3 slim_characters.py --categoria amanti-segreti [--dry-run]
    python3 slim_characters.py --tutte

I campi rimossi restano recuperabili dal backup git: il personaggio mantiene
`id`, quindi si può ricostruire.
"""

import argparse
import glob
import json
import os
import re
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TAG_MAX = 5
ESSENZA_MAX = 180
PERSONALITY_MAX = 220

DA_TOGLIERE = (
    "evolution", "personality_depth", "possessions", "family", "childhood",
    "education", "occupation", "backstory", "opening_scenario",
    "opening_scenario_variants", "conversations", "species", "birth_date",
    "personality_profile", "speaking_style", "hobbies", "stats", "rating",
    "visibility", "is_favorite", "_testo", "_resto", "generated_image",
)


def scrivi_json(path, righe):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def prima_frase(testo, limite):
    t = re.sub(r"\s+", " ", str(testo or "")).strip()
    if not t:
        return ""
    frasi = re.split(r"(?<=[.!?])\s+", t)
    out = frasi[0].strip()
    for f in frasi[1:]:
        if len(out) + len(f) > limite:
            break
        out += " " + f.strip()
    if len(out) > limite:
        out = out[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "."
    return out


def asciuga(c):
    for chiave in DA_TOGLIERE:
        c.pop(chiave, None)

    c["essence"] = prima_frase(c.get("essence"), ESSENZA_MAX)
    c["personality"] = prima_frase(c.get("personality"), PERSONALITY_MAX)
    c["tags"] = [t for t in (c.get("tags") or []) if isinstance(t, str)][:TAG_MAX]

    conoscenze = c.get("knowledge_domains")
    c["knowledge_domains"] = {"expertise": [e for e in (conoscenze or {}).get("expertise", []) if isinstance(e, str)][:3]}

    # il campo system_prompt non viene usato a runtime (si ricostruisce): si tiene corto
    c["system_prompt"] = prima_frase(c.get("system_prompt"), 240)
    c["slim"] = 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categoria", default="")
    ap.add_argument("--tutte", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.tutte:
        file_da_fare = [p for p in sorted(glob.glob(os.path.join(DATA, "*.json"))) if not p.endswith("categories.json")]
    elif args.categoria:
        file_da_fare = [os.path.join(DATA, args.categoria + ".json")]
    else:
        sys.exit("serve --categoria <slug> oppure --tutte")

    for path in file_da_fare:
        righe = json.load(open(path, encoding="utf-8"))
        prima = len(json.dumps(righe, ensure_ascii=False))
        for c in righe:
            asciuga(c)
        dopo = len(json.dumps(righe, ensure_ascii=False))
        print(f"{os.path.basename(path)}: JSON {prima // 1024} KB -> {dopo // 1024} KB, personaggi {len(righe)}")
        if not args.dry_run:
            scrivi_json(path, righe)


if __name__ == "__main__":
    main()
