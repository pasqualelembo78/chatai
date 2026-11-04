# -*- coding: utf-8 -*-
"""Supporto linguistico contestuale per le chat.

Il repertorio vive in JSON separati (cartella `language/`). A ogni messaggio se ne
pescano pochi elementi pertinenti al contesto, evitando quelli già usati negli
ultimi scambi: pochi token, nessuna lista da ripetere, niente seconde chiamate.

Uso tipico (prompt_builder):
    from language import blocco_prompt
    blocco = blocco_prompt(categoria, testo_utente, storia, user_id, character_id, turno)
"""

import hashlib
import json
import re
import os
import threading
from collections import deque

_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCK = threading.Lock()
_CACHE = {}
_USATI = {}
_MAX_USATI = 30

_INDICE = None


def _carica(nome):
    """Carica un file del repertorio una volta sola (cache in memoria)."""
    if nome in _CACHE:
        return _CACHE[nome]
    percorso = os.path.join(_DIR, nome)
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
    except Exception:
        dati = {}
    _CACHE[nome] = dati
    return dati


def _indice():
    global _INDICE
    if _INDICE is None:
        _INDICE = _carica("index.json") or {}
    return _INDICE


def _normalizza(testo):
    return " " + str(testo or "").lower() + " "


def _file_pertinenti(testo, turno):
    """Sceglie i file in base al contesto: pochi e pertinenti, mai tutti."""
    indice = _indice()
    reg = indice.get("registri", {})
    scelti = []

    # grammatica sempre (è la parte che corregge gli errori ricorrenti)
    scelti.append("italian-grammar.json")
    if turno <= 1:
        scelti += reg.get("inizio", [])
    t = _normalizza(testo)
    for voce in indice.get("files", []):
        for aggancio in voce.get("agganci", []):
            if aggancio in t and voce["file"] not in scelti:
                scelti.append(voce["file"])
                break
    for f in reg.get("sesso", []):
        if any(k in t for k in ("scop", "cazzo", "figa", "culo", "sesso", "sborr", "incul", "sega", "venire", "bocca")):
            if f not in scelti:
                scelti.append(f)
            break
    for f in reg.get("leggero", []):
        if any(k in t for k in ("ahah", "rido", "battuta", "scherz", "ironi")):
            if f not in scelti:
                scelti.append(f)
            break
    # al massimo quattro file: oltre, il blocco diventa peso
    return scelti[:4]


def _voci(file_name):
    """Estrae le stringhe utili da un file, qualunque sia la sua forma."""
    dati = _carica(file_name)
    out = []

    if file_name == "italian-grammar.json":
        out.append("parole italiane reali, mai inventate")
        for c in dati.get("correzioni_brevi", [])[:3]:
            out.append(f"non '{c['sbagliato']}' ma '{c['giusto']}'")
        return out

    if file_name == "italian-verbs.json":
        for v in dati.get("voci", []):
            out.append(f"{v['verbo']}: {v['presente']}")
        return out

    if file_name == "italian-synonyms.json":
        for g in dati.get("gruppi", []):
            out.append(f"invece di '{g['base']}': {', '.join(g['varianti'][:3])}")
        return out

    if file_name == "italian-dialogues.json":
        for d in dati.get("dialoghi", []):
            out.append(d["registro"] + ": " + " / ".join(d["battute"][:3]))
        return out

    if file_name == "italian-syntax.json":
        out += dati.get("regole", [])[:2]
        for m in dati.get("modelli", [])[:4]:
            out.append(f"es. {m['frase']}")
        return out

    if file_name == "italian-humor.json":
        for m in dati.get("mosse", []):
            out.append(f"\"{m['esempio']}\"")
        return out

    if file_name == "italian-expressions.json":
        for e in dati.get("voci", []):
            out.append(f"\"{e['espressione']}\" ({e['significato']})")
        return out

    for v in dati.get("voci", []):
        etichetta = v.get("termine") or v.get("espressione") or ""
        if etichetta:
            out.append(etichetta)
    return out


