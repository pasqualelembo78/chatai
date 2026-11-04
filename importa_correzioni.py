#!/usr/bin/env python3
"""Importa le correzioni proposte da un correttore esterno (ChatGPT ecc.).

Legge la risposta incollata in un file, prende solo le righe JSON del dizionario,
valida e le aggiunge a `backend/language/italian-grammar.json`. Per ognuna crea anche
il caso in `verifica_correzioni.py` (prima il test, poi la regola).

Uso:
    python3 importa_correzioni.py --file /opt/aria/prove/risposta-chatgpt.txt [--prova]
"""
import argparse
import json
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
GRAMMATICA = os.path.join(QUI, "backend", "language", "italian-grammar.json")
VERIFICA = os.path.join(QUI, "verifica_correzioni.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()

    testo = open(args.file, encoding="utf-8").read()
    voci = []
    for riga in testo.splitlines():
        riga = riga.strip().strip("`, ")
        if not riga.startswith("{"):
            continue
        try:
            d = json.loads(riga)
        except Exception:
            continue
        sbagliato, giusto = (d.get("sbagliato") or "").strip(), (d.get("giusto") or "").strip()
        if not sbagliato or giusto is None:
            continue
        if len(sbagliato) > 60 or len(giusto) > 60:
            continue
        voci.append({"sbagliato": sbagliato, "giusto": giusto, "nota": (d.get("nota") or "esterno")[:90]})

    if not voci:
        sys.exit("nessuna voce JSON valida trovata nel file")

    gram = json.load(open(GRAMMATICA, encoding="utf-8"))
    esistenti = {c["sbagliato"].lower() for c in gram["correzioni_brevi"]}
    nuove = [v for v in voci if v["sbagliato"].lower() not in esistenti]

    print(f"voci valide: {len(voci)} · nuove: {len(nuove)} · già presenti: {len(voci) - len(nuove)}")
    for v in nuove:
        print(f"  {v['sbagliato']} -> {v['giusto']}")
    if args.prova:
        return

    gram["correzioni_brevi"].extend(nuove)
    json.dump(gram, open(GRAMMATICA, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # un caso di verifica per ogni nuova voce: la regola non deve poter sparire in silenzio
    testo_v = open(VERIFICA, encoding="utf-8").read()
    if nuove:
        casi = "\n".join(
            f'    ("{v["sbagliato"]}", "{v["giusto"]}", "{v["sbagliato"]}", "importata"),'
            for v in nuove)
        testo_v = testo_v.replace("    # regole generali, non singole parole",
                                  casi + "\n    # regole generali, non singole parole", 1)
        open(VERIFICA, "w", encoding="utf-8").write(testo_v)
    print(f"aggiunte {len(nuove)} voci al dizionario e a verifica_correzioni.py")


if __name__ == "__main__":
    main()
