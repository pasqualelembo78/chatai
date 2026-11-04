#!/usr/bin/env python3
"""Qualifica i lemmi raccolti: ognuno diventa utile o scarto, con il motivo scritto.

Non si fida del registro della fonte: guarda la definizione. Una voce resta solo se il suo
significato regge in una chat — erotica o normale — e se non è un doppione, una locuzione
letterale o un senso estraneo (araldica, edilizia, nautica).

Uscita:
  - lessico-qualificato.json : tutte le voci con esito e motivo (archivio delle decisioni)
  - da_rivedere.txt          : i casi dubbi, da guardare a mano
  - backend/language/lessico/<gruppo>.json : solo le voci utili, con esempio quando c'è

Uso:
  python3 qualifica_lessico.py                 # entrambi i gruppi
  python3 qualifica_lessico.py --gruppo erotico --dettagli
"""
import argparse
import json
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
DESTINAZIONE = os.path.join(QUI, "backend/language/lessico")
REVISIONE = os.path.join(QUI, "revisione_umana.json")   # decisioni a mano, hanno la precedenza

# la definizione deve parlare di sesso per stare nel lessico erotico
SEGNALI_EROTICO = (
    "sesso", "sessual", "pene", "vagina", "vulva", "clitoride", "testicol", "sperma",
    "orgasm", "eiacul", "masturb", "anale", "orale", "rapporto", "erot", "libidin",
    "seno", "sedere", "natica", "coscia", "capezzol", "erezione", "fellatio", "cunnilingus",
    "parafili", "fetic", "bdsm", "bondage", "dominazione", "sottomission", "voyeur", "porn",
)
# non dicono "sesso" ma si usano in un discorso erotico o ammiccante
SEGNALI_USO = ("volgare", "colloquiale", "gergale", "familiare", "popolare", "scherzoso",
               "ironico", "dispregiativo", "figurato", "traslato", "sessuale")
# nucleo di parole che restano comunque: sono il cuore del registro
NUCLEO = {
    "figo", "figa", "bombare", "rompicoglioni", "pippe mentali", "celibato", "effeminato",
    "buggerare", "cazzata", "cazzone", "puttanata", "troiaio", "sveltina", "pompino",
    "bocchino", "sega", "pippa", "ditalino", "sborra", "sborrare", "scopare", "inculare",
    "cazzo", "culo", "tette", "palle", "coglioni", "mignotta", "zoccola", "puttana",
}
# roba vera ma che in chat non entra
FUORI_CONTESTO = (
    "araldic", "blason", "stemma", "merlatur", "nautic", "marinar", "natante", "vela",
    "ediliz", "muratur", "carpenteria", "botanic", "chimic", "geometr", "matematic",
    "militar", "ferrovia", "diritto", "giuridic", "contabil", "informatic",
)
# locuzioni letterali: definizione che parte con un complemento di materia o ambito
LETTERALI = ("(di ", "(specie di ", "che si applica a", "proprio di", "relativo a")


def carica(percorso):
    if not os.path.exists(percorso):
        return []
    try:
        return json.load(open(percorso, encoding="utf-8"))
    except Exception as e:
        print(f"  illeggibile {percorso}: {e}")
        return []


def carica_revisione():
    if not os.path.exists(REVISIONE):
        return {}
    try:
        return json.load(open(REVISIONE, encoding="utf-8"))
    except Exception:
        return {}


