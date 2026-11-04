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
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatibile; raccolta lemmi; +https://pornovirtuale.com)"
QUI = os.path.dirname(os.path.abspath(__file__))

FONTI = [
    {
        "id": "wiktionary-volgari",
        "url": "https://it.wiktionary.org/wiki/Categoria:Parole_volgari-IT",
        "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)",
        "tipo": "wiktionary",
        "categoria": "Categoria:Parole volgari-IT",
        "registro": "volgare",
    },
    {
        "id": "wiktionary-sessualita",
        "url": "https://it.wiktionary.org/wiki/Categoria:Sessualità-IT",
        "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)",
        "tipo": "wiktionary",
        "categoria": "Categoria:Sessualità-IT",
        "registro": "tecnico",
    },
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

# Italiano comune: espressioni, interiezioni, locuzioni. Niente volgarità.
FONTI_COMUNE = [
    {"id": "wikt-espressioni", "url": "https://it.wiktionary.org/wiki/Categoria:Espressioni_in_italiano",
     "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)", "tipo": "wiktionary",
     "categoria": "Categoria:Espressioni in italiano", "registro": "comune"},
    {"id": "wikt-interiezioni", "url": "https://it.wiktionary.org/wiki/Categoria:Interiezioni_in_italiano",
     "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)", "tipo": "wiktionary",
     "categoria": "Categoria:Interiezioni in italiano", "registro": "comune"},
    {"id": "wikt-locuzioni-verbali", "url": "https://it.wiktionary.org/wiki/Categoria:Locuzioni_verbali_in_italiano",
     "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)", "tipo": "wiktionary",
     "categoria": "Categoria:Locuzioni verbali in italiano", "registro": "comune"},
    {"id": "wikt-locuzioni-aggettivali", "url": "https://it.wiktionary.org/wiki/Categoria:Locuzioni_aggettivali_in_italiano",
     "licenza": "CC BY-SA 4.0 (it.wiktionary, attribuzione)", "tipo": "wiktionary",
     "categoria": "Categoria:Locuzioni aggettivali in italiano", "registro": "comune"},
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


def api_wiktionary(params):
    """Una chiamata all'API di it.wiktionary, con pausa per non farsi limitare."""
    params = dict(params, format="json", formatversion="2")
    url = "https://it.wiktionary.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "lessico-chatai/1.0 (raccolta lemmi)"})
    for tentativo in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                time.sleep(0.6)
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (tentativo + 1))
                continue
            raise
    return {}


def definizione_italiana(wikitext, termine=""):
    """Prima riga di definizione della sezione italiana, e registro dal template."""
    wikitext = wikitext.replace("{{Pn}}", termine).replace("{{pn}}", termine)
    sezione = re.split(r"==\s*[^=]+\s*==", wikitext)
    italiana = ""
    for blocco in sezione[1:]:
        if re.match(r"\s*Italiano", sezione[0] if False else ""):
            pass
    # più semplice: cerco la sezione == Italiano == e mi fermo alla successiva
    m = re.search(r"==\s*(?:\{\{-it-\}\}|Italiano)\s*==(.*?)(?:\n==[^=]|$)", wikitext, re.S)
    if m:
        italiana = m.group(1)
    if not italiana:
        return "", ""
    registro = ""
    if re.search(r"\{\{(volgare|volgarismo)|\{\{Term\|volgare", italiana, re.I):
        registro = "volgare"
    elif re.search(r"\{\{(colloquiale|gergale|familiare)|\{\{Term\|(gergale|colloquiale|familiare)", italiana, re.I):
        registro = "colloquiale"
    righe = [r for r in italiana.splitlines() if r.startswith("#") and not r.startswith("#:")]
    if not righe:
        return "", registro
    testi_esempio = [r[2:].strip() for r in italiana.splitlines() if r.startswith("#*")]
    testo = re.sub(r"\{\{[^}]*\}\}", "", righe[0])
    testo = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", testo)
    testo = re.sub(r"\[\[([^\]]*)\]\]", r"\1", testo)
    testo = re.sub(r"<[^>]+>", "", testo).strip("# :,")
    testo = re.sub(r"^[,;]\s*", "", testo)
    if testi_esempio:
        esempio = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", testi_esempio[0])
        esempio = re.sub(r"\[\[([^\]]*)\]\]", r"\1", esempio)
        esempio = re.sub(r"'{2,3}", "", esempio)
        esempio = re.sub(r"\{\{[^}]*\}\}", "", esempio).strip()
        return testo[:120] + (" ~~ " + esempio[:160] if esempio else ""), registro
    return testo[:120], registro


def da_wiktionary(categoria):
    """Lemmi della categoria + prima definizione, via API MediaWiki."""
    fuori = []
    continua = None
    while True:
        params = {"action": "query", "list": "categorymembers", "cmtitle": categoria,
                  "cmlimit": "500", "cmnamespace": "0"}
        if continua:
            params["cmcontinue"] = continua
        d = api_wiktionary(params)
        membri = d.get("query", {}).get("categorymembers", [])
        titoli = [m["title"] for m in membri]
        for i in range(0, len(titoli), 40):
            gruppo = titoli[i:i + 40]
            dd = api_wiktionary({"action": "query", "prop": "revisions", "rvslots": "main",
                                 "rvprop": "content", "titles": "|".join(gruppo)})
            for pagina in dd.get("query", {}).get("pages", []):
                contenuto = (pagina.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")
                if not contenuto:
                    continue
                senso, registro = definizione_italiana(contenuto, pagina.get("title", ""))
                fuori.append((pagina.get("title", ""), registro, senso))
        continua = d.get("continue", {}).get("cmcontinue")
        if not continua:
            break
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
        if re.search(r"\d", p) or len(re.sub(r"[^a-zàèéìòù]", "", p)) < 4:
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
    ap.add_argument("--gruppo", choices=["erotico", "comune"], default="erotico",
                    help="erotico (volgare/sessuale) oppure comune (italiano normale)")
    args = ap.parse_args()

    fonti = FONTI if args.gruppo == "erotico" else FONTI_COMUNE
    suffisso = "" if args.gruppo == "erotico" else "-comune"
    USCITA = os.path.join(QUI, f"lessico-grezzo{suffisso}.json")
    SCARTI = os.path.join(QUI, f"lessico-scartati{suffisso}.txt")

    voci = {}
    scartati = []
    for fonte in fonti:
        if args.fonte and fonte["id"] not in args.fonte:
            continue
        print(f"→ {fonte['id']}: {fonte['url']}")
        testo = ""
        if fonte["tipo"] != "wiktionary":
            try:
                testo = scarica(fonte["url"])
            except Exception as e:
                print(f"  non raggiungibile: {e}")
                continue
        if fonte["tipo"] == "wiktionary":
            grezze = da_wiktionary(fonte["categoria"])
        else:
            grezze = {"righe": da_righe, "h2": da_h2, "term-title": da_term_title}[fonte["tipo"]](testo)
        print(f"  righe utili: {len(grezze)}")
        for testa, registro, senso in grezze:
            # forme flesse e voci vuote non servono in chat
            if not senso or re.match(r"^(plurale|femminile|maschile|participio|voce|"
                                     r"congiuntivo|indicativo|gerundio|comparativo)\b", senso, re.I):
                continue
            # roba da manuale, non da chat
            if re.search(r"(araldic|blason|attributo araldico|stemma|merlatur)", senso, re.I):
                continue
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

    conteggi = {}
    for v in voci.values():
        conteggi[v["fonte"]] = conteggi.get(v["fonte"], 0) + 1
    percorso_fonti = os.path.join(QUI, "fonti.md")
    if not os.path.exists(percorso_fonti):
        with open(percorso_fonti, "w", encoding="utf-8") as f:
            f.write("# Fonti del lessico\n\n| fonte | url | licenza | lemmi |\n|---|---|---|---|\n")
    with open(percorso_fonti, "a", encoding="utf-8") as f:
        for fonte in fonti:
            if args.fonte and fonte["id"] not in args.fonte:
                continue
            if fonte["id"] in conteggi:
                f.write(f"| {fonte['id']} | {fonte['url']} | {fonte['licenza']} | {conteggi[fonte['id']]} |\n")

    print(f"\nlemmi tenuti: {len(voci)} · scartati: {len(scartati)}")
    print(f"file: {USCITA}\n")
    for v in sorted(voci.values(), key=lambda v: v["termine"])[: args.mostra]:
        print(f"  {v['termine']:22} [{v['registro']}] {v['senso_fonte'][:60]}")


if __name__ == "__main__":
    main()
