#!/usr/bin/env python3
"""Estrae scambi di parlato dal corpus KIParla (trascrizione ortografica).

KIParla è trascrizione di conversazioni vere: ottima per la lingua di tutti i giorni, piena
però di segni di trascrizione (overlap, allungamenti, troncamenti) e di deittici. Qui si pulisce
e si tengono solo coppie di battute di parlanti diversi.

Licenza: CC BY-NC-SA 4.0, consultazione per ricerca e senza fini di lucro; i dati non andrebbero
inclusi in un'altra risorsa senza accordo con i responsabili. Va quindi tenuta come collezione
separata e marcata.

Uso: python3 archivio/kiparla.py --modulo KIPasti [--max 3000]
"""
import argparse
import hashlib
import io
import json
import os
import re
import urllib.request
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
BASE = "https://codeload.github.com/KIParla/{m}/zip/refs/heads/main"


def pulisci(testo):
    """La trascrizione ortografica è già pulita: via solo rumore residuo."""
    testo = re.sub(r"\bxxx?\b", " ", testo)      # incomprensibile
    testo = re.sub(r"[<>°#]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip(" .,")
    return testo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modulo", default="KIPasti")
    ap.add_argument("--max", type=int, default=3000)
    args = ap.parse_args()

    os.makedirs(DATI, exist_ok=True)
    uscita = os.path.join(DATI, f"kiparla-{args.modulo.lower()}.jsonl")
    visti = set()
    coppie = 0

    with urllib.request.urlopen(BASE.format(m=args.modulo), timeout=300) as r:
        archivio = zipfile.ZipFile(io.BytesIO(r.read()))

    nomi = [n for n in archivio.namelist() if "/linear-orthographic/" in n and n.endswith(".txt")]
    print(f"file di trascrizione: {len(nomi)}")

    with open(uscita, "w", encoding="utf-8") as f:
        for nome in nomi:
            try:
                contenuto = archivio.read(nome).decode("utf-8", "replace")
            except Exception:
                continue
            righe = []
            for riga in contenuto.splitlines():
                if "\t" not in riga:
                    continue
                parlante, testo = riga.split("\t", 1)
                testo = pulisci(testo)
                if testo:
                    righe.append((parlante.strip(), testo))
            for (s1, t1), (s2, t2) in zip(righe, righe[1:]):
                if s1 == s2 or not (3 <= len(t1.split()) <= 30) or not (3 <= len(t2.split()) <= 30):
                    continue
                chiave = hashlib.sha1((t1 + t2).encode()).hexdigest()
                if chiave in visti:
                    continue
                visti.add(chiave)
                f.write(json.dumps({
                    "messaggi": [{"role": "user", "content": t1},
                                 {"role": "assistant", "content": t2}],
                    "provenienza": f"KIParla/{args.modulo} ({nome.split('/')[-1]})",
                    "licenza": "CC BY-NC-SA 4.0 (KIParla) — non commerciale",
                    "collezione": "parlato", "categoria": "quotidiano",
                    "registro": "parlato", "esplicito": False, "stile": 1,
                }, ensure_ascii=False) + "\n")
                coppie += 1
                if coppie >= args.max:
                    break
            if coppie >= args.max:
                break
    print(f"coppie estratte: {coppie} -> {uscita}")


if __name__ == "__main__":
    main()
