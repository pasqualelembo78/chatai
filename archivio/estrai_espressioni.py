#!/usr/bin/env python3
"""Estrae espressioni ricorrenti dal corpus erotico, per il lessico iniettato.

Non inventa: conta n-grammi di 3-5 parole già presenti nel materiale importato, tiene
solo quelli che ricorrono abbastanza e che contengono un verbo d'azione o un complemento
utile. Scarta i riempitivi ("ahh il tuo sperma") e i doppioni con il lessico esistente.

Uso:
  python3 archivio/estrai_espressioni.py --min 6
Output: archivio/espressioni-candidate.json e un riepilogo a schermo da leggere a mano.
"""
import argparse
import collections
import json
import os
import re

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
LESSICO = os.path.join(QUI, "..", "backend", "language", "lessico")

VERBI = ("spogliati", "spogliare", "togliti", "togli", "apri", "aprile", "metti", "mettiti",
         "vieni", "prendi", "prendimi", "tocca", "toccami", "lecca", "leccami", "succhia",
         "succhiami", "muoviti", "muovi", "gira", "girati", "alzati", "alza", "siediti",
         "baciami", "bacia", "spingi", "spingimi", "continua", "fermati", "aspetta", "guarda",
         "guardami", "stringi", "stringimi", "tieni", "ferma", "scendi", "sali", "entra",
         "infila", "sfila", "sfilati", "dammi", "fammi", "fammi vedere", "voglio", "sento")
COMPLEMENTI = ("da dietro", "a quattro zampe", "di dietro", "a pecora", "sopra di te",
               "sotto di me", "più forte", "più piano", "più veloce", "più deciso",
               "senza fermarti", "non fermarti", "ancora un po'", "ancora più")
RUMORE = ("ahh", "ohh", "mmm", "il tuo", "la tua", "il mio", "la mia", "è così", "così bene",
          "di te", "che mi", "mi stai")


def normalizza(testo):
    testo = re.sub(r"\*[^*]*\*", " ", testo)          # via le azioni fra asterischi
    testo = re.sub(r"[^\wàèéìòù' ]+", " ", testo.lower())
    return re.findall(r"[a-zàèéìòù']+", testo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=6)
    ap.add_argument("--file", default="nsfw-chat-it.qual.jsonl")
    args = ap.parse_args()

    percorso = os.path.join(DATI, args.file)
    if not os.path.exists(percorso):
        raise SystemExit(f"manca {percorso}: prima importa e qualifica")

    conteggi = collections.Counter()
    esempi = {}
    for riga in open(percorso, encoding="utf-8"):
        r = json.loads(riga)
        testo = r["messaggi"][0]["content"] + " " + r["messaggi"][-1]["content"]
        parole = normalizza(testo)
        for n in (3, 4, 5):
            for i in range(len(parole) - n + 1):
                espressione = " ".join(parole[i:i + n])
                if all(p in RUMORE for p in parole[i:i + n]):
                    continue
                conteggi[espressione] += 1
                esempi.setdefault(espressione, testo.strip()[:140])

    # doppioni e varianti: se una versione più corta ha quasi la stessa frequenza, tengo la corta
    scelte = {}
    for espressione, n in conteggi.most_common():
        if n < args.min:
            break
        if not any(v in espressione for v in VERBI) and not any(
                c in espressione for c in COMPLEMENTI):
            continue
        if espressione.startswith(("ahh", "ohh", "mmm")):
            continue
        ridondante = False
        for altra in list(scelte):
            if espressione in altra and scelte[altra] > n * 0.8:
                ridondante = True
                break
            if altra in espressione and n < scelte[altra] * 1.25:
                ridondante = True
                break
        if ridondante:
            continue
        scelte[espressione] = n

    # doppioni col lessico esistente
    gia = set()
    for gruppo in ("erotico", "comune"):
        try:
            for v in json.load(open(os.path.join(LESSICO, f"{gruppo}.json"), encoding="utf-8")):
                gia.add((v.get("termine") or "").lower().strip())
        except Exception:
            pass

    fuori = []
    for espressione, n in scelte.items():
        if espressione in gia:
            continue
        fuori.append({"termine": espressione, "volte": n,
                      "esempio": esempi.get(espressione, "")})

    fuori.sort(key=lambda x: -x["volte"])
    with open(os.path.join(QUI, "espressioni-candidate.json"), "w", encoding="utf-8") as f:
        json.dump(fuori, f, ensure_ascii=False, indent=1)

    print(f"candidate: {len(fuori)} (min {args.min})")
    for v in fuori[:40]:
        print(f"  {v['volte']:3}x  {v['termine']}")
    print(f"\nfile: {os.path.join(QUI, 'espressioni-candidate.json')}")


if __name__ == "__main__":
    main()