def _chiave_uso(user_id, character_id):
    return f"{user_id}:{character_id}"


def _usati(user_id, character_id):
    with _LOCK:
        coda = _USATI.get(_chiave_uso(user_id, character_id))
        if coda is None:
            coda = deque(maxlen=_MAX_USATI)
            _USATI[_chiave_uso(user_id, character_id)] = coda
        return coda


def _scarta_usati(voci, gia):
    """Toglie le voci già usate: è il vero antiripetizione."""
    normalizzati = {_normalizza(g).strip() for g in gia}
    out = []
    for v in voci:
        chiave = _normalizza(v).split(":")[0].strip()
        if chiave and chiave not in normalizzati:
            out.append(v)
    return out or voci


def blocco_prompt(categoria, testo_utente, storia=None, user_id=0, character_id="", turno=0):
    """Blocco compatto di supporto linguistico, o stringa vuota."""
    file_scelti = _file_pertinenti(testo_utente, turno)
    if not file_scelti:
        return ""

    gia = [m.get("content", "") for m in (storia or [])[-6:] if m.get("role") == "assistant"]
    mem = _usati(user_id, character_id)
    gia = list(gia) + list(mem)

    semi = int(hashlib.md5(f"{user_id}:{character_id}:{turno}:{(testo_utente or '')[:40]}".encode()).hexdigest()[:8], 16)
    pezzi = []
    for f in file_scelti:
        voci = _scarta_usati(_voci(f), gia)
        if not voci:
            continue
        scelta = voci[semi % len(voci)]
        pezzi.append(scelta)
        with _LOCK:
            mem.append(scelta.split(":")[-1][:40])

    if not pezzi:
        return ""

    blocco = "RIFERIMENTI (usali se servono, non elencarli): " + " · ".join(pezzi[:4])
    return blocco[:230]


_BIANCA = None


def _bianca():
    """Parole ammesse anche se il dizionario non le conosce: gergo e nomi."""
    global _BIANCA
    if _BIANCA is not None:
        return _BIANCA
    base = {
        "cazzo", "figa", "fica", "figo", "fico", "sborra", "sborro", "sborrare", "sborrata",
        "inculo", "incolo", "inculare", "inculato", "sego", "segare", "segata", "sega", "seghe",
        "scopo", "scopare", "scopata", "chiavo", "chiavare", "chiavata", "pompino", "pompini",
        "ciuccio", "ciucciare", "lecco", "leccare", "leccata", "topa", "passera", "mazzo",
        "tette", "poppe", "succhio", "succhiare", "orgasmo", "orgasmi", "preliminari",
        "sfizio", "ghirba", "sballare", "figata", "boh", "dai", "ok", "okay",
    }
    for f in ("italian-anatomy.json", "italian-erotic.json", "italian-colloquial.json",
              "italian-syntax.json", "italian-expressions.json", "italian-humor.json"):
        for campo in ("voci", "modelli", "mosse"):
            for voce in (_carica(f).get(campo) or []):
                for chiave in ("termine", "espressione", "frase", "esempio", "nota"):
                    for parola in str(voce.get(chiave, "")).lower().replace(",", " ").split():
                        pulita = "".join(c for c in parola if c.isalpha() or c == "'")
                        if pulita:
                            base.add(pulita)
    _BIANCA = base
    return base


def parole_sconosciute(testo, limite=6, maiuscole=False):
    """Parole che il dizionario italiano non riconosce (per log e revisione)."""
    if not testo:
        return []
    try:
        import subprocess
        esito = subprocess.run(
            ["hunspell", "-d", "it_IT", "-l"], input=testo.encode("utf-8"),
            capture_output=True, timeout=4,
        )
    except Exception:
        return []
    bianca = _bianca()
    fuori = []
    for riga in esito.stdout.decode("utf-8", "ignore").splitlines():
        parola = riga.strip()
        if len(parola) < 4 or parola.lower() in bianca:
            continue
        if parola[0].isupper() and not maiuscole:
            continue
            continue
        fuori.append(parola)
    return fuori[:limite]


