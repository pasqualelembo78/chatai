#!/usr/bin/env python3
"""Estrae dialoghi dai racconti erotici italiani pubblicati sul web.

Non esiste un dataset pubblico italiano di roleplay adulto: le fonti italiane sono racconti.
Qui si prendono SOLO le battute di dialogo (fra virgolette), accoppiate in ordine, e si tengono
quelle che sembrano uno scambio vero. La narrazione resta fuori.

Uso: python3 archivio/racconti.py --post 60 --pagine 5
Output: archivio/dati/racconti-it.jsonl (provenienza = URL del racconto)
"""
import argparse
import hashlib
import html as _html
import json
import os
import re
import time
import urllib.parse
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
API = "https://raccontimilu.com/wp-json/wp/v2/posts"
UA = {"User-Agent": "Mozilla/5.0 (raccolta dialoghi; chatai)"}


def testo_pulito(html):
    testo = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    testo = re.sub(r"<br\s*/?>|</p>", "\n", testo, flags=re.I)
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = _html.unescape(testo).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", testo)


def battute(testo):
    """Solo le frasi fra virgolette: italiane (« »), dritte o tipografiche."""
    trovate = re.findall(r"[«\"“]([^»\"”]{15,260})[»\"”]", testo)
    fuori = []
    for b in trovate:
        b = b.strip(" .,;:—-")
        if 4 <= len(b.split()) <= 40 and not re.match(r"^(cap|parte)\b", b, re.I):
            fuori.append(b)
    return fuori


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", type=int, default=40)
    ap.add_argument("--pagine", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(DATI, exist_ok=True)
    uscita = os.path.join(DATI, "racconti-it.jsonl")
    visti = set()
    if os.path.exists(uscita):
        visti = {hashlib.sha1(json.loads(r)["messaggi"][0]["content"].encode()).hexdigest()
                 for r in open(uscita, encoding="utf-8")}

    coppie = 0
    letti = 0
    with open(uscita, "a", encoding="utf-8") as f:
        for pagina in range(1, args.pagine + 1):
            url = API + "?" + urllib.parse.urlencode(
                {"per_page": str(args.post), "page": str(pagina), "_fields": "id,link,content"})
            try:
                risposta = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)
                post = json.load(risposta)
            except Exception as e:
                print(f"pagina {pagina}: {e}")
                break
            if not post:
                break
            for p in post:
                letti += 1
                testo = testo_pulito(p.get("content", {}).get("rendered", ""))
                pezzi = battute(testo)
                # a passi di due: ogni battuta fa da domanda una volta sola
                for a, b in zip(pezzi[0::2], pezzi[1::2]):
                    chiave = hashlib.sha1(a.encode()).hexdigest()
                    if chiave in visti:
                        continue
                    visti.add(chiave)
                    f.write(json.dumps({
                        "messaggi": [{"role": "user", "content": a},
                                     {"role": "assistant", "content": b}],
                        "provenienza": p.get("link", ""),
                        "licenza": "racconto pubblicato su raccontimilu.com (diritti degli autori)",
                        "registro": "esplicito", "esplicito": True,
                    }, ensure_ascii=False) + "\n")
                    coppie += 1
            f.flush()
            print(f"pagina {pagina}: racconti {letti}, coppie {coppie}", flush=True)
            time.sleep(0.6)
    print(f"fine: {coppie} coppie da {letti} racconti")


if __name__ == "__main__":
    main()
