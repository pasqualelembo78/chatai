#!/usr/bin/env python3
"""Importa, qualifica e indicizza un archivio conversazionale italiano per il recupero.

Tre fasi, richiamabili separatamente:
    python3 archivio/strumenti.py importa     # scarica a blocchi (nessun dataset installato)
    python3 archivio/strumenti.py qualifica    # filtra e classifica
    python3 archivio/strumenti.py indice       # costruisce l'indice di ricerca
    python3 archivio/strumenti.py stato

Non modifica modelli né pesi: produce solo file in archivio/. Usa l'API pubblica
datasets-server, quindi non serve huggingface_hub e non si scaricano archivi interi.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
DB = os.path.join(QUI, "archivio.db")
UA = {"User-Agent": "chatai-archivio/1.0"}

# Fonti verificate una per una con l'API di Hugging Face.
FONTI = [
    {"id": "warmroleplay-en", "dataset": "minas2025/WarmRoleplay", "formato": "messages",
     "licenza": "aggregato, licenza per riga (campo license)", "collezione": "generale",
     "max": 600, "inglese": True},
    {"id": "roleplay-npc-en", "dataset": "chimbiwide/RolePlay-NPCv2", "formato": "messages",
     "licenza": "Apache 2.0 (dichiarata aggregando fonti terze)", "collezione": "generale",
     "max": 400, "inglese": True},
    {"id": "nsfw-chat-it", "dataset": "Raphael172/NSFW_Multilanguage_Chat_Dataset",
     "formato": "io-it", "licenza": "Apache 2.0", "collezione": "erotico", "max": 6632,
     "locale": os.path.join(QUI, "grezzi", "nsfw-it.json")},
    {"id": "due-chiacchiere", "dataset": "DeepMount00/due-chiacchiere",
     "formato": "messages", "licenza": "dataset gated, condizioni accettate",
     "collezione": "generale", "max": 6000, "gated": True,
     "file": "ita_conversations_0001.jsonl"},
    {"id": "italian-conversations", "dataset": "DeepMount00/italian_conversations",
     "formato": "conversation", "licenza": "Creative Commons (dichiarata 'cc')",
     "collezione": "generale", "max": 6000},
    {"id": "sintetiche-casuali", "dataset": "MaxForce01/Syntetic_italian_Conversation",
     "formato": "io", "licenza": "Apache 2.0", "collezione": "generale", "max": 1000},
    {"id": "orvieto-42k", "dataset": "OysterCoreAI/Orvieto-42k", "formato": "messages",
     "licenza": "CC BY 4.0", "collezione": "generale", "max": 7000},
    {"id": "data-ai-conversation-ita", "dataset": "Mattimax/DATA-AI_Conversation_ITA",
     "formato": "qa", "licenza": "Apache 2.0", "collezione": "generale", "max": 6000},
    {"id": "openitaliandata", "dataset": "DeepMount00/OpenItalianData", "formato": "conversation",
     "licenza": "Apache 2.0 (derivato da WildChat)", "collezione": "generale", "max": 8000},
]

# Parlato/erotico che non si può usare senza diritti chiari: resta scritto, non importato.
ESCLUSE = [
    ("DeepMount00/due-chiacchiere", "gated: serve un token HF e l'accettazione delle condizioni"),
    ("SerFabio89/italian-open-sft-chat-dataset", "CC BY-NC 4.0: non commerciale, tenuto fuori "
     "finché il progetto è commerciale"),
    ("RBTL/Erotico", "solo audio (una riga, campo audio), niente testo"),
    ("AntonelloS01/Conversazioni", "licenza non dichiarata"),
    ("KIParla", "accesso su richiesta, licenza per singolo corpus: da verificare prima di importare"),
    ("PAISÀ / itWaC / CombiNet / Dodiom", "corpora grandi con licenze diverse per contenuto: "
     "valutazione separata, non importati ora"),
]

ESPLICITO = (
    "cazzo", "figa", "fica", "culo", "scopare", "scopata", "inculare", "sborra", "sborrare",
    "pompino", "bocchino", "sega", "ditalino", "tette", "palle", "coglioni", "verga", "pene",
    "vagina", "orgasmo", "eccitato", "eccitata", "nudo", "nuda", "erotico", "sessuale", "sesso",
    "linguaggio", "seno", "capezzoli", "masturbazione", "fellatio", "cunnilingus",
)
PRIVACY = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "email"),
    (re.compile(r"\+?\d[\d\s]{8,14}\d"), "telefono"),
    (re.compile(r"\bIT\d{2}[A-Z]\d{10}\b"), "iban"),
]
CATEGORIE = [
    ("domanda-servizio", r"^(che ore|che ora|che giorno|quanto|dove|come si|cosa significa|"
                         r"mi (spieghi|dici)|puoi spiegarmi)"),
    ("roleplay", r"(facciamo che|immagina|sei un|sei una|interpreta|roleplay|gioco di ruolo)"),
    ("erotico", r"(sesso|erotic|scopare|nudo|eccitat|sedu|flirt|intim)"),
    ("quotidiano", r"(ciao|buongiorno|come stai|grazie|scusa|oggi| lavoro|famiglia)"),
    ("spiegazione", r"(come funziona|perché|cos'è|definizione|differenza tra)"),
]


def scarica(dataset, config, split, offset, quanti):
    q = urllib.parse.urlencode({"dataset": dataset, "config": config, "split": split,
                                "offset": offset, "length": quanti})
    req = urllib.request.Request("https://datasets-server.huggingface.co/rows?" + q, headers=UA)
    for tentativo in range(7):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if tentativo == 6:
                raise
            time.sleep(25 if e.code == 429 else 5 * (tentativo + 1))
        except Exception:
            if tentativo == 6:
                raise
            time.sleep(3 * (tentativo + 1))
    return {}


def normalizza(fonte, riga, indice):
    """Da qualunque formato a un record unico. Restituisce None se inadatto."""
    messaggi = []
    if fonte["formato"] == "messages":
        for m in riga.get("messages") or []:
            if m.get("role") == "system":
                continue
            ruolo = "user" if m.get("role") == "user" else "assistant"
            testo = (m.get("content") or "").strip()
            if testo:
                messaggi.append({"role": ruolo, "content": testo})
    elif fonte["formato"] == "io-it":
        for ruolo, chiave in (("user", "input"), ("assistant", "output")):
            if riga.get(chiave):
                messaggi.append({"role": ruolo, "content": str(riga[chiave]).strip()})
    elif fonte["formato"] == "io":
        coppia = riga.get("train") or riga
        for ruolo, chiave in (("user", "Input"), ("assistant", "Output")):
            if coppia.get(chiave):
                messaggi.append({"role": ruolo, "content": str(coppia[chiave]).strip()})
    elif fonte["formato"] == "qa":
        p = (riga.get("train") or {}).get("prompt") if "train" in riga else riga.get("prompt")
        r = (riga.get("train") or {}).get("response") if "train" in riga else riga.get("response")
        for ruolo, testo in (("user", p), ("assistant", r)):
            if testo:
                messaggi.append({"role": ruolo, "content": str(testo).strip()})
    else:
        for m in riga.get("conversation") or []:
            ruolo = "user" if m.get("role") == "user" else "assistant"
            testo = (m.get("content") or "").strip()
            if testo:
                messaggi.append({"role": ruolo, "content": testo})

    if len(messaggi) < 2 or messaggi[0]["role"] != "user" or messaggi[-1]["role"] != "assistant":
        return None

    utente = messaggi[0]["content"]
    risposta = messaggi[-1]["content"]
    if not utente or not risposta:
        return None
    if len(risposta.split()) < 4 or len(risposta) > 1400:
        return None
    if len(utente) > 900:
        return None
    if len(risposta.split()) > 200:
        return None

    testo_totale = (utente + " " + risposta).lower()
    esplicito = any(k in testo_totale for k in ESPLICITO)
    categoria = "altro"
    for nome, rx in CATEGORIE:
        if re.search(rx, utente.lower()):
            categoria = nome
            break

    return {
        "id": f"{fonte['id']}-{indice}",
        "provenienza": fonte["dataset"],
        "licenza": fonte["licenza"],
        "collezione": "erotico" if esplicito else fonte["collezione"],
        "messaggi": messaggi[:8],
        "cronologia": len(messaggi) > 2,
        "categoria": categoria,
        "sottocategoria": "",
        "registro": "colloquiale",
        "esplicito": esplicito,
        "intenzione": "domanda" if utente.strip().endswith("?") else "affermazione",
        "contesto": "",
        "originale": True,
        "qualita": {},
    }


def _token():
    try:
        return open("/root/.hf_token").read().strip()
    except Exception:
        return ""


def righe_da_file(dataset, nome_file):
    """Legge un jsonl direttamente dal repo (serve per i dataset gated)."""
    url = f"https://huggingface.co/datasets/{dataset}/resolve/main/{nome_file}"
    req = urllib.request.Request(url, headers={**UA, "Authorization": "Bearer " + _token()})
    with urllib.request.urlopen(req, timeout=120) as r:
        for riga in r:
            riga = riga.decode("utf-8", "replace").strip()
            if riga:
                try:
                    yield json.loads(riga)
                except Exception:
                    continue


def fase_importa(solo=None, max_totale=None):
    os.makedirs(DATI, exist_ok=True)
    visti = set()
    totale = 0
    for fonte in FONTI:
        if solo and fonte["id"] not in solo:
            continue
        percorso = os.path.join(DATI, f"{fonte['id']}.jsonl")
        # ripresa: se il file esiste si continua da dove si era fermato
        fatti = 0
        offset = 0
        if os.path.exists(percorso):
            fatti = sum(1 for _ in open(percorso, encoding="utf-8"))
            offset = fatti
        print(f"→ {fonte['id']} ({fonte['licenza']}), max {fonte['max']}")
        if fonte.get("locale"):
            with open(percorso, "a" if fatti else "w", encoding="utf-8") as f:
                for riga in json.load(open(fonte["locale"], encoding="utf-8")):
                    rec = normalizza(fonte, riga, fatti)
                    if not rec:
                        continue
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fatti += 1
            totale += fatti
            print(f"   totale {fonte['id']}: {fatti}")
            continue

        if fonte.get("file"):
            with open(percorso, "a" if fatti else "w", encoding="utf-8") as f:
                for i, riga in enumerate(righe_da_file(fonte["dataset"], fonte["file"])):
                    if fatti >= fonte["max"]:
                        break
                    rec = normalizza(fonte, riga, fatti)
                    if not rec:
                        continue
                    impronta = hashlib.sha1(
                        (rec["messaggi"][0]["content"] + rec["messaggi"][-1]["content"]).encode()
                    ).hexdigest()
                    if impronta in visti:
                        continue
                    visti.add(impronta)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fatti += 1
                    if fatti % 500 == 0:
                        print(f"   {fatti} record", flush=True)
            totale += fatti
            print(f"   totale {fonte['id']}: {fatti}")
            continue

        with open(percorso, "a" if fatti else "w", encoding="utf-8") as f:
            while fatti < fonte["max"]:
                blocco = scarica(fonte["dataset"], "default", "train", offset, 100)
                righe = blocco.get("rows") or []
                if not righe:
                    break
                for x in righe:
                    rec = normalizza(fonte, x["row"], fatti)
                    if not rec:
                        continue
                    impronta = hashlib.sha1(
                        (rec["messaggi"][0]["content"] + rec["messaggi"][-1]["content"]).encode()
                    ).hexdigest()
                    if impronta in visti:
                        continue
                    visti.add(impronta)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fatti += 1
                    if fatti >= fonte["max"]:
                        break
                offset += len(righe)
                print(f"   {fatti} record", flush=True)
                if max_totale and totale + fatti >= max_totale:
                    break
            totale += fatti
    print(f"\nimportati: {totale}")


FORTI = ("cazzo", "figa", "fica", "culo", "scopare", "scopata", "inculare", "sborra", "sborrare",
         "pompino", "bocchino", "ditalino", "tette", "coglioni", "verga", "pene", "vagina",
         "orgasmo", "eccitato", "eccitata", "masturb", "fellatio", "cunnilingus", "nuda", "nudo")


def esplicito_vero(testo):
    """Esplicito solo se c'è almeno un termine forte, o due deboli."""
    basso = testo.lower()
    if any(k in basso for k in FORTI):
        return True
    deboli = sum(1 for k in ("sesso", "sessuale", "erotico", "intimo", "desiderio", "sensuale",
                             "seduzione", "flirt") if k in basso)
    return deboli >= 2


