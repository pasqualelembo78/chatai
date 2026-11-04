#!/usr/bin/env python3
"""Pubblica il sito su directory italiane che accettano l'invio senza account.

Le directory "gratis e senza scambio" sono vecchie e quasi tutte usano un CAPTCHA immagine:
qui il codice viene letto con tesseract e, se la directory lo rifiuta, si riprova con un
CAPTCHA nuovo (fino a --tentativi). Ogni esito viene registrato in `backlink_invii.log`.

Uso:
    python3 pubblica_directory.py --sito golink
    python3 pubblica_directory.py --sito golink --prova     # non invia, mostra i campi
"""
import argparse
import http.cookiejar
import os
import random
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

SITO = "https://pornovirtuale.com"
EMAIL = "info@pornovirtuale.com"
TITOLO = "Chat erotiche in italiano con personaggi inventati"
DESCRIZIONE = ("Pornovirtuale: 24 stanze di chat a tema con personaggi inventati e 4 messaggi di "
               "prova senza registrarsi. Chat in italiano per adulti, personaggi originali, "
               "nessun nome protetto.")
PAROLE = "chat erotiche, chat adulti, personaggi virtuali, chat in italiano, roleplay"
CATEGORIA = "Tempo libero / Chat"

TESTA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

DESTINAZIONI = {
    "golink": {
        "url": "http://www.golink.it/addurl.php",
        "captcha": "http://www.golink.it/include/captcha/captcha.php",
        "campi": {"titolo": TITOLO, "link": SITO, "descrizione": DESCRIZIONE,
                  "parolechiavi": PAROLE, "email": EMAIL, "categoria": CATEGORIA},
        # non c'è un messaggio di conferma: se il modulo col captcha non c'è più, è andata
        "successo": r"(grazie|inserit|aggiunt|ricevut)",
        "form_rifatto": r'name="code"',
    },
}


def sessione():
    cesto = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cesto))


def leggi(op, url):
    with op.open(urllib.request.Request(url, headers=TESTA), timeout=30) as r:
        return r.read()


def leggi_testo(op, url):
    return leggi(op, url).decode("utf-8", "replace")


def leggi_captcha(op, url):
    """Legge il codice provando più preparazioni e tenendo la lettura più plausibile."""
    dati = leggi(op, url)
    percorso = tempfile.mktemp(suffix=".png")
    open(percorso, "wb").write(dati)
    candidati = []
    try:
        for prepara in ([], ["-resize", "400%", "-colorspace", "gray"],
                        ["-resize", "600%", "-colorspace", "gray", "-sharpen", "0x2"]):
            img = percorso
            if prepara:
                img = tempfile.mktemp(suffix=".png")
                subprocess.run(["convert", percorso] + prepara + [img], capture_output=True, timeout=20)
            for psm in ("7", "8"):
                esito = subprocess.run(["tesseract", img, "stdout", "--psm", psm],
                                       capture_output=True, timeout=25)
                testo = re.sub(r"[^A-Za-z0-9]", "", esito.stdout.decode())
                if 4 <= len(testo) <= 6:
                    candidati.append(testo)
            if img != percorso and os.path.exists(img):
                os.unlink(img)
    finally:
        os.unlink(percorso)
    if not candidati:
        return ""
    # la lettura più frequente vince
    return max(set(candidati), key=candidati.count)


def log(riga):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backlink_invii.log"), "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M") + " " + riga + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sito", required=True, choices=sorted(DESTINAZIONI))
    ap.add_argument("--tentativi", type=int, default=8)
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()

    d = DESTINAZIONI[args.sito]
    if args.prova:
        print("URL:", d["url"])
        for k, v in d["campi"].items():
            print(f"  {k}: {v[:80]}")
        return

    for tentativo in range(1, args.tentativi + 1):
        op = sessione()
        try:
            leggi_testo(op, d["url"])
            time.sleep(1)
            codice = leggi_captcha(op, d["captcha"])
            if len(codice) < 4:
                print(f"[{tentativo}] captcha illeggibile ({codice!r})")
                continue
            corpo = dict(d["campi"], code=codice)
            richiesta = urllib.request.Request(
                d["url"], data=urllib.parse.urlencode(corpo).encode(),
                headers={**TESTA, "Referer": d["url"],
                         "Content-Type": "application/x-www-form-urlencoded"})
            with op.open(richiesta, timeout=40) as r:
                pagina = r.read().decode("utf-8", "replace")
            basso = pagina.lower()
            if re.search(d["successo"], basso) or not re.search(d["form_rifatto"], pagina):
                print(f"[{tentativo}] pubblicato con captcha {codice!r}")
                log(f"{args.sito} OK captcha={codice} url={SITO}")
                return
            print(f"[{tentativo}] rifiutato con captcha {codice!r}")
        except Exception as e:
            print(f"[{tentativo}] errore: {str(e)[:70]}")
        time.sleep(2)

    log(f"{args.sito} FALLITO dopo {args.tentativi} tentativi")
    print("non pubblicato: guarda il log")


if __name__ == "__main__":
    main()
