#!/usr/bin/env python3
"""Prepara una conversazione da far correggere a un correttore esterno (ChatGPT ecc.).

Mette insieme: contesto, regole di stile, i turni, e le istruzioni su come rispondere.
L'uscita è un file di testo pronto da incollare o caricare, più un blocco JSON leggibile
da macchina con le stesse coppie.

Uso:
    python3 esporta_per_chatgpt.py --file /opt/aria/prove/erotico.md
    python3 esporta_per_chatgpt.py --tutte            # tutte le prove nella cartella
    python3 esporta_per_chatgpt.py --tutte --out /opt/aria/prove/correzione.txt
"""
import argparse
import glob
import json
import os
import re

BASE = "/opt/aria/prove"


def leggi(percorso):
    """Da .jsonl (preferito) o .md: lista di coppie utente/risposta."""
    coppie = []
    if percorso.endswith(".jsonl"):
        for riga in open(percorso, encoding="utf-8"):
            try:
                d = json.loads(riga)
                coppie.append((d.get("utente", ""), d.get("risposta", "")))
            except Exception:
                continue
    else:
        testo = open(percorso, encoding="utf-8").read()
        for m in re.finditer(r"\*\*(\d+)\. U:\*\* (.*?)\n\n\*\*A \([^)]*\):\*\* (.*?)\n\n", testo, re.S):
            coppie.append((m.group(2).strip(), m.group(3).strip()))
    return coppie


INTESTAZIONE = """Sei un correttore di lingua italiana. Ti passo conversazioni reali tra un utente e
un personaggio virtuale italiano: sono risposte generate da un modello piccolo (3 miliardi di
parametri) e servono solo per trovarne i difetti.

CONTESTO DEL PROGETTO
- Sito di chat per adulti con personaggi inventati. Registro: due adulti complici, colloquiale.
- Le risposte devono stare entro 20 parole, 1-2 frasi, dirette: prima si risponde alla domanda,
  il gesto viene dopo e non la sostituisce.
- Il lessico erotico è ammesso, ma solo quando la scena lo chiede, con parole comuni
  (bocca, lingua, culo, figa, cazzo, sborra) e senza riempitivi.
- Vietati: terza persona narrativa, frasi fatte ("mi sento a mio agio", "non posso continuare"),
  verbi inventati, doppioni di parole.

COSA DEVI FARE
1. Riscrivi SOLO le risposte del personaggio (le righe "A"), lasciando intatte le domande
   dell'utente. Mantieni lunghezza e registro. Non spiegare, non commentare dentro il dialogo.
2. Elenca gli errori trovati, uno per riga, in questa forma:
   `turno N | tipo | sbagliato -> corretto`
   Tipi ammessi: grammatica, verbo, persona, ripetizione, fuori-contesto, non-risponde,
   frase-fatta, lessico-sbagliato, troppo-lunga.
3. Proponi le voci da aggiungere al dizionario delle correzioni, in JSON, forma esatta:
   {"sbagliato": "...", "giusto": "...", "nota": "..."}
   Solo forme che si ripeteranno, non correzioni una tantum.
4. Se una risposta non risponde alla domanda, dillo nella lista errori con tipo `non-risponde`.

FORMATO DELLA TUA RISPOSTA
- Prima sezione: DIALOGO CORRETTO (stessa numerazione, solo le righe A cambiate).
- Seconda sezione: ERRORI (elenco come sopra).
- Terza sezione: VOCI DIZIONARIO (JSON, una per riga).

------------------------------------------------------------------

"""


def blocco(nome, coppie):
    righe = [f"### CONVERSAZIONE: {nome}", ""]
    for i, (u, a) in enumerate(coppie, 1):
        righe.append(f"{i}. U: {u}")
        righe.append(f"   A: {a}")
        righe.append("")
    return "\n".join(righe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append")
    ap.add_argument("--tutte", action="store_true")
    ap.add_argument("--out", default=os.path.join(BASE, "da-correggere.txt"))
    args = ap.parse_args()

    file = args.file or (sorted(glob.glob(os.path.join(BASE, "*.jsonl"))) if args.tutte else [])
    if not file:
        raise SystemExit("indica --file oppure --tutte")

    parti, totale = [], 0
    for f in file:
        coppie = leggi(f)
        if not coppie:
            continue
        nome = os.path.basename(f).split(".")[0]
        parti.append(blocco(nome, coppie))
        totale += len(coppie)

    testo = INTESTAZIONE + "\n".join(parti)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(testo)
    print(f"scritto {args.out}: {totale} turni da {len(parti)} conversazioni, "
          f"{len(testo)} caratteri (~{len(testo)//4} token)")


if __name__ == "__main__":
    main()