def qualifica_record(rec):
    """Punteggio e motivi di scarto. Non si fida della grammatica."""
    testo = " ".join(m["content"] for m in rec["messaggi"])
    utente = rec["messaggi"][0]["content"]
    risposta = rec["messaggi"][-1]["content"]
    basso = testo.lower()
    qualita = {"parole": len(risposta.split())}

    for rx, nome in PRIVACY:
        if rx.search(testo):
            qualita[nome] = True
    if re.search(r"https?://", basso) and len(risposta.split()) < 15:
        qualita["link"] = True
    # tracce di template o di codice
    if re.search(r"(\{|\}|</?\w+>|\bnull\b|\bundefined\b)", basso):
        qualita["markup"] = True
    # risposta che ripete la domanda
    if risposta.strip().lower().startswith(utente.strip().lower()[:25]) and len(utente) > 15:
        qualita["ripete-domanda"] = True
    # domanda senza risposta: risposta che è un'altra domanda
    if risposta.strip().endswith("?") and len(risposta.split()) < 8 and not rec["esplicito"]:
        qualita["solo-domanda"] = True
    # emoji eccessive (tipiche delle risposte svuotate)
    if len(re.findall(r"[\U0001F300-\U0001FAFF]", risposta)) >= 3:
        qualita["emoji"] = True
    # non-italiano probabile
    if not re.search(r"\b(il|la|di|che|un|una|per|con|non|è)\b", basso):
        qualita["forse-non-italiano"] = True

    rec["esplicito"] = esplicito_vero(testo)
    rec["collezione"] = "erotico" if rec["esplicito"] else "generale"
    # quanto somiglia a una chat e non a un compito
    stile = 0
    if 8 <= len(risposta.split()) <= 70 and not re.search(r"[•\n*-]\s", risposta):
        stile += 2
    if re.search(r"\b(sono|mi|ti|ho|hai|siamo|stai)\b", risposta.lower()):
        stile += 1
    if re.search(r"(contesto:|genera|trasforma|riscrivi|elenca|traduci)", utente.lower()):
        stile -= 2
    if re.search(r"^(ecco|certamente|certo!|va bene, ecco)", risposta.lower()):
        stile -= 1
    rec["stile"] = stile
    rec["qualita"] = qualita
    rec["utile"] = not any(k in qualita for k in
                           ("email", "telefono", "iban", "markup", "ripete-domanda",
                            "solo-domanda", "forse-non-italiano"))
    # registro (prima si decide l'esplicito, poi il registro)
    rec["esplicito"] = esplicito_vero(testo)
    rec["collezione"] = "erotico" if rec["esplicito"] else "generale"
    if re.search(r"\b(cazzo|figa|fica|culo|scopare|inculare|sborra)\b", basso):
        rec["registro"] = "volgare"
    elif rec["esplicito"]:
        rec["registro"] = "esplicito"
    elif re.search(r"\b(ciao|dai|boh|guarda|senti)\b", basso):
        rec["registro"] = "colloquiale"
    return rec


