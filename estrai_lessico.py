#!/usr/bin/env python3
"""Estrae lemmi da glossari pubblici di sessualità: solo le PAROLE, non i testi.

Prende i termini (e il registro quando la fonte lo dichiara), li pulisce, scarta la
monnezza con hunspell e scrive `lessico-grezzo.json`. Definizioni ed esempi si
riscrivono dopo: così restiamo fuori dai vincoli di licenza (alcune fonti sono
CC BY-NC-ND, che vieta le opere derivate: l'elenco di lemmi è un fatto, il testo no).

Uso:
    python3 estrai_lessico.py                 # tutte le fonti
    python3 estrai_lessico.py --mostra 50     # stampa i primi 50 candidati
    python3 estrai_lessico.py --fonte parliamoitaliano

Output: lessico-grezzo.json, fonti.md, lessico-scartati.txt
"""
import argparse
import json
import os
import re
import subprocess
import urllib.request

UA = "Mozilla/5.0 (compatibile; raccolta lemmi; +https://pornovirtuale.com)"
QUI = os.path.dirname(os.path.abspath(__file__))
USCITA = os.path.join(QUI, "lessico-grezzo.json")
SCARTI = os.path.join(QUI, "lessico-scartati.txt")

FONTI = [
    {
        "id": "parliamoitaliano",
        "url": "http://parliamoitaliano.altervista.org/il-linguaggio-volgare-del-sesso/",
        "licenza": "CC BY-NC-ND 3.0",
        "tipo": "righe",       # "**termine** / **termine**: definizione. Registro."
        "registro": "colloquiale",
    },
    {
        "id": "parliamoitaliano-espressioni",
        "url": "http://parliamoitaliano.altervista.org/espressioni-volgari/",
        "licenza": "CC BY-NC-ND 3.0",
        "tipo": "righe",
        "registro": "colloquiale",
    },
    {
        "id": "raccontivietati",
        "url": "https://raccontivietati.com/dizionario-del-sesso-e-porno/",
        "licenza": "sito commerciale, uso informativo",
        "tipo": "term-title",   # <span class="term-title">Termine - descrizione</span>
        "registro": "tecnico",
    },
    {
        "id": "sensamo",
        "url": "https://sensamo.it/glossario-sesso/",
        "licenza": "sito commerciale, uso informativo",
        "tipo": "h2",          # "## Termine" seguito dal paragrafo
        "registro": "tecnico",
    },
]

# termini che hunspell non conosce ma che sono italiani e vivi
NOTI = {
    "cazzo", "figa", "fica", "culo", "sborra", "sborrare", "sega", "pippa", "ditalino",
    "pompino", "bocchino", "spompinare", "inculare", "scopare", "fottere", "chiavare",
    "trombare", "pippare", "arrapato", "arrapare", "zinne", "sise", "pere", "verga",
    "uccello", "pisello", "pisellino", "patatina", "farfallina", "coglioni", "palle",
    "ciucciare", "leccare", "slabbrare", "succhia", "succhio", "segone", "pompino",
    "anilingus", "cunnilingus", "cunnilingio", "fellatio", "frottage", "pegging",
    "tribadismo", "sforbicata", "deepthroating", "spanking", "squirting", "rimming",
    "fistfucking", "bondage", "shibari", "strap-on", "strapon", "dildo", "vibratore",
}
# parole troppo generiche per stare in un lessico
TROPPO_GENERICHE = {
    "sesso", "persona", "pratica", "pratiche", "uomo", "donna", "partner", "corpo",
    "atto", "atti", "rapporto", "rapporti", "zona", "parte", "modo", "volta",
}


def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def _testo(html):
    """Toglie i tag tenendo il testo (per le parti che non ci interessano)."""
    import html as _h
    senza = re.sub(r"<[^>]+>", "", html)
    return _h.unescape(senza).strip()


def da_righe(testo):
    """Paragrafi tipo '<strong>Scopare</strong> / <strong>fottere</strong>: fare sesso. Volgare.'
    Accetta anche il markdown (**termine**), utile se la pagina arriva già convertita."""
    fuori = []
    blocchi = re.findall(r"<p[^>]*>(.*?)</p>", testo, re.S | re.I)
    if not blocchi:
        blocchi = testo.splitlines()
    for riga in blocchi:
        riga = riga.strip()
        if ":" not in riga or len(riga) > 600 or "http" in riga.lower():
            continue
        if "<strong>" in riga:
            testa_html, coda = riga.split(":", 1)
            if "<strong>" not in testa_html:
                continue
            testa = " / ".join(re.findall(r"<strong>(.*?)</strong>", testa_html, re.S))
            coda = _testo(coda)
        else:
            testa, coda = riga.split(":", 1)
            if "**" not in testa:
                continue
        registro = ""
        if re.search(r"\bvolgare\b", coda, re.I):
            registro = "volgare"
        elif re.search(r"(poco volgare|meno volgare|non molto volgare)", coda, re.I):
            registro = "colloquiale"
        elif re.search(r"si dice ai bambini|bambini", coda, re.I):
            registro = "vezzeggiativo"
        fuori.append((testa, registro, coda.strip()[:120]))
    return fuori


