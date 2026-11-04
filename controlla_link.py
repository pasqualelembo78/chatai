#!/usr/bin/env python3
"""Trova i link interni rotti (404) partendo dalle pagine delle sitemap.

Non tocca niente: produce `link_rotti.txt` con, per ogni link morto, le pagine che lo
contengono. Serve a sapere cosa correggere, e a non correggerlo due volte.

Uso:
    python3 controlla_link.py                 # solo link interni
    python3 controlla_link.py --esterni       # aggiunge i link esterni (più lento)
"""
import argparse
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SITO = "https://pornovirtuale.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121 Safari/537.36"}


def pagine():
    """URL delle pagine da controllare: sitemap + un campione di schede personaggio."""
    urls = []
    try:
        indice = urllib.request.urlopen(urllib.request.Request(
            f"{SITO}/sitemap_index.xml", headers=UA), timeout=30).read().decode("utf-8", "replace")
        for sotto in re.findall(r"<loc>(.*?)</loc>", indice):
            if not sotto.endswith(".xml"):
                continue
            try:
                xml = urllib.request.urlopen(urllib.request.Request(sotto, headers=UA),
                                             timeout=40).read().decode("utf-8", "replace")
                urls += [u for u in re.findall(r"<loc>(.*?)</loc>", xml) if not u.endswith(".xml")]
            except Exception:
                pass
    except Exception as e:
        print(f"sitemap non leggibile: {e}")
    return list(dict.fromkeys(urls))


def link_da(url, esterni=False):
    try:
        html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        html = html.decode("utf-8", "replace")
    except Exception:
        return url, [], []
    interni, fuori = set(), set()
    for grezzo in re.findall(r'href="([^"#]+)', html):
        if grezzo.startswith(("mailto:", "tel:", "javascript:")):
            continue
        assoluto = urllib.parse.urljoin(url, grezzo)
        host = urllib.parse.urlparse(assoluto).netloc.replace("www.", "")
        if "pornovirtuale.com" in host:
            interni.add(assoluto.split("#")[0])
        elif esterni:
            fuori.add(assoluto)
    return url, sorted(interni), sorted(fuori)


def codice(url):
    for metodo in ("HEAD", "GET"):
        try:
            richiesta = urllib.request.Request(url, method=metodo, headers=UA)
            with urllib.request.urlopen(richiesta, timeout=20) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            continue
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esterni", action="store_true")
    ap.add_argument("--max-pagine", type=int, default=400)
    args = ap.parse_args()

    da_controllare = pagine()
    print(f"pagine da leggere: {len(da_controllare)}")
    origini = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for url, interni, fuori in pool.map(lambda u: link_da(u, args.esterni), da_controllare):
            for l in interni + fuori:
                origini.setdefault(l, set()).add(url)

    tutti = sorted(origini)
    print(f"link distinti da verificare: {len(tutti)}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        esiti = list(pool.map(lambda u: (u, codice(u)), tutti))

    rotti = [(u, c) for u, c in esiti if c in (404, 410, 0)]
    with open("link_rotti.txt", "w", encoding="utf-8") as f:
        for u, c in sorted(rotti, key=lambda x: x[0]):
            f.write(f"{c}\t{u}\n")
            for o in sorted(origini[u])[:5]:
                f.write(f"\t   su {o}\n")
    print(f"link rotti: {len(rotti)} → link_rotti.txt")

    per_tipo = {}
    for u, c in rotti:
        chiave = "/" + (u.split("/")[3] if len(u.split("/")) > 3 else "")
        per_tipo[chiave] = per_tipo.get(chiave, 0) + 1
    for k, v in sorted(per_tipo.items(), key=lambda x: -x[1])[:10]:
        print(f"  {v:4} {k}")


if __name__ == "__main__":
    main()
