#!/usr/bin/env python3
"""Genera un lotto di risposte della IA da leggere e correggere.

Non giudica: chiama la chat come farebbe un utente vero, salva tutto in JSONL
(una riga per risposta) e stampa solo l'avanzamento. Le risposte poi si leggono
insieme, si classificano gli errori e si trasformano in correzioni nel codice.

Uso:
    python3 probe_qualita.py --quante 120
    python3 probe_qualita.py --quante 120 --out /tmp/opencode/risposte.jsonl --pausa 1

Riprende da dove si era fermato se il file esiste (stessa coppia personaggio+messaggio).
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:5000"
DATI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend/characters/data")

# messaggi finti: corti, lunghi, espliciti, di ruolo, generici. Servono a stanare
# gli errori ricorrenti, non a fare bella figura.
MESSAGGI = [
    # saluti e aperture
    "Ciao", "Ehi, ci sei?", "Buonasera", "Ciao, che sorpresa",
    # corti e secchi
    "Voglio te", "Sì", "Continua", "E poi?", "Ancora", "Non fermarti", "Adesso",
    # richieste d'azione
    "Che mi fai?", "Come lo faresti?", "Fammi eccitare", "Toccami", "Spogliati",
    "Mettiti in ginocchio", "Vieni qui", "Baciami", "Prendimi",
    # domande sul personaggio
    "Cosa ti eccita di più?", "Cosa ti piace farmi?", "Come stai?", "A cosa pensi?",
    "Cosa indossi adesso?", "Dove siamo?",
    # corpo, al plurale (spesso sbaglia gli articoli)
    "Ti tocco le tette", "Mi piacciono le tue cosce", "Guardo il tuo culo",
    "Ti lecco il collo", "Ti bacio la pancia",
    # messaggi lunghi, con contesto
    "Sono appena rientrato da lavoro, ho la camicia sbottonata e lei mi guarda dalla porta",
    "Sono in ritardo di venti minuti, ho solo dieci minuti: cosa facciamo?",
    "Ci siamo visti ieri e non riesco a smettere di pensarci: tu?",
    "Ho lasciato la porta aperta apposta, se vuoi entrare",
    # roleplay e direttive di scena
    "Facciamo che sei tu il capo e io l'impiegato nuovo",
    "Comandami tu, stasera", "Racconta cosa mi fai, senza girarci intorno",
    "Sorprendimi, ma senza esagerare",
    # domande fuori dal sesso (test se esce dalla parte)
    "Che giorno è oggi?", "Che ore sono?", "Conosci un buon posto qui vicino?",
    "Hai visto il telegiornale?",
    # correzioni e incomprensioni
    "Non ho capito, ripeti", "Piano, rallenta", "Troppo veloce",
    "Sì, ma con calma", "No, così no",
]


def token():
    tok = open("/tmp/ptk_admin.txt").read().strip()
    req = urllib.request.Request(
        BACKEND + "/auth/reauth",
        data=json.dumps({"persistent_token": tok}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=25))["access_token"]


def personaggi():
    fuori = []
    for nome in sorted(os.listdir(DATI)):
        if not nome.endswith(".json") or nome == "categories.json":
            continue
        try:
            elenco = json.load(open(os.path.join(DATI, nome), encoding="utf-8"))
        except Exception:
            continue
        categoria = nome[:-5]
        for p in elenco:
            if p.get("id") and p.get("personality"):
                fuori.append((categoria, p["id"]))
    return fuori


def chiama(character, testo, jwt):
    """Una chiamata; se il token scade (401) lo rinnova e riprova."""
    req = urllib.request.Request(
        BACKEND + "/chat/stream",
        data=json.dumps({"character": character, "text": testo, "username": "admin"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt},
    )
    for tentativo in range(3):
        parti = []
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                for riga in r:
                    linea = riga.decode("utf-8", "replace")
                    if linea.startswith("data:") and '"response"' in linea:
                        try:
                            parti.append(json.loads(linea[5:])["response"])
                        except Exception:
                            pass
            return parti[-1] if parti else ""
        except urllib.error.HTTPError as e:
            if e.code == 401 and tentativo < 2:
                jwt = token()
                req.remove_header("Authorization")
                req.add_header("Authorization", "Bearer " + jwt)
                continue
            raise
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quante", type=int, default=100)
    ap.add_argument("--out", default="/tmp/opencode/risposte.jsonl")
    ap.add_argument("--pausa", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    random.seed(args.seed)
    jwt = token()
    elenco = personaggi()
    if not elenco:
        sys.exit("nessun personaggio con personalità trovato")

    gia = set()
    if os.path.exists(args.out):
        for riga in open(args.out, encoding="utf-8"):
            try:
                d = json.loads(riga)
                gia.add((d["personaggio"], d["utente"]))
            except Exception:
                pass

    coppie = []
    tentativi = 0
    while len(coppie) < args.quante and tentativi < args.quante * 40:
        tentativi += 1
        categoria, pid = random.choice(elenco)
        testo = random.choice(MESSAGGI)
        if (pid, testo) in gia:
            continue
        coppie.append((categoria, pid, testo))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fatti = 0
    errori = 0
    with open(args.out, "a", encoding="utf-8") as f:
        for i, (categoria, pid, testo) in enumerate(coppie, 1):
            t0 = time.time()
            try:
                risposta = chiama(pid, testo, jwt)
            except Exception as e:
                errori += 1
                print(f"[{i}/{len(coppie)}] ERRORE {pid}: {e}", flush=True)
                continue
            if not risposta:
                errori += 1
                print(f"[{i}/{len(coppie)}] vuota {pid}", flush=True)
                continue
            f.write(json.dumps({
                "categoria": categoria, "personaggio": pid, "utente": testo,
                "risposta": risposta, "secondi": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            f.flush()
            fatti += 1
            print(f"[{i}/{len(coppie)}] {categoria}/{pid} ({time.time()-t0:.0f}s) "
                  f"{len(risposta.split())} parole", flush=True)
            time.sleep(args.pausa)
    print(f"FINE: {fatti} risposte salvate in {args.out}, {errori} errori", flush=True)


if __name__ == "__main__":
    main()