def qualifica(gruppo, voci, revisione=None):
    revisione = revisione or {}
    esiti = []
    for v in voci:
        termine = v.get("termine", "").strip()
        senso = (v.get("senso_fonte") or "").strip()
        motivo = ""
        utile = True

        if not termine or not senso:
            utile, motivo = False, "senza termine o senza definizione"
        elif len(senso) < 8:
            utile, motivo = False, "definizione troppo corta"
        elif re.search(r"^(plurale|femminile|maschile|participio|voce|variante|sinonimo)\b", senso, re.I):
            utile, motivo = False, "forma flessa o rimando"
        elif re.search(r"(mente|ista)$", termine):
            utile, motivo = False, "avverbio o etichetta, non parola d'uso"
        elif re.search(r"^termine con cui", senso, re.I):
            utile, motivo = False, "definizione di etichetta"
        elif "''" in senso:
            utile, motivo = False, "residuo di markdown"
        elif re.search(r"(talmud|torah)", termine, re.I):
            utile, motivo = False, "voce enciclopedica"
        elif "-" in termine and " " not in termine and termine != "strap-on":
            utile, motivo = False, "composto con trattino"
        else:
            basso = senso.lower()
            if any(k in basso for k in FUORI_CONTESTO):
                utile, motivo = False, "fuori contesto"
            elif (gruppo == "erotico" and not any(k in basso for k in SEGNALI_EROTICO)
                  and not any(k in basso for k in SEGNALI_USO)
                  and termine.lower() not in NUCLEO
                  and len(termine.split()) == 1):
                utile, motivo = False, "definizione non sessuale"
            elif gruppo == "comune" and basso.startswith(LETTERALI):
                utile, motivo = False, "locuzione letterale"
            elif gruppo == "comune" and len(termine.split()) == 1 and len(senso) < 25:
                utile, motivo = False, "parola singola troppo generica"
            elif " ~~ " not in senso and len(senso) > 110:
                utile, motivo = False, "definizione lunga senza esempio"

        decisione = revisione.get(termine.lower())
        if decisione == "utile":
            utile, motivo = True, "scelta a mano"
        elif decisione == "scarto":
            utile, motivo = False, "scartata a mano"

        esiti.append({
            "termine": termine,
            "gruppo": gruppo,
            "registro": v.get("registro", "comune"),
            "senso": senso,
            "fonte": v.get("fonte", ""),
            "esito": "utile" if utile else "scarto",
            "motivo": motivo,
        })
    return esiti


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gruppo", action="append", choices=["erotico", "comune"])
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()

    revisione = carica_revisione()
    gruppi = args.gruppo or ["erotico", "comune"]
    tutti, visti = [], set()
    for gruppo in gruppi:
        file_grezzo = os.path.join(QUI, "lessico-grezzo.json" if gruppo == "erotico"
                                   else "lessico-grezzo-comune.json")
        voci = carica(file_grezzo)
        print(f"→ {gruppo}: {len(voci)} voci grezze da {os.path.basename(file_grezzo)}")
        esiti = qualifica(gruppo, voci, revisione)
        for e in esiti:
            chiave = e["termine"].lower()
            if e["esito"] == "utile" and chiave in visti:
                e["esito"], e["motivo"] = "scarto", "doppione"
            if e["esito"] == "utile":
                visti.add(chiave)
            tutti.append(e)

    # le voci aggiunte a mano al lessico non devono sparire a ogni giro:
    # se stanno già nei file attivi, restano
    for gruppo in gruppi:
        percorso = os.path.join(DESTINAZIONE, f"{gruppo}.json")
        if not os.path.exists(percorso):
            continue
        attive = {v["termine"].lower() for v in json.load(open(percorso, encoding="utf-8"))}
        for e in tutti:
            if e["gruppo"] == gruppo and e["termine"].lower() in attive and e["esito"] != "utile":
                e["esito"], e["motivo"] = "utile", "presente nel lessico attivo"

    utili = [e for e in tutti if e["esito"] == "utile"]
    scarti = [e for e in tutti if e["esito"] != "utile"]

    with open(os.path.join(QUI, "lessico-qualificato.json"), "w", encoding="utf-8") as f:
        json.dump(tutti, f, ensure_ascii=False, indent=1)

    with open(os.path.join(QUI, "da_rivedere.txt"), "w", encoding="utf-8") as f:
        f.write("# Casi dubbi (definizione vaga ma possibile)\n\n")
        for e in tutti:
            if e["esito"] == "scarto" and e["motivo"] in ("definizione non sessuale",
                                                          "parola singola troppo generica"):
                f.write(f"{e['termine']} [{e['gruppo']}] — {e['senso'][:110]}\n")

    os.makedirs(DESTINAZIONE, exist_ok=True)
    for gruppo in gruppi:
        buone = [e for e in utili if e["gruppo"] == gruppo]
        percorso = os.path.join(DESTINAZIONE, f"{gruppo}.json")
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump([{"termine": e["termine"], "registro": e["registro"],
                        "senso": e["senso"], "fonte": e["fonte"]} for e in buone],
                      f, ensure_ascii=False, indent=1)
        print(f"  utili {gruppo}: {len(buone)} -> {percorso}")

    print(f"\ntotale utili: {len(utili)} · scarti: {len(scarti)}")
    if args.dettagli:
        for e in utili[:40]:
            print(f"  ok {e['termine']:26} {e['senso'][:70]}")
        for e in scarti[:20]:
            print(f"  no {e['termine']:26} [{e['motivo']}]")


if __name__ == "__main__":
    main()
