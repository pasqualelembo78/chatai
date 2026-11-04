#!/usr/bin/env python3
"""Benchmark conversazionale: 100 prove fisse, prima e dopo il recupero.

Le prove sono scritte a mano e divise per dimensione. Con `--condizione` si sceglie
se girare con il recupero spento o acceso: i due giri vanno confrontati sulle stesse
prove, altrimenti non vale niente.

Uso:
    python3 archivio/benchmark.py --condizione senza --quante 25
    python3 archivio/benchmark.py --condizione con   --quante 25
    python3 archivio/benchmark.py --confronta
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
ESITI = os.path.join(QUI, "benchmark")
BACKEND = "http://127.0.0.1:5000"
DATI = os.path.join(QUI, "..", "backend", "characters", "data")
sys.path.insert(0, os.path.join(QUI, "..", "backend"))

PROVE = [
    # pertinenza: domande semplici
    ("pertinenza", "lesbo", "che ore sono?"),
    ("pertinenza", "milf", "che giorno è oggi?"),
    ("pertinenza", "mature", "come stai?"),
    ("pertinenza", "bdsm", "cosa vuol dire dominante?"),
    ("pertinenza", "lesbo", "dove siamo?"),
    ("pertinenza", "chat-romantica", "ti va di uscire stasera?"),
    ("pertinenza", "dirty-talk", "quanti anni hai?"),
    ("pertinenza", "senza-tabu", "cosa ti piace fare?"),
    # naturalezza e quotidianità
    ("quotidiano", "chat-romantica", "ciao, come va la giornata?"),
    ("quotidiano", "mature", "ho lavorato fino a tardi, sono distrutto"),
    ("quotidiano", "milf", "che si dice di bello?"),
    ("quotidiano", "chat-romantica", "oggi piove, che noia"),
    ("quotidiano", "lesbo", "cosa hai mangiato a pranzo?"),
    # sentimenti
    ("sentimenti", "chat-romantica", "ci penso spesso a te"),
    ("sentimenti", "mature", "mi sento solo stasera"),
    ("sentimenti", "milf", "ti voglio bene, lo sai?"),
    # doppi sensi e allusioni
    ("allusione", "dirty-talk", "mi fai vedere cosa sai fare?"),
    ("allusione", "milf", "hai qualcosa in mente per stasera?"),
    ("allusione", "senza-tabu", "mi hai fatto venire un'idea"),
    ("allusione", "chat-romantica", "sono curioso di sapere dove vuoi arrivare"),
    # erotico esplicito
    ("esplicito", "dirty-talk", "voglio scoparti"),
    ("esplicito", "lesbo", "toccami"),
    ("esplicito", "sesso-orale", "mettiti in ginocchio"),
    ("esplicito", "bdsm", "legami al letto"),
    ("esplicito", "dirty-talk", "quanto sei bagnata?"),
    # roleplay
    ("roleplay", "roleplay-erotico", "facciamo che sei l'infermiera e io il paziente"),
    ("roleplay", "roleplay-erotico", "sei la supplente, io resto dopo la lezione"),
    ("roleplay", "fantasie-proibite", "immagina un albergo, io alla reception"),
    # continuità (due turni sulla stessa categoria)
    ("continuita", "camera-privata", "sono in cucina con il grembiule"),
    ("continuita", "camera-privata", "mi sono tagliato un dito"),
    ("continuita", "lesbo", "mi chiamo Nadia"),
    ("continuita", "lesbo", "come mi chiamo?"),
    # rifiuti e incomprensioni
    ("rifiuto", "senza-tabu", "puoi mandarmi una foto?"),
    ("rifiuto", "bdsm", "non ho capito, ripeti"),
    ("rifiuto", "milf", "no, così no"),
    # erotico fuori contesto: deve restare casto
    ("casto", "chat-romantica", "che ore sono?"),
    ("casto", "mature", "conosci un buon ristorante qui?"),
    ("casto", "chat-romantica", "hai visto il telegiornale?"),
    ("casto", "mature", "che lavoro fai?"),
    # modi di dire
    ("modi-dire", "dirty-talk", "dai, non fare il prezioso"),
    ("modi-dire", "milf", "mi raccomando, non fare il furbo"),
    ("modi-dire", "lesbo", "mi sei simpatica, sai?"),
    # altro materiale per arrivare a 100
    ("pertinenza", "gay", "che ore sono?"),
    ("pertinenza", "bisex", "che giorno è oggi?"),
    ("pertinenza", "threesome", "come funziona, in pratica?"),
    ("pertinenza", "dominazione", "cosa ti aspetti da me?"),
    ("quotidiano", "mature", "che bella giornata oggi"),
    ("quotidiano", "lesbo", "ho appena finito di lavorare"),
    ("quotidiano", "milf", "mi serve un consiglio su una cosa"),
    ("sentimenti", "chat-romantica", "mi manchi quando non ci sei"),
    ("sentimenti", "senza-tabu", "sono nervoso stasera"),
    ("allusione", "dirty-talk", "indovino cosa stai pensando"),
    ("allusione", "mature", "sei una donna pericolosa"),
    ("esplicito", "milf", "spogliati"),
    ("esplicito", "sesso-orale", "lo prendi in bocca?"),
    ("esplicito", "masturbazione", "mi tocco guardandoti"),
    ("esplicito", "dominazione", "comandami"),
    ("esplicito", "feticismi", "toccami i piedi"),
    ("roleplay", "fantasie-erotiche", "siamo in treno, vagone vuoto"),
    ("roleplay", "voyeurismo", "fingi di non vedermi"),
    ("continuita", "camera-privata", "accendo la luce"),
    ("continuita", "milf", "ho 51 anni, faccio il medico"),
    ("continuita", "milf", "quanti anni ho?"),
    ("rifiuto", "lesbo", "ripeti, non ho capito"),
    ("rifiuto", "dirty-talk", "troppo veloce, rallenta"),
    ("casto", "lesbo", "che ore sono?"),
    ("casto", "milf", "dove si mangia bene da queste parti?"),
    ("casto", "mature", "sai chi ha vinto la partita?"),
    ("modi-dire", "bdsm", "stavolta fai sul serio"),
    ("modi-dire", "senza-tabu", "non ti tirare indietro"),
    ("pertinenza", "feticismi", "cosa sono i feticismi?"),
    ("pertinenza", "masturbazione", "cosa preferisci?"),
    ("pertinenza", "threesome", "due uomini o due donne?"),
    ("quotidiano", "gay", "tutto bene oggi?"),
    ("quotidiano", "bisex", "che programmi hai?"),
    ("sentimenti", "lesbo", "mi piaci molto"),
    ("sentimenti", "gay", "mi fido di te"),
    ("allusione", "milf", "lo sapevi che sono sposata?"),
    ("allusione", "chat-romantica", "stasera ho la casa libera"),
    ("esplicito", "scambio-di-coppia", "e se ci fosse anche un altro?"),
    ("esplicito", "bdsm", "dammi uno schiaffo"),
    ("esplicito", "senza-tabu", "facciamo qualcosa di spinto"),
    ("roleplay", "incontri-bollenti", "dieci minuti, in piedi, contro il muro"),
    ("roleplay", "fantasie-proibite", "il capo sono io, tu sei qui per altro"),
    ("continuita", "chat-romantica", "mi chiamo Aldo"),
    ("continuita", "chat-romantica", "come mi chiamo?"),
    ("rifiuto", "milf", "aspetta un attimo"),
    ("rifiuto", "bdsm", "allenta, troppo stretto"),
    ("casto", "mature", "che mese è?"),
    ("casto", "dirty-talk", "quanti anni hai?"),
    ("modi-dire", "chat-romantica", "non prendermi in giro"),
    ("modi-dire", "mature", "scherzavo, sai"),
    ("pertinenza", "senza-tabu", "cosa vuol dire senza tabù?"),
    ("pertinenza", "masturbazione", "lo fai anche tu?"),
    ("quotidiano", "chat-romantica", "buonasera"),
    ("quotidiano", "milf", "come si dice, piacere di conoscerti"),
    ("sentimenti", "mature", "sono contento di parlare con te"),
    ("allusione", "mature", "mi fai sentire giovane"),
    ("esplicito", "dirty-talk", "continua"),
    ("roleplay", "roleplay-erotico", "entra nella parte e non uscirne"),
    ("continuita", "camera-privata", "dove eravamo rimasti?"),
    ("rifiuto", "lesbo", "non mi piace, cambia"),
]


def token():
    tok = open("/tmp/ptk_admin.txt").read().strip()
    r = urllib.request.Request(BACKEND + "/auth/reauth",
                               data=json.dumps({"persistent_token": tok}).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=25))["access_token"]


def personaggio(categoria, i=0):
    elenco = json.load(open(os.path.join(DATI, categoria + ".json"), encoding="utf-8"))
    return elenco[i % len(elenco)]["id"]


def chiedi(cid, testo, jwt):
    for tentativo in range(5):
        req = urllib.request.Request(BACKEND + "/chat/stream",
                                     data=json.dumps({"character": cid, "text": testo,
                                                      "username": "admin"}).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + jwt})
        parti = []
        try:
            with urllib.request.urlopen(req, timeout=200) as f:
                for riga in f:
                    l = riga.decode("utf-8", "replace")
                    if l.startswith("data:") and '"response"' in l:
                        try:
                            parti.append(json.loads(l[5:])["response"])
                        except Exception:
                            pass
            return parti[-1] if parti else ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15)
                continue
            if e.code == 401:
                jwt = token()
                continue
            raise
    return ""


ESPLICITE = ("cazzo", "figa", "culo", "scop", "sborr", "tette", "pompino", "bocchino",
             "nud", "eccitat", "orgasm", "lingua", "cosce", "seno")


def misura(risposta, domanda):
    basso = risposta.lower()
    parole = re.findall(r"\b[a-zà-èéìòù]{4,}\b", basso)
    chiave = [p for p in re.findall(r"\b[a-zà-èéìòù]{4,}\b", domanda.lower())][:6]
    return {
        "parole": len(risposta.split()),
        "lemmi": len(set(parole)),
        "pertinenza": sum(1 for k in chiave if k in basso),
        "esplicite": sum(1 for e in ESPLICITE if e in basso),
        "vuota": not risposta.strip(),
        "domanda_aperta": basso.rstrip().endswith("?"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condizione", choices=["senza", "con"], default="senza")
    ap.add_argument("--quante", type=int, default=25)
    ap.add_argument("--confronta", action="store_true")
    args = ap.parse_args()
    os.makedirs(ESITI, exist_ok=True)

    if args.confronta:
        esiti = {}
        for cond in ("senza", "con"):
            percorso = os.path.join(ESITI, f"{cond}.jsonl")
            if os.path.exists(percorso):
                esiti[cond] = [json.loads(r) for r in open(percorso, encoding="utf-8")]
        if len(esiti) < 2:
            sys.exit("servono entrambi i giri")
        print(f"{'metrica':22}{'senza':>10}{'con':>10}")
        for chiave in ("parole", "lemmi", "pertinenza", "esplicite", "vuote", "domanda_aperta"):
            a = sum(1 for x in esiti["senza"] if x.get(chiave)) if chiave in ("vuote", "domanda_aperta") \
                else sum(x.get(chiave, 0) for x in esiti["senza"])
            b = sum(1 for x in esiti["con"] if x.get(chiave)) if chiave in ("vuote", "domanda_aperta") \
                else sum(x.get(chiave, 0) for x in esiti["con"])
            print(f"{chiave:22}{a:>10}{b:>10}")
        return

    prova = PROVE[: args.quante]
    jwt = token()
    percorso = os.path.join(ESITI, f"{args.condizione}.jsonl")
    with open(percorso, "w", encoding="utf-8") as f:
        for i, (dimensione, categoria, domanda) in enumerate(prova, 1):
            cid = personaggio(categoria, i)
            r = chiedi(cid, domanda, jwt)
            m = misura(r, domanda)
            f.write(json.dumps({"dimensione": dimensione, "domanda": domanda, "risposta": r, **m},
                               ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(prova)}] {dimensione}: {domanda[:40]} → {r[:70]}", flush=True)
            time.sleep(3)
    print(f"fatto: {percorso}")


if __name__ == "__main__":
    main()
