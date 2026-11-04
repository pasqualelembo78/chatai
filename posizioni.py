#!/usr/bin/env python3
"""Controlla su che posizione compare il sito per alcune query (motore: Bing).

Google serve oggi una pagina solo JavaScript a chi non ha i cookie: da terminale non si legge.
Bing risponde in HTML e usa IndexNow, che abbiamo già attivo, quindi è anche il motore su cui
possiamo avere un effetto reale. Per Google servono i dati di Search Console.

Uso:
    python3 posizioni.py                 # query predefinite
    python3 posizioni.py --query "..."   # una query
    python3 posizioni.py --indicizzate   # quante pagine risultano indicizzate
"""
import argparse
import re
import urllib.parse
import urllib.request

DOMINIO = "pornovirtuale.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36",
      "Accept-Language": "it-IT,it;q=0.9"}

QUERY = ["pornovirtuale", "chat erotiche", "chat erotiche in italiano", "chat con personaggi",
         "chat erotiche gratis", "chat adulti in italiano"]


def risultati(query, quanti=30):
    """URL dei risultati, in ordine di posizione."""
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "count": quanti,
                                                                  "setlang": "it"})
    html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode(
        "utf-8", "replace")
    urls = re.findall(r'<h2><a[^>]+href="(https?://[^"]+)"', html)
    puliti = []
    for u in urls:
        host = urllib.parse.urlparse(u).netloc.replace("www.", "")
        if "bing.com" in host or "microsoft" in host:
            continue
        puliti.append(host + urllib.parse.urlparse(u).path)
    return puliti


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", action="append")
    ap.add_argument("--indicizzate", action="store_true")
    args = ap.parse_args()

    if args.indicizzate:
        html = urllib.request.urlopen(urllib.request.Request(
            "https://www.bing.com/search?" + urllib.parse.urlencode({"q": f"site:{DOMINIO}"}),
            headers=UA), timeout=30).read().decode("utf-8", "replace")
        m = re.search(r"([\d.,]+)\s+risultati", html)
        print(f"pagine indicizzate dichiarate da Bing: {m.group(1) if m else 'non dichiarato'}")
        return

    for query in (args.query or QUERY):
        try:
            esiti = risultati(query)
        except Exception as e:
            print(f"{query:32} errore: {str(e)[:50]}")
            continue
        posizione = next((i for i, u in enumerate(esiti, 1) if DOMINIO in u), None)
        print(f"{query:32} " + (f"posizione {posizione}" if posizione else "non nei primi 30"))
        for i, u in enumerate(esiti[:3], 1):
            print(f"   {i}. {u[:70]}")


if __name__ == "__main__":
    main()
