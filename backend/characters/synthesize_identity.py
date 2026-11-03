# -*- coding: utf-8 -*-
"""Sintetizza in italiano l'identità dei personaggi la cui biografia è in inglese.

La `personality` e il `role`/`occupation` sono già in italiano e specifici: da lì si
costruisce una riga identitaria italiana, al posto del testo inglese che il modello
leggeva male. Chi è già stato tradotto (`identity_it`) resta com'è.

Uso: python3 synthesize_identity.py [--dry-run]
"""

import glob
import json
import os
import re
import sys

def scrivi_json(path, righe):
    """Scrittura atomica: un crash a metà non lascia il file troncato."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def inglese(testo):
    t = " " + str(testo or "").lower() + " "
    return sum(t.count(w) for w in (" the ", " is ", " and ", " of ", " his ", " her ", " was "))


def prima_frase(personality):
    testo = re.sub(r"\s+", " ", str(personality or "")).strip()
    # toglie l'introduzione col nome: "Vera è una persona..." -> "una persona..."
    testo = re.sub(r"^[A-ZÀ-Ý][\w'’\-\. ]{0,40}?\s+(è|ha|ama|sa|parla|lavora)\s+", "", testo, count=1)
    frasi = re.split(r"(?<=[.!?])\s+", testo)
    testo = " ".join(frasi[:2]).strip()
    if len(testo) > 240:
        testo = testo[:240].rsplit(" ", 1)[0]
        testo = re.sub(r"\s+(e|a|di|da|in|con|su|per|tra|fra|che|delle|degli|della|dei|dello|il|lo|la|le|gli|un|una|uno)\s*$", "", testo)
        testo = testo.rstrip(",;:") + "."
    if testo:
        testo = testo[0].upper() + testo[1:]
    return testo


def sintesi(c):
    pezzo = prima_frase(c.get("personality"))
    lavoro = ((c.get("occupation") or {}).get("title") or "").strip()
    if lavoro and (c.get("gender_display") or "").lower() == "femminile" and lavoro.endswith("o"):
        lavoro = lavoro[:-1] + "a"  # operaio -> operaia, impiegato -> impiegata
    ruolo = (c.get("original_role") or "").strip()
    coda = ""
    if lavoro:
        coda = f" Lavora come {lavoro[0].lower() + lavoro[1:]}."
    elif ruolo:
        coda = f" Ruolo: {ruolo}."
    corpo = (pezzo + coda).strip()
    return corpo[:300]


def main():
    dry = "--dry-run" in sys.argv
    fatti = 0
    esempi = []
    for path in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        if path.endswith("categories.json"):
            continue
        righe = json.load(open(path, encoding="utf-8"))
        cambiato = False
        for c in righe:
            if c.get("identity_it"):
                continue
            base = str(c.get("essence") or "").split("Stanza tematica:")[0].strip()
            if base and inglese(base) < 3 and len(base) >= 40:
                continue  # c'è già un'identità italiana

            # se la personality è solo la riga generica di categoria, meglio tradurre la bio
            if len(str(c.get("personality") or "").strip()) < 90:
                continue
            nuovo = sintesi(c)
            if not nuovo:
                continue
            c["essence"] = nuovo
            c["identity_it"] = True
            c["identity_sintetica"] = True
            fatti += 1
            cambiato = True
            if len(esempi) < 6:
                esempi.append((c["id"], nuovo))
        if cambiato and not dry:
            scrivi_json(path, righe)
    print(f"{'DRY RUN' if dry else 'FATTO'}: identità sintetizzate {fatti}")
    for i, t in esempi:
        print(f"  {i}: {t}")


if __name__ == "__main__":
    main()