def esempi_stile(categoria, seed=0, quanti=2, esclusi=()):
    """Due battute di esempio nella categoria: il modello imita ritmo e registro."""
    dati = _carica("italian-style.json").get("stili", {})
    voci = [v for v in dati.get(categoria, []) if v not in esclusi]
    if not voci:
        return []
    inizio = seed % len(voci)
    return [voci[(inizio + i) % len(voci)] for i in range(min(quanti, len(voci)))]


def correggi(testo):
    """Corregge le forme sbagliate già osservate, senza toccare altro."""
    if not testo:
        return testo
    originale = testo
    dati = _carica("italian-grammar.json")
    for c in dati.get("correzioni_brevi", []):
        sbagliato, giusto = c.get("sbagliato"), c.get("giusto")
        # giusto può essere vuoto: significa "togli questa forma"
        if not sbagliato or giusto is None:
            continue
        dopo = c.get("tranne_dopo")
        # confronto senza distinzione fra maiuscole e minuscole, e la maiuscola
        # iniziale si conserva ("Ti bacchio" -> "Ti bacio")
        def _sost(m, g=giusto):
            return g[:1].upper() + g[1:] if m.group(0)[:1].isupper() and g else g
        if dopo:
            testo = re.sub(re.escape(sbagliato) + r"(?!" + re.escape(dopo) + ")",
                           _sost, testo, flags=re.IGNORECASE)
        else:
            testo = re.sub(re.escape(sbagliato), _sost, testo, flags=re.IGNORECASE)

    # frasi fatte da buttare. Le prime tre per regex: il modello le varia
    # ("questa conversazione", "Mi scuso, ma…") e la lista secca non le prendeva.
    testo = re.sub(r"(?i)\b(?:mi scuso|mi dispiace)?[,\s]*(?:ma\s+)?non posso continuare "
                   r"(?:con )?(?:la|questa) conversazione(?: in questo modo)?\s*[.!]?\s*", "", testo)
    testo = re.sub(r"(?i)c'?[eè] qualcos'?altro in cui posso aiutarti\??\s*", "", testo)
    testo = re.sub(r"(?i)cosa posso fare per te\??\s*", "", testo)
    testo = re.sub(r"(?i)posso aiutarti a iniziare una nuova conversazione\s*[.!]?\s*", "", testo)
    testo = re.sub(r"(?i)\b(?:inizia di nuovo|ricominciamo(?: da capo)?)\s*[.!]?\s*", "", testo)

    # frasi fatte da buttare (l'utente le trova inutili)
    for frase in sorted(dati.get("frasi_da_togliere", []), key=len, reverse=True):
        testo = testo.replace(frase, "")
    testo = re.sub(r"\s{2,}", " ", testo).strip()
    testo = re.sub(r"^[,\s]*(ma|e|quindi)[,\s]+", "", testo, flags=re.IGNORECASE)

    # "una" davanti a vocale prende l'apostrofo ("una atmosfera" -> "un'atmosfera")
    testo = re.sub(r"\buna ([aeiouàèéìòù])", r"un'\1", testo, flags=re.IGNORECASE)

    # varietà: le aperture e i "negli occhi" del modello sono sempre le stesse
    _seme = sum(ord(c) for c in testo)
    if testo.lower().startswith("mi avvicino a te"):
        _alt = ("Ti arrivo vicino", "Mi sposto verso di te", "Vengo addosso", "Ti sono addosso")
        testo = _alt[_seme % len(_alt)] + testo[len("mi avvicino a te"):]
    if "negli occhi" in testo.lower() and _seme % 3:
        _alt = ("in faccia", "bene")
        testo = re.sub(r"negli occhi", _alt[_seme % len(_alt)], testo, count=1, flags=re.IGNORECASE)

    # "la tua fronte, la tua fronte che si abbassa" -> "la tua fronte che si abbassa"
    testo = re.sub(
        r"\b((?:il|lo|la|le|gli|i|un|una|il tuo|la tua|i tuoi|le tue|il mio|la mia|i miei|le mie)"
        r"(?:\s+[\wàèéìòù']+){0,3}),\s*\1\s+che\b",
        r"\1 che", testo, flags=re.IGNORECASE)

    # clausola identica ripetuta con " e " ("ti avvicinassi a me e ti avvicinassi a me")
    testo = re.sub(r"\b((?:[\wàèéìòù']+\s+){2,6}[\wàèéìòù']+) e \1\b", r"\1", testo, flags=re.IGNORECASE)

    # clausola identica ripetuta ("la tua fronte che si abbassa, la tua fronte che si abbassa")
    testo = re.sub(r"\b((?:[\wàèéìòù']+\s+){2,7}[\wàèéìòù']+),\s*\1\b", r"\1", testo, flags=re.IGNORECASE)

    # orario con la virgola al posto dei due punti ("14,30")
    testo = re.sub(r"\b([01]?\d|2[0-3])[,.](\d{2})\b(?![\d])", r"\1:\2", testo)

    # asterischi di enfasi (*ti guarda*): il modello li alterna al parlato
    testo = re.sub(r"\*([^*]+)\*", r"\1", testo)
    testo = testo.replace("*", "")

    # punteggiatura doppia o orfana ("!.", "?.", " .")
    testo = re.sub(r"([!?])\s*\.", r"\1", testo)
    testo = re.sub(r"([\wàèéìòù])\.\s*([!?])", r"\1\2", testo)
    testo = re.sub(r"\.\s*\.", ".", testo)
    testo = re.sub(r"\s+([,.;:!?])", r"\1", testo)
    testo = re.sub(r"(?<=[.!?])\s+(?!$)", " ", testo).strip()
    testo = re.sub(r"^(\s*[!?.,;:])", "", testo).strip()
    # niente spazio prima della punteggiatura ("faccia , ")
    testo = re.sub(r"\s+([,.;:!?])", r"\1", testo)
    testo = re.sub(r"\.{2,}", ".", testo)

    # se il taglio ha lasciato un attacco orfano ("o a risolvere...") o minuscolo
    testo = re.sub(r"^(?:o|e|ma|quindi)\s+", "", testo)
    if testo[:1].islower():
        testo = testo[:1].upper() + testo[1:]

    # maiuscola dopo il punto ("È novembre. e sono") — piccola pulizia tipografica
    testo = re.sub(r"([.!?]\s+)([a-zàèéìòù])", lambda m: m.group(1) + m.group(2).upper(), testo)

    # due verbi incollati senza congiunzione ("mi siedo sul divano sciolgo i lacci")
    testo = re.sub(
        r"\b(mi siedo|siedo|mi alzo|alzo|mi avvicino|prendo|poso|tolgo|scendo|salgo|"
        r"mi giro|giro|appoggio)\s+"
        r"(sciolgo|slaccio|sfilo|tolgo|prendo|poso|alzo|scendo|salgo|stringo|spingo|tiro)\b",
        r"\1 e \2", testo, flags=re.IGNORECASE)

    # parole identiche ripetute di fila ("addosso addosso"): tipico del modello piccolo.
    # Restano le ripetizioni che in italiano hanno senso (piano piano, molto molto...).
    testo = re.sub(r"\b(il|lo|la|le|gli|i|un|una|di|da|e|a|o|in|con|su|per|al|dal|del|nel|sul)\s+\1\b",
                   lambda m: m.group(1), testo, flags=re.IGNORECASE)
    testo = re.sub(r"\b(\w{3,})\s+\1\b",
                   lambda m: m.group(0) if m.group(1).lower() in {"che", "piano", "molto", "poco", "tanto", "solo", "via", "oltre", "prima", "dopo", "mai", "già"} else m.group(1),
                   testo, flags=re.IGNORECASE)
    return testo
