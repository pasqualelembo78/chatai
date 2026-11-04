#!/usr/bin/env python3
"""Traduce in italiano i record inglesi dell'archivio, con il modello locale.

Non traduce se il record è già italiano. Salva in `<file>-it.jsonl`, riprende da dove si era
fermato, e tiene il testo inglese accanto per confronto (campo "inglese"): così una traduzione
sbagliata si può rifare o correggere senza perdere l'originale.

Uso: python3 archivio/traduci.py archivio/dati/warmroleplay-en.jsonl [--max 100]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/generate"
GOOGLE = "https://translate.googleapis.com/translate_a/single"
MODELLO = "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M"
ISTRUZIONI = ("Traduci in italiano colloquiale, naturale, mantenendo gli asterischi per le azioni "
              "e la stessa persona verbale. Rispondi SOLO con la traduzione, senza commenti.")
ITALIANE = ("il", "lo", "la", "che", "di", "un", "una", "per", "con", "non", "sono", "sei", "è")


def gia_italiano(testo):
    basso = " " + testo.lower() + " "
    return sum(1 for k in ITALIANE if f" {k} " in basso) >= 3


def traduci_google(testo):
    import urllib.parse
    parametri = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "it", "dt": "t",
                                        "q": testo[:4500]})
    richiesta = urllib.request.Request(GOOGLE + "?" + parametri,
                                       headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(richiesta, timeout=30) as r:
        dati = json.load(r)
    return "".join(parte[0] for parte in dati[0] if parte and parte[0]).strip()


def traduci_locale(testo):
    prompt = f"{ISTRUZIONI}\n\nEN: {testo[:600]}\nIT:"
    corpo = {"model": MODELLO, "prompt": prompt, "stream": False,
             "options": {"temperature": 0.2, "num_predict": 220}}
    richiesta = urllib.request.Request(OLLAMA, data=json.dumps(corpo).encode(),
                                       headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(richiesta, timeout=300) as r:
        uscita = json.load(r)["response"].strip()
    # pulizia: il modello a volte ripete "IT:" o mette virgolette
    uscita = re.sub(r"^IT:\s*", "", uscita).strip('"').strip()
    return uscita


def traduci(testo):
    """Prima il traduttore gratuito; se non risponde, il modello locale."""
    try:
        esito = traduci_google(testo)
        if len(esito.split()) >= max(1, len(testo.split()) // 3):
            return esito, "google"
    except Exception:
        pass
    return traduci_locale(testo), "locale 3B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()

    uscita = args.file.replace(".jsonl", "-it.jsonl")
    fatti = 0
    if os.path.exists(uscita):
        fatti = sum(1 for _ in open(uscita, encoding="utf-8"))
        print(f"riprendo da {fatti}")

    righe = [json.loads(x) for x in open(args.file, encoding="utf-8")][fatti:]
    with open(uscita, "a", encoding="utf-8") as f:
        for i, r in enumerate(righe[: args.max], 1):
            utente = r["messaggi"][0]["content"]
            risposta = r["messaggi"][-1]["content"]
            if gia_italiano(utente) and gia_italiano(risposta):
                tradotto = r
            else:
                t0 = time.time()
                try:
                    u_it, mu = traduci(utente) if not gia_italiano(utente) else (utente, "")
                    r_it, mr = traduci(risposta) if not gia_italiano(risposta) else (risposta, "")
                except Exception as e:
                    print(f"[{i}] errore: {e}", flush=True)
                    continue
                tradotto = {**r, "messaggi": [{"role": "user", "content": u_it},
                                              {"role": "assistant", "content": r_it}],
                            "inglese": {"utente": utente, "risposta": risposta},
                            "traduzione": mu or mr or "nessuna"}
                print(f"[{i}] {time.time()-t0:.1f}s", flush=True)
            tradotto["provenienza"] = r.get("provenienza", "") + " (tradotto it)"
            f.write(json.dumps(tradotto, ensure_ascii=False) + "\n")
            f.flush()
    print(f"fatto: {fatti + min(len(righe), args.max)} righe in {uscita}")


if __name__ == "__main__":
    main()
