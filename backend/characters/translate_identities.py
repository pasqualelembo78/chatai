# -*- coding: utf-8 -*-
"""Traduce in italiano le biografie (essence) ancora in inglese, col modello locale.

Il prompt usa solo i primi ~240 caratteri dell'essence: si traduce la parte iniziale
(fino a 400 caratteri) e si lascia il resto com'è. Ogni personaggio tradotto viene
marcato con `identity_it` e non viene ripetuto.

Uso:
    python3 translate_identities.py --limit 8          # prova su 8 personaggi
    python3 translate_identities.py --category bdsm    # una categoria
    python3 translate_identities.py                    # tutte le categorie
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.request

def scrivi_json(path, righe):
    """Scrittura atomica: un crash a metà non lascia il file troncato."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(righe, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OLLAMA = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
MODEL = "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M"
TAGLIA = 220
LOTTO = 1

PROMPT = """Traduci in italiano naturale le biografie qui sotto.
Mantieni nomi propri, luoghi e titoli. Non aggiungere commenti, non riassumere.
Inizia ogni traduzione con "Sono <nome>".
Rispondi SOLO con una riga per personaggio, nel formato:
ID||traduzione

{brani}"""


PAROLE_INGLESI = (" the ", " is ", " and ", " of ", " his ", " her ", " was ", " with ", " from ")
PAROLE_ITALIANE = (" il ", " la ", " una ", " uno ", " che ", " sono ", " per ", " con ", " nel ", " della ", " dei ", " gli ", " si ", " di ")


def inglese(testo):
    t = " " + str(testo or "").lower() + " "
    return sum(t.count(w) for w in PAROLE_INGLESI)


MARCA_INGLESE = (" is ", " was ", " are ", " who ", " his ", " her ", " they ", " has ")


def parla_italiano(testo):
    """Accetta solo se il testo è italiano: niente verbi/possessivi inglesi, e almeno
    due parole funzionali italiane. I nomi propri inglesi non contano."""
    t = " " + str(testo or "").lower() + " "
    ita = sum(t.count(w) for w in PAROLE_ITALIANE)
    if any(m in t for m in MARCA_INGLESE):
        return False
    return ita >= 2


def genera(prompt):
    corpo = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 3072, "num_predict": 260, "num_thread": int(os.environ.get("OLLAMA_NUM_THREAD", "6"))},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r).get("response", "")


ULTIMA_RISPOSTA = ""


def traduci_lotto(gruppo):
    global ULTIMA_RISPOSTA
    brani = "\n".join(f"{c['id']}||{c['_testo']}" for c in gruppo)
    risposta = genera(PROMPT.format(brani=brani))
    ULTIMA_RISPOSTA = risposta
    mappa = {}
    ids_validi = {c["id"] for c in gruppo}
    for riga in risposta.splitlines():
        if "||" not in riga:
            continue
        i, _, testo = riga.partition("||")
        i = i.strip().strip("-*` ").lstrip("0123456789. )")
        testo = testo.strip().strip('"')
        if i in ids_validi and testo and parla_italiano(testo):
            mappa[i] = testo
    # Con un solo personaggio, se il modello omette l'ID (o usa un'intestazione) si accetta
    # la risposta intera una volta ripulita dalle righe che non sono la traduzione.
    if not mappa and len(gruppo) == 1:
        righe = [r.strip() for r in risposta.splitlines() if r.strip() and "||" not in r and r.strip().lower() not in ("id||traduzione", "traduzione:", "ecco la traduzione:")]
        pulito = " ".join(righe).strip().strip('"').strip()
        if pulito and parla_italiano(pulito):
            mappa[gruppo[0]["id"]] = pulito
    return mappa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--category", default="")
    ap.add_argument("--shard", default="", help="i/n: dividi i file tra processi")
    ap.add_argument("--solo-inglesi", action="store_true", help="solo biografie con inglese vero")
    args = ap.parse_args()

    file_da_fare = sorted(glob.glob(os.path.join(DATA, "*.json")))
    if args.category:
        file_da_fare = [p for p in file_da_fare if os.path.basename(p) == args.category + ".json"]
    if args.shard:
        i, _, n = args.shard.partition("/")
        i, n = int(i), int(n)
        file_da_fare = [p for k, p in enumerate(file_da_fare) if k % n == i]

    totale_ok = totale_saltati = 0
    for path in file_da_fare:
        if path.endswith("categories.json"):
            continue
        righe = json.load(open(path, encoding="utf-8"))
        if args.solo_inglesi:
            coda = [c for c in righe if any(m in " " + str(c.get("essence") or "").lower() + " " for m in MARCA_INGLESE)]
        else:
            coda = [c for c in righe if not c.get("identity_it") and inglese(c.get("essence")) >= 3]
        if not coda:
            continue
        if args.limit:
            coda = coda[: args.limit]

        for inizio in range(0, len(coda), LOTTO):
            gruppo = []
            for c in coda[inizio:inizio + LOTTO]:
                essenza = str(c.get("essence") or "").split("Stanza tematica:")[0].strip()
                if not essenza:
                    continue
                c["_testo"] = essenza[:TAGLIA]
                c["_resto"] = essenza[TAGLIA:].strip()
                gruppo.append(c)
            if not gruppo:
                continue
            try:
                mappa = traduci_lotto(gruppo)
            except Exception as e:  # rete/modello
                print(f"  ! lotto fallito ({e}), riprovo tra 5s", flush=True)
                time.sleep(5)
                mappa = {}

            for c in gruppo:
                nuovo = mappa.get(c["id"])
                if not nuovo:
                    totale_saltati += 1
                    with open("/tmp/raw_skip.log", "a", encoding="utf-8") as dbg:
                        dbg.write(f"--- {c['id']}\nRISPOSTA: {ULTIMA_RISPOSTA[:400]!r}\n")
                    # Rete di sicurezza: meglio un'identità italiana sintetica che l'inglese
                    from synthesize_identity import sintesi as _sintesi
                    nuovo = _sintesi(c)
                    if nuovo:
                        c["identity_sintetica"] = True
                        c["essence"] = nuovo
                        if "Stanza tematica:" not in c["essence"]:
                            pass  # la riga la riaggiunge apply_categories
                        c["identity_it"] = True
                    continue
                # "Sono <nome>." è già nella riga "Sei <nome>." del prompt: si toglie
                primo = (c.get("name") or "").split()[0].lower() if c.get("name") else ""
                if primo:
                    nuovo = re.sub(r"^(Sono|Sii|Mi chiamo|Il mio nome è)\s+" + re.escape(c["name"].split()[0]) + r"\b[^.]*\.\s*", "", nuovo, flags=re.I)
                coda_testo = " " + c["_resto"] if c["_resto"] else ""
                c["essence"] = nuovo.strip() + coda_testo
                if "Stanza tematica:" not in c["essence"]:
                    from characters import category_profiles as cp
                    meta = next(x for x in json.load(open(os.path.join(DATA, "categories.json"), encoding="utf-8")) if x["id"] == c["category"])
                    c["essence"] += "\nStanza tematica: " + meta["name"] + " — " + cp.profile_for(c["category"])["hook"] + "."
                c["identity_it"] = True
                c.pop("_testo", None)
                c.pop("_resto", None)
                totale_ok += 1

            scrivi_json(path, righe)
            print(f"{os.path.basename(path)}: tradotti finora {totale_ok} (scartati {totale_saltati})", flush=True)

    print(f"FINE: tradotti {totale_ok}, non tradotti {totale_saltati}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
