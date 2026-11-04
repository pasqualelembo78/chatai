#!/usr/bin/env python3
"""Analizza il grafo dei link interni: pagine orfane (nessun link in entrata) e link esterni morti.

Uscita: `link_orfani.txt` (pagine senza link in entrata) e `link_esterni_morti.txt`.
Non modifica niente: serve a decidere cosa collegare.

Uso: python3 analizza_link.py [--esterni]
"""
import argparse
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SITO = "https://pornovirtuale.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121 Safari/537.36"}


def sitemap():
    urls = []
    try:
        indice = urllib.request.urlopen(urllib.request.Request(f"{SITO}/sitemap_index.xml",
                                                              headers=UA), timeout=30).read().decode()
        for sotto in re.findall(r"<loc>(.*?)</loc>", indice):
            if sotto.endswith(".xml"):
                xml = urllib.request.urlopen(urllib.request.Request(sotto, headers=UA),
                                             timeout=40).read().decode("utf-8", "replace")
                urls += [u for u in re.findall(r"<loc>(.*?)</loc>", xml) if not u.endswith(".xml")]
    except Exception as e:
        print("sitemap:", e)
    return list(dict.fromkeys(urls))


def leggi(url, esterni):
    try:
        html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        html = html.decode("utf-8", "replace")
    except Exception:
        return set(), set()
    interni, fuori = set(), set()
    for l in re.findall(r'href="([^"#]+)', html):
        if l.startswith(("mailto:", "tel:", "javascript:")):
            continue
        a = urllib.parse.urljoin(url, l).split("#")[0]
        host = urllib.parse.urlparse(a).netloc.replace("www.", "")
        if "pornovirtuale.com" in host:
            interni.add(a.rstrip("/"))
        elif esterni:
            fuori.add(a)
    return interni, fuori


def stato(url):
    for m in ("HEAD", "GET"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method=m, headers=UA),
                                        timeout=15) as r:
                return url, r.status
        except urllib.error.HTTPError as e:
            return url, e.code
        except Exception:
            continue
    return url, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esterni", action="store_true")
    args = ap.parse_args()

    pagine = [p.rstrip("/") for p in sitemap()]
    print(f"pagine: {len(pagine)}")
    entrate, uscite, esterni = {p: set() for p in pagine}, {p: set() for p in pagine}, set()

    with ThreadPoolExecutor(max_workers=4) as pool:
        for sorgente, (interni, fuori) in zip(pagine, pool.map(lambda u: leggi(u, args.esterni), pagine)):
            uscite[sorgente] = interni
            esterni |= fuori
            for dest in interni:
                entrate.setdefault(dest, set()).add(sorgente)

    orfane = [p for p in pagine if not entrate.get(p)]
    with open("link_orfani.txt", "w", encoding="utf-8") as f:
        for p in orfane:
            f.write(p + "\n")
    print(f"pagine senza link in entrata: {len(orfane)}")

    if args.esterni:
        print(f"link esterni distinti: {len(esterni)}")
        with ThreadPoolExecutor(max_workers=8) as pool:
            morti = [(u, c) for u, c in pool.map(stato, sorted(esterni)) if c in (404, 410, 0, 500)]
        with open("link_esterni_morti.txt", "w", encoding="utf-8") as f:
            for u, c in morti:
                f.write(f"{c}\t{u}\n")
        print(f"link esterni morti: {len(morti)}")


if __name__ == "__main__":
    main()
