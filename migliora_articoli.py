#!/usr/bin/env python3
"""Migliora gli articoli già scritti: link alle stanze e una fonte esterna.

Non riscrive il testo. Aggiunge solo:
  - due link interni a stanze pertinenti, se mancano
  - un riferimento esterno autorevole (nofollow automatico dal mu-plugin), scelto per argomento
e porta la lunghezza più vicino alla soglia minima utile.

Uso:
    python3 migliora_articoli.py --prova
    python3 migliora_articoli.py
"""
import argparse
import re
import subprocess
import sys

WP = ["wp", "--allow-root", "--path=/var/www/pornovirtuale"]

FONTI = [
    (r"(chatbot|assistente|intelligenza artificiale|modello)", "Chatterbot",
     "https://it.wikipedia.org/wiki/Chatterbot"),
    (r"(diritto|copyright|personaggio esistente|nomi protetti)", "diritto d'autore",
     "https://it.wikipedia.org/wiki/Diritto_d%27autore"),
    (r"(bdsm|dominazione|sottomissione|bondage|corda)", "BDSM",
     "https://it.wikipedia.org/wiki/BDSM"),
    (r"(roleplay|gioco di ruolo|interpreta)", "gioco di ruolo",
     "https://it.wikipedia.org/wiki/Gioco_di_ruolo"),
    (r"(privacy|dati personali|gdpr)", "privacy",
     "https://www.garanteprivacy.it"),
    (r"(erotismo|erotico|sessualità|desiderio)", "erotismo",
     "https://it.wikipedia.org/wiki/Erotismo"),
]

STANZE = {
    r"(bdsm|corda|dominazione|sottomissione|comando|padrone)": ["bdsm", "dominazione"],
    r"(romantic|tenere|sentimenti|coppia stabile)": ["chat-romantica", "mature"],
    r"(esplicit|volgare|sporco|dirty)": ["dirty-talk", "senza-tabu"],
    r"(roleplay|scena|interpret)": ["roleplay-erotico", "fantasie-erotiche"],
    r"(prima volta|inesperienza|timidezza|iniziare)": ["camera-privata", "chat-romantica"],
    r"(fantasia|immaginare|sogno)": ["fantasie-erotiche", "fantasie-proibite"],
}
STANZE_DEFAULT = ["chat-romantica", "camera-privata"]
# ripieghi quando l'argomento non ha una fonte propria: si alternano per non ripetere
RIPIEGHI = [
    ("chat", "https://it.wikipedia.org/wiki/Chat_(informatica)"),
    ("comunicazione non verbale", "https://it.wikipedia.org/wiki/Comunicazione_non_verbale"),
    ("testo", "https://it.wikipedia.org/wiki/Testo"),
]


def wp(*args):
    return subprocess.run(WP + list(args), capture_output=True, text=True).stdout


def articoli():
    ids = []
    for stato in ("publish", "future"):
        ids += [r.split("\t")[0] for r in wp("post", "list", "--post_type=post",
                                             f"--post_status={stato}", "--format=csv",
                                             "--fields=ID").splitlines()[1:] if r.strip()]
    return ids


def stanze_per(testo):
    scelte = []
    for schema, stanze in STANZE.items():
        if re.search(schema, testo.lower()):
            scelte += stanze
    for s in STANZE_DEFAULT:
        if len(scelte) < 2:
            scelte.append(s)
    viste, fuori = set(), []
    for s in scelte:
        if s not in viste:
            viste.add(s)
            fuori.append(s)
    return fuori[:2]


def fonte_per(testo):
    for schema, nome, url in FONTI:
        if re.search(schema, testo.lower()):
            return nome, url
    indice = sum(ord(c) for c in testo) % len(RIPIEGHI)
    return RIPIEGHI[indice]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()

    cambiati = 0
    for pid in articoli():
        contenuto = wp("post", "get", pid, "--field=post_content")
        titolo = wp("post", "get", pid, "--field=post_title")
        nuovo = contenuto

        if len(re.findall(r"/stanza/", contenuto)) == 0:
            stanze = stanze_per(titolo + " " + contenuto)
            elenco = ", ".join(f'<a href="/stanza/{s}/">stanza {s.replace("-", " ")}</a>' for s in stanze)
            nuovo += f"\n<p><strong>Stanze collegate:</strong> {elenco}.</p>"

        if not re.search(r'href="https?://(?!pornovirtuale)', nuovo):
            nome, url = fonte_per(titolo + " " + contenuto)
            if url:
                nuovo += (f'\n<p>Per approfondire: <a href="{url}">{nome}</a>.</p>')

        if nuovo != contenuto:
            cambiati += 1
            if args.prova:
                print(f"{pid} {titolo[:50]} → +{len(nuovo) - len(contenuto)} caratteri")
            else:
                tmp = f"/tmp/art_{pid}.html"
                open(tmp, "w", encoding="utf-8").write(nuovo)
                wp("post", "update", pid, tmp)
    print(f"articoli modificati: {cambiati}")


if __name__ == "__main__":
    main()