def da_h2(testo):
    """Titoli di sezione <h2>Termine</h2> con il paragrafo successivo come spiegazione."""
    fuori = []
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|<footer|$)", testo, re.S | re.I):
        termine = _testo(m.group(1))
        if not termine or len(termine) > 60:
            continue
        paragrafi = re.findall(r"<p[^>]*>(.*?)</p>", m.group(2), re.S | re.I)
        spiegazione = _testo(paragrafi[0])[:120] if paragrafi else ""
        fuori.append((termine, "", spiegazione))
    return fuori


def da_term_title(testo):
    """Elenchi tipo <span class="term-title">Termine - descrizione</span>."""
    fuori = []
    for m in re.finditer(r'class="term-title"[^>]*>(.*?)</span>', testo, re.S | re.I):
        testo_titolo = _testo(m.group(1))
        testa, _, coda = re.split(r"\s[–—-]\s", testo_titolo, maxsplit=1)[0], None, None
        parti = re.split(r"\s[–—-]\s", testo_titolo, maxsplit=1)
        testa = parti[0]
        coda = parti[1] if len(parti) > 1 else ""
        fuori.append((testa, "", coda[:120]))
    return fuori


def normalizza(testa):
    """'**Scopare** / **fottere** / **chiavare**' -> ['scopare', 'fottere', 'chiavare']"""
    testa = re.sub(r"\*+", "", testa)
    testa = re.sub(r"\[|\]|\([^)]*\)", "", testa)
    pezzi = re.split(r"[/,;]| oppure | o ", testa)
    buoni = []
    for p in pezzi:
        p = p.strip(" .:—-").lower()
        p = re.sub(r"\s+", " ", p)
        if not p or len(p) < 3 or len(p) > 28:
            continue
        if p in TROPPO_GENERICHE:
            continue
        if not re.fullmatch(r"[a-zàèéìòù' -]+", p):
            continue
        if len(p.split()) > 3:
            continue
        buoni.append(p)
    return buoni


def conosce(parola):
    if parola in NOTI:
        return True
    try:
        esito = subprocess.run(["hunspell", "-d", "it_IT", "-l"],
                               input=parola.encode(), capture_output=True, timeout=5)
    except Exception:
        return True
    return not esito.stdout.decode().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonte", action="append")
    ap.add_argument("--mostra", type=int, default=20)
    args = ap.parse_args()

    voci = {}
    scartati = []
    for fonte in FONTI:
        if args.fonte and fonte["id"] not in args.fonte:
            continue
        print(f"→ {fonte['id']}: {fonte['url']}")
        try:
            testo = scarica(fonte["url"])
        except Exception as e:
            print(f"  non raggiungibile: {e}")
            continue
        grezze = {"righe": da_righe, "h2": da_h2, "term-title": da_term_title}[fonte["tipo"]](testo)
        print(f"  righe utili: {len(grezze)}")
        for testa, registro, senso in grezze:
            for parola in normalizza(testa):
                if parola in voci:
                    continue
                if not conosce(parola):
                    scartati.append(f"{parola} ({fonte['id']})")
                    continue
                voci[parola] = {
                    "termine": parola,
                    "registro": registro or fonte["registro"],
                    "fonte": fonte["id"],
                    "senso_fonte": senso,
                }

    with open(USCITA, "w", encoding="utf-8") as f:
        json.dump(sorted(voci.values(), key=lambda v: v["termine"]), f,
                  ensure_ascii=False, indent=2)
    with open(SCARTI, "w", encoding="utf-8") as f:
        f.write("\n".join(scartati))

    os.makedirs(QUI, exist_ok=True)
    with open(os.path.join(QUI, "fonti.md"), "a", encoding="utf-8") as f:
        for fonte in FONTI:
            if args.fonte and fonte["id"] not in args.fonte:
                continue
            f.write(f"- {fonte['id']} — {fonte['url']} — licenza: {fonte['licenza']}\n")

    print(f"\nlemmi tenuti: {len(voci)} · scartati: {len(scartati)}")
    print(f"file: {USCITA}\n")
    for v in sorted(voci.values(), key=lambda v: v["termine"])[: args.mostra]:
        print(f"  {v['termine']:22} [{v['registro']}] {v['senso_fonte'][:60]}")


if __name__ == "__main__":
    main()