def fase_qualifica():
    tenuti, scartati = 0, 0
    for nome in sorted(os.listdir(DATI)):
        if not nome.endswith(".jsonl") or nome.endswith(".qual.jsonl"):
            continue
        percorso = os.path.join(DATI, nome)
        uscita = os.path.join(DATI, nome.replace(".jsonl", ".qual.jsonl"))
        with open(percorso, encoding="utf-8") as f, open(uscita, "w", encoding="utf-8") as o:
            for riga in f:
                try:
                    rec = qualifica_record(json.loads(riga))
                except Exception:
                    scartati += 1
                    continue
                if rec["utile"]:
                    o.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    tenuti += 1
                else:
                    scartati += 1
        print(f"   {nome}: tenuti {tenuti}, scartati {scartati}")
    print(f"\nqualificati: {tenuti} · scartati: {scartati}")


def fase_indice():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE frammenti (
        id TEXT PRIMARY KEY, provenienza TEXT, licenza TEXT, collezione TEXT,
        categoria TEXT, registro TEXT, esplicito INT, utente TEXT, risposta TEXT,
        cronologia TEXT, parole INT, stile INT)""")
    conn.execute("""CREATE VIRTUAL TABLE cerca USING fts5(
        utente, risposta, categoria, registro, content='frammenti', content_rowid='rowid')""")
    n = 0
    for nome in sorted(os.listdir(DATI)):
        if not nome.endswith(".qual.jsonl"):
            continue
        print(f"   indicizzo {nome}", flush=True)
        with open(os.path.join(DATI, nome), encoding="utf-8") as f:
            for riga in f:
                r = json.loads(riga)
                conn.execute("INSERT OR IGNORE INTO frammenti VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (r["id"], r["provenienza"], r["licenza"], r["collezione"],
                              r["categoria"], r["registro"], int(r["esplicito"]),
                              r["messaggi"][0]["content"], r["messaggi"][-1]["content"],
                              json.dumps(r["messaggi"][:-1], ensure_ascii=False),
                              len(r["messaggi"][-1]["content"].split()), r.get("stile", 0)))
                n += 1
    conn.commit()
    conn.execute("INSERT INTO cerca(cerca) VALUES('rebuild')")
    conn.commit()
    conn.close()
    print(f"indice costruito con {n} frammenti in {DB}")


def stato():
    if not os.path.exists(DB):
        print("archivio non ancora costruito")
        return
    conn = sqlite3.connect(DB)
    for riga in conn.execute("SELECT collezione, registro, COUNT(*) FROM frammenti "
                             "GROUP BY collezione, registro ORDER BY 3 DESC"):
        print("  ", riga)
    print("   totale:", conn.execute("SELECT COUNT(*) FROM frammenti").fetchone()[0])
    print("   dimensione db:", round(os.path.getsize(DB) / 1048576, 1), "MB")
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fase", choices=["importa", "qualifica", "indice", "stato"])
    ap.add_argument("--solo", action="append")
    ap.add_argument("--max", type=int)
    args = ap.parse_args()
    {"importa": lambda: fase_importa(args.solo, args.max),
     "qualifica": fase_qualifica, "indice": fase_indice, "stato": stato}[args.fase]()


if __name__ == "__main__":
    main()
