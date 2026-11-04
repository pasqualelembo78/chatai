#!/usr/bin/env python3
"""Pulizia dell'archivio: toglie il materiale che non serve e ricostruisce l'indice.

Regole (deliberatamente prudenti, si toglie solo ciò che è chiaramente inutile):
  - risposte sotto le 6 parole
  - risposte identiche ripetute (resta la prima)
  - risposte senza nessuna parola funzione italiana
  - risposte che sono elenchi puntati o numerati
  - testi rimasti in inglese

Uso: python3 archivio/pulisci.py [--prova]
"""
import argparse
import re
import sqlite3
import os

QUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(QUI, "archivio.db")

ITALIANE = ("il", "lo", "la", "di", "che", "un", "una", "per", "con", "non", "è", "sono",
            "sei", "ho", "hai", "mi", "ti", "si", "del", "della", "nella", "sulla")
INGLESI = ("the", "and", "you", "your", "with", "this", "that", "have", "from")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    prima = conn.execute("SELECT COUNT(*) FROM frammenti").fetchone()[0]
    regole = {
        "risposta corta (<6 parole)": "parole < 6",
        "risposta che è un elenco": "risposta LIKE '%- %' OR risposta LIKE '%1. %'",
        "risposta con codice": "risposta LIKE '%```%'",
    }
    for nome, condizione in regole.items():
        n = conn.execute(f"SELECT COUNT(*) FROM frammenti WHERE {condizione}").fetchone()[0]
        print(f"  {nome}: {n}")
        if not args.prova:
            conn.execute(f"DELETE FROM frammenti WHERE {condizione}")

    # duplicati di risposta: resta la riga con id più basso
    duplicati = conn.execute(
        "SELECT COUNT(*) FROM frammenti WHERE rowid NOT IN "
        "(SELECT MIN(rowid) FROM frammenti GROUP BY risposta)").fetchone()[0]
    print(f"  risposte duplicate: {duplicati}")
    if not args.prova:
        conn.execute("DELETE FROM frammenti WHERE rowid NOT IN "
                     "(SELECT MIN(rowid) FROM frammenti GROUP BY risposta)")

    # italiano: deve avere almeno due parole funzione italiane e non troppe inglesi
    scartate = []
    for rowid, risposta in conn.execute("SELECT rowid, risposta FROM frammenti").fetchall():
        basso = " " + risposta.lower() + " "
        it = sum(1 for k in ITALIANE if f" {k} " in basso)
        en = sum(1 for k in INGLESI if f" {k} " in basso)
        if it < 2 or en > it:
            scartate.append(rowid)
    print(f"  risposte non italiane: {len(scartate)}")
    if not args.prova:
        conn.executemany("DELETE FROM frammenti WHERE rowid = ?", [(r,) for r in scartate])

    if not args.prova:
        conn.execute("INSERT INTO cerca(cerca) VALUES('rebuild')")
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    dopo = conn.execute("SELECT COUNT(*) FROM frammenti").fetchone()[0]
    print(f"\nda {prima} a {dopo} (tolte {prima - dopo})")
    conn.close()


if __name__ == "__main__":
    main()
