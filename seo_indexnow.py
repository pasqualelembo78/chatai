#!/usr/bin/env python3
"""Segnala a IndexNow le pagine pubblicate (Bing, Yandex e chi lo adotta).

I backlink veri richiedono account e CAPTCHA, quindi non si possono postare da qui. Quello che
si può automatizzare è la **scoperta** delle pagine: IndexNow prende gli URL e li passa ai motori
in pochi secondi, senza account.

La chiave deve stare in un file di testo alla radice del sito, con dentro la chiave stessa.
Lo script lo crea se manca.

Uso:
    python3 seo_indexnow.py --tutte              # tutte le pagine delle sitemap
    python3 seo_indexnow.py --url https://pornovirtuale.com/stanza/lesbo/
    python3 seo_indexnow.py --prova              # mostra cosa invierebbe
"""
import argparse
import json
import os
import random
import re
import string
import urllib.request
from xml.etree import ElementTree

SITO = "https://pornovirtuale.com"
RADICE_WEB = "/var/www/pornovirtuale"
FILE_CHIAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "indexnow.key")
MOTORI = ["https://api.indexnow.org/indexnow"]


def chiave():
    if os.path.exists(FILE_CHIAVE):
        return open(FILE_CHIAVE).read().strip()
    nuova = "".join(random.choices(string.hexdigits.lower(), k=32))
    open(FILE_CHIAVE, "w").write(nuova)
    return nuova


def assicura_file_chiave(chiave_valore):
    percorso = os.path.join(RADICE_WEB, f"{chiave_valore}.txt")
    if not os.path.exists(percorso):
        open(percorso, "w").write(chiave_valore)
        os.chmod(percorso, 0o644)
        print(f"creato {percorso}")


def url_da_sitemap():
    fuori = []
    try:
        indice = urllib.request.urlopen(f"{SITO}/sitemap_index.xml", timeout=30).read()
        for loc in re.findall(rb"<loc>(.*?)</loc>", indice):
            sotto = loc.decode()
            if not sotto.endswith(".xml"):
                continue
            try:
                xml = urllib.request.urlopen(sotto, timeout=40).read()
                fuori += [u.decode() for u in re.findall(rb"<loc>(.*?)</loc>", xml)
                          if not u.decode().endswith(".xml")]
            except Exception as e:
                print(f"  sitemap non leggibile {sotto}: {e}")
    except Exception as e:
        print(f"sitemap index non leggibile: {e}")
    return list(dict.fromkeys(fuori))


def invia(chiave_valore, urls):
    corpo = {"host": "pornovirtuale.com", "key": chiave_valore,
             "keyLocation": f"{SITO}/{chiave_valore}.txt", "urlList": urls[:10000]}
    dati = json.dumps(corpo).encode()
    for motore in MOTORI:
        richiesta = urllib.request.Request(motore, data=dati,
                                           headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(richiesta, timeout=60) as r:
                print(f"{motore}: HTTP {r.status}")
        except Exception as e:
            print(f"{motore}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="append")
    ap.add_argument("--tutte", action="store_true")
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()

    chiave_valore = chiave()
    assicura_file_chiave(chiave_valore)

    urls = args.url or (url_da_sitemap() if args.tutte else [])
    if not urls:
        raise SystemExit("niente da inviare: usa --url oppure --tutte")

    urls = [u for u in urls if u.startswith(SITO)]
    print(f"URL da segnalare: {len(urls)}")
    for u in urls[:5]:
        print(f"  {u}")
    if args.prova:
        return
    invia(chiave_valore, urls)
    print("fatto")


if __name__ == "__main__":
    main()
