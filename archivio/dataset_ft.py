#!/usr/bin/env python3
"""Costruisce il dataset per il fine-tuning (ChatML) dal materiale già raccolto.

Regole:
  - si usa solo materiale già qualificato (archivio) e lessico verificato
  - nessun doppione, nessuna contaminazione: la divisione train/valid/test dipende
    dall'impronta del contenuto, non dall'ordine di lettura
  - ogni record porta provenienza e licenza nel campo meta
  - il system prompt resta corto e impersonale: la personalità la dà il prompt a runtime

Uso: python3 archivio/dataset_ft.py [--max 20000]
Output: archivio/dataset_ft/{train,valid,test}.jsonl + manifest.json
"""
import argparse
import glob
import hashlib
import json
import os

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
USCITA = os.path.join(QUI, "dataset_ft")
LESSICO = os.path.join(QUI, "..", "backend", "language", "lessico")
GRAMMATICA = os.path.join(QUI, "..", "backend", "language", "italian-grammar.json")

SYSTEM = "Sei un personaggio italiano che chatta in modo naturale, breve e colloquiale."


def impronta(utente, risposta):
    return hashlib.sha1((utente + "\x00" + risposta).encode()).hexdigest()[:16]


def divisione(chiave):
    """90/5/5 deciso dall'impronta: stabile e senza contaminazione."""
    n = int(chiave[:8], 16) % 100
    if n < 90:
        return "train"
    if n < 95:
        return "valid"
    return "test"


def record(utente, risposta, provenienza, licenza, tipo):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": utente},
            {"role": "assistant", "content": risposta},
        ],
        "meta": {"provenienza": provenienza, "licenza": licenza, "tipo": tipo},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20000)
    args = ap.parse_args()
    os.makedirs(USCITA, exist_ok=True)

    visti = set()
    file_uscita = {d: open(os.path.join(USCITA, f"{d}.jsonl"), "w", encoding="utf-8")
                   for d in ("train", "valid", "test")}
    conteggi = {"train": 0, "valid": 0, "test": 0}
    per_fonte = {}

    def aggiungi(utente, risposta, provenienza, licenza, tipo):
        if not utente.strip() or not risposta.strip():
            return False
        chiave = impronta(utente, risposta)
        if chiave in visti:
            return False
        visti.add(chiave)
        d = divisione(chiave)
        file_uscita[d].write(json.dumps(record(utente, risposta, provenienza, licenza, tipo),
                                        ensure_ascii=False) + "\n")
        conteggi[d] += 1
        per_fonte[provenienza] = per_fonte.get(provenienza, 0) + 1
        return True

    # 1) dialoghi dall'archivio qualificato
    for percorso in sorted(glob.glob(os.path.join(DATI, "*.qual.jsonl"))):
        for riga in open(percorso, encoding="utf-8"):
            if sum(conteggi.values()) >= args.max:
                break
            r = json.loads(riga)
            aggiungi(r["messaggi"][0]["content"], r["messaggi"][-1]["content"],
                     r["provenienza"], r["licenza"], "dialogo")

    # 2) lessico: ogni voce diventa una micro-risposta d'uso
    for gruppo in ("erotico", "comune"):
        try:
            voci = json.load(open(os.path.join(LESSICO, f"{gruppo}.json"), encoding="utf-8"))
        except Exception:
            continue
        for v in voci:
            senso = (v.get("senso") or "").split(" ~~ ")[0].strip()
            if not senso or not v.get("termine"):
                continue
            aggiungi(f"Cosa vuol dire «{v['termine']}»?",
                     f"{senso[:1].upper()}{senso[1:]}.",
                     v.get("fonte", "lessico"), "vedi fonti.md", "lessico")

    # 3) correzioni: coppia sbagliato -> corretto
    try:
        gram = json.load(open(GRAMMATICA, encoding="utf-8"))
        for c in gram.get("correzioni_brevi", []):
            if c.get("sbagliato") and c.get("giusto"):
                aggiungi(f"Correggi: {c['sbagliato']}", c["giusto"], "correzioni", "interno",
                         "correzione")
    except Exception:
        pass

    for f in file_uscita.values():
        f.close()

    manifest = {
        "creato": os.popen("date -Iseconds").read().strip(),
        "formato": "ChatML (messages)",
        "system": SYSTEM,
        "conteggi": conteggi,
        "per_fonte": per_fonte,
        "divisione": "90/5/5 deciso da sha1(utente+risposta): nessuna contaminazione",
        "licenze": "vedi fonti.md e archivio/README.md",
    }
    with open(os.path.join(USCITA, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
