#!/usr/bin/env python3
"""Registra conversazioni con la IA, turno per turno, per poi leggerle e correggere.

A differenza di `probe_qualita.py` (una domanda secca per volta, a caso) qui ci sono
conversazioni scritte a mano, con un filo: servono a vedere se il modello tiene la scena,
se risponde, se si ripete, se ricorda. Ogni conversazione usa un personaggio diverso,
così non si sporca la memoria dell'utente.

Uso:
    python3 registra_conversazioni.py                  # tutte, con i turni previsti
    python3 registra_conversazioni.py --scenario calma
    python3 registra_conversazioni.py --turni 3        # massimo 3 turni per conversazione
    python3 registra_conversazioni.py --out /tmp/opencode/conv --pausa 2

Scrive un .md leggibile e un .jsonl per ogni conversazione, più un riepilogo finale con
lunghezza, tempi e ripetizioni. Il token scade: allo scadere si riautentica da solo.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:5000"
DATI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend/characters/data")

# Ogni conversazione: nome, categoria, indice del personaggio, turni dell'utente.
# I turni sono scritti per mettere alla prova cose diverse (vedi "cosa guarda").
CONVERSAZIONI = [
    {
        "nome": "calma",
        "cosa_guarda": "conversazione normale: risponde o svicola? resta sul pezzo?",
        "categoria": "chat-romantica",
        "indice": 70,
        "turni": [
            "Ciao, come va la giornata?",
            "Ho lavorato fino a tardi, sono distrutto",
            "Tu che hai fatto invece?",
            "Mi va di stare un po' tranquillo, niente di impegnativo",
            "Raccontami tu qualcosa, allora",
        ],
    },
    {
        "nome": "scena",
        "cosa_guarda": "continuità della scena: il luogo detto dall'utente vince sulla stanza?",
        "categoria": "camera-privata",
        "indice": 71,
        "turni": [
            "Sono in cucina, sto tagliando le verdure con il grembiule",
            "Mi sono tagliato un dito, sanguino",
            "Mi hai preso la mano, cosa fai?",
            "Dove eravamo rimasti?",
            "Riprendi da lì",
        ],
    },
    {
        "nome": "memoria",
        "cosa_guarda": "ricorda i dati dichiarati e li usa senza confondersi?",
        "categoria": "mature",
        "indice": 72,
        "turni": [
            "Ciao, mi chiamo Aldo, ho 58 anni e faccio il pescivendolo",
            "Cosa ti colpisce di me?",
            "Come mi chiamo?",
            "Quanti anni ho?",
            "Che lavoro faccio?",
        ],
    },
    {
        "nome": "erotico",
        "cosa_guarda": "sa essere esplicito senza perdere la grammatica?",
        "categoria": "dirty-talk",
        "indice": 73,
        "turni": [
            "Voglio scoparti",
            "Come lo faresti?",
            "Continua",
            "Più deciso",
            "Adesso tocca a te",
        ],
    },
    {
        "nome": "roleplay",
        "cosa_guarda": "entra nella parte e ci resta?",
        "categoria": "roleplay-erotico",
        "indice": 74,
        "turni": [
            "Facciamo che sei l'infermiera del turno di notte e io il paziente insonne",
            "Mi controlli la febbre",
            "Il termometro è freddo",
            "Mi sembra che tu ci stia prendendo gusto",
        ],
    },
    {
        "nome": "servizio",
        "cosa_guarda": "domande di servizio in mezzo alla scena: risponde e resta nella parte?",
        "categoria": "milf",
        "indice": 75,
        "turni": [
            "Ti va di uscire stasera?",
            "Che ore sono?",
            "Che giorno è oggi?",
            "Dove potremmo andare?",
            "Quindi ci vediamo?",
        ],
    },
    {
        "nome": "correzioni",
        "cosa_guarda": "accetta le correzioni o ripete l'errore?",
        "categoria": "bdsm",
        "indice": 76,
        "turni": [
            "Legami al letto",
            "No, le mani avanti",
            "Troppo stretto, allenta",
            "Va bene così. Adesso?",
        ],
    },
    {
        "nome": "lunga",
        "cosa_guarda": "dopo molti turni: si stilla, si ripete, perde il filo?",
        "categoria": "lesbo",
        "indice": 77,
        "turni": [
            "Ciao, mi chiamo Nadia e sono appena entrata",
            "Che posto è questo?",
            "Mi piace il profumo che c'è",
            "Vieni più vicina",
            "Toccami i capelli",
            "Ora baciami",
            "Dove eravamo rimasti?",
            "Riprendi",
            "Cosa ho detto all'inizio?",
            "Continua",
        ],
    },
    {
        "nome": "fuori tema",
        "cosa_guarda": "tiene la parte su domande che non c'entrano nulla?",
        "categoria": "senza-tabu",
        "indice": 78,
        "turni": [
            "Hai visto il telegiornale stasera?",
            "Conosci un ristorante qui vicino?",
            "Sai chi ha vinto la partita?",
            "Comunque, dove eravamo?",
        ],
    },
]


def scegli_dal_menu():
    """Domanda iniziale: quale tipo di test. Nessun argomento = menu interattivo."""
    print("Che tipo di test vuoi registrare?\n")
    for i, c in enumerate(CONVERSAZIONI, 1):
        print(f"  {i}. {c['nome']:12} {c['cosa_guarda']}")
    print(f"  {len(CONVERSAZIONI) + 1}. tutte")
    print("\nNumeri separati da virgola (es. 2,5), Invio = tutte, q = esci.")

    while True:
        try:
            scelta = input("\nScelta: ").strip().lower()
        except EOFError:
            return [c["nome"] for c in CONVERSAZIONI]
        if scelta in ("q", "quit", "esci"):
            sys.exit("niente da fare, esco.")
        if not scelta:
            return [c["nome"] for c in CONVERSAZIONI]
        nomi, validi = [], True
        for pezzo in scelta.replace(";", ",").split(","):
            pezzo = pezzo.strip()
            if not pezzo:
                continue
            if pezzo.isdigit():
                n = int(pezzo)
                if 1 <= n <= len(CONVERSAZIONI):
                    nomi.append(CONVERSAZIONI[n - 1]["nome"])
                elif n == len(CONVERSAZIONI) + 1:
                    return [c["nome"] for c in CONVERSAZIONI]
                else:
                    validi = False
            elif pezzo in {c["nome"] for c in CONVERSAZIONI}:
                nomi.append(pezzo)
            else:
                validi = False
        if nomi and validi:
            return list(dict.fromkeys(nomi))
        print("Scelta non valida, riprovo.")


def chiedi_turni(predefinito):
    try:
        risposta = input(f"Turni per conversazione [tutti = {predefinito}]: ").strip()
    except EOFError:
        return predefinito
    if not risposta.isdigit() or int(risposta) < 1:
        return predefinito
    return min(int(risposta), predefinito)


def token():
    tok = open("/tmp/ptk_admin.txt").read().strip()
    r = urllib.request.Request(
        BACKEND + "/auth/reauth",
        data=json.dumps({"persistent_token": tok}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(r, timeout=25))["access_token"]


def personaggio(categoria, indice):
    elenco = json.load(open(os.path.join(DATI, categoria + ".json"), encoding="utf-8"))
    return elenco[indice % len(elenco)]


def turno(character_id, testo, jwt):
    for tentativo in range(3):
        r = urllib.request.Request(
            BACKEND + "/chat/stream",
            data=json.dumps({"character": character_id, "text": testo, "username": "admin"}).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt},
        )
        parti = []
        try:
            with urllib.request.urlopen(r, timeout=200) as f:
                for riga in f:
                    l = riga.decode("utf-8", "replace")
                    if l.startswith("data:") and '"response"' in l:
                        try:
                            parti.append(json.loads(l[5:])["response"])
                        except Exception:
                            pass
            return parti[-1] if parti else ""
        except urllib.error.HTTPError as e:
            if e.code == 401 and tentativo < 2:
                jwt = token()
                continue
            raise
    return ""


def ripetizioni(risposte):
    """Frasi (5+ parole) già uscite in questa conversazione."""
    viste, doppie = set(), []
    for r in risposte:
        for frase in re.split(r"(?<=[.!?])\s+", r.lower()):
            frase = frase.strip(" .,!?\"")
            if len(frase.split()) >= 5:
                if frase in viste:
                    doppie.append(frase)
                viste.add(frase)
    return doppie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", action="append", help="nome della conversazione (ripetibile)")
    ap.add_argument("--turni", type=int, default=99)
    ap.add_argument("--out", default="/tmp/opencode/conversazioni")
    ap.add_argument("--pausa", type=float, default=1.5)
    args = ap.parse_args()

    if args.scenario:
        scelte = [c for c in CONVERSAZIONI if c["nome"] in args.scenario]
        if not scelte:
            sys.exit("nessuna conversazione trovata: " + ", ".join(c["nome"] for c in CONVERSAZIONI))
    else:
        scelti = scegli_dal_menu()  # una chiamata sola: dentro la comprensione si ripeterebbe
        scelte = [c for c in CONVERSAZIONI if c["nome"] in scelti]
        if not args.turni or args.turni >= 99:
            args.turni = chiedi_turni(max(len(c["turni"]) for c in scelte))

    os.makedirs(args.out, exist_ok=True)
    jwt = token()
    riepilogo = []

    for conv in scelte:
        p = personaggio(conv["categoria"], conv["indice"])
        cid, nome = p["id"], p.get("name", "?")
        base = os.path.join(args.out, conv["nome"])
        risposte, tempi = [], []
        with open(base + ".md", "w", encoding="utf-8") as md, open(base + ".jsonl", "w", encoding="utf-8") as js:
            md.write(f"# {conv['nome']} — {nome} ({conv['categoria']})\n"
                     f"Cosa guarda: {conv['cosa_guarda']}\n\n")
            print(f"\n=== {conv['nome']} — {nome} ({conv['categoria']}) ===", flush=True)
            for i, msg in enumerate(conv["turni"][: args.turni], 1):
                t0 = time.time()
                try:
                    r = turno(cid, msg, jwt)
                except Exception as e:
                    r = f"[ERRORE: {e}]"
                dt = round(time.time() - t0, 1)
                risposte.append(r)
                tempi.append(dt)
                md.write(f"**{i}. U:** {msg}\n\n**A ({dt}s):** {r}\n\n")
                md.flush()
                js.write(json.dumps({"turno": i, "utente": msg, "risposta": r, "secondi": dt},
                                    ensure_ascii=False) + "\n")
                js.flush()
                print(f"  {i}. U: {msg}\n     A ({dt}s): {r[:160]}", flush=True)
                time.sleep(args.pausa)

            doppie = ripetizioni(risposte)
            md.write(f"\n---\nRipetizioni: {len(doppie)}\n")
            for d in doppie:
                md.write(f"- {d}\n")
            parole = sum(len(r.split()) for r in risposte) / max(1, len(risposte))
            md.write(f"Media parole: {parole:.1f} · Tempo medio: {sum(tempi)/max(1, len(tempi)):.1f}s\n")
            riepilogo.append((conv["nome"], len(risposte), parole,
                              sum(tempi) / max(1, len(tempi)), len(doppie), sum(r == "" for r in risposte)))
            print(f"  -> {len(doppie)} ripetizioni, {parole:.1f} parole medie", flush=True)

    print("\n=== RIEPILOGO ===")
    print(f"{'conversazione':16} {'turni':>6} {'parole':>7} {'tempo':>6} {'ripet':>6} {'vuote':>6}")
    for nome, n, parole, tempo, doppie, vuote in riepilogo:
        print(f"{nome:16} {n:>6} {parole:>7.1f} {tempo:>5.1f}s {doppie:>6} {vuote:>6}")
    print(f"\nFile in {args.out}")


if __name__ == "__main__":
    main()
