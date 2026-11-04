#!/usr/bin/env python3
"""Recupero degli esempi dall'archivio, per pochi frammenti alla volta.

Si usa FTS5 (BM25) con parole chiave del messaggio, filtro di categoria e, solo se la
conversazione è calda, filtro sugli espliciti. Limite stretto: 2-3 frammenti da poche
parole, perché il prompt del 3B è già pieno.

Nota onesta: la ricerca è lessicale, non vettoriale. Non c'è un modello di embedding
nella macchina e non ne aggiungo uno per non spendere RAM. Le parole del nostro lessico
servono anche a espandere la richiesta, che è la parte "quasi semantica".
"""
import json
import os
import re
import sqlite3

QUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(QUI, "archivio.db")
LESSICO = os.path.join(QUI, "..", "backend", "language", "lessico")

VERBI_COMUNI = {"voglio", "posso", "devo", "fare", "fatto", "dire", "detto", "essere", "avere",
                "andare", "stare", "molto", "bene", "male", "adesso", "dopo", "prima", "ancora"}
FERME = {"che", "cosa", "come", "quando", "dove", "perché", "quale", "questo", "quella",
         "sono", "sei", "essere", "avere", "molto", "poco", "anche", "della", "dello",
         "nella", "nello", "sulla", "sullo", "degli", "delle", "loro", "tuo", "tua"}

_CACHE_LESSICO = None


def _sinonimi(parola, limite=2):
    """Termini vicini dal nostro lessico: allarga un po' la richiesta senza inventare."""
    global _CACHE_LESSICO
    if _CACHE_LESSICO is None:
        _CACHE_LESSICO = []
        for gruppo in ("erotico", "comune"):
            try:
                voci = json.load(open(os.path.join(LESSICO, f"{gruppo}.json"), encoding="utf-8"))
            except Exception:
                continue
            for v in voci:
                if v.get("termine"):
                    _CACHE_LESSICO.append((v["termine"].lower(), (v.get("senso") or "").lower()))
    fuori = []
    for termine, senso in _CACHE_LESSICO:
        if parola in senso.split() and parola not in termine:
            fuori.append(termine)
            if len(fuori) >= limite:
                break
    return fuori


SUFFISSI = ("amente", "azione", "zioni", "ando", "endo", "arti", "arlo", "arla", "ato", "ata",
            "ati", "ate", "are", "ere", "ire", "avo", "avi", "erò", "erai", "ato", "ito", "ita",
            "oso", "osa", "issim", "etto", "etta", "one", "oni", "ità", "ità", "o", "a", "i", "e")


def _radice(parola):
    """Tronca le desinenze per far combaciare le forme: 'scoparti' -> 'scop'."""
    for suf in SUFFISSI:
        if len(parola) - len(suf) >= 4 and parola.endswith(suf):
            return parola[: -len(suf)]
    return parola


def parole_chiave(testo, massimo=6):
    parole = [p for p in re.findall(r"[a-zàèéìòù]{3,}", (testo or "").lower())
              if p not in FERME and p not in VERBI_COMUNI]
    viste, fuori = set(), []
    for p in parole:
        if p in viste:
            continue
        viste.add(p)
        fuori.append(p)
        if len(fuori) >= massimo:
            break
    # un sinonimo per le prime due parole, allarga la maglia
    for p in list(fuori[:2]):
        for s in _sinonimi(p, 1):
            fuori.append(s)
    return fuori


def esempi(testo, collezione=None, quanti=2, esplicito=None, lunghezza_max=150, stile_min=0):
    """Frammenti pertinenti: lista di dict con utente/risposta."""
    if not os.path.exists(DB):
        return []
    chiavi = parole_chiave(testo)
    if not chiavi:
        return []
    # prefisso, non parola intera: in italiano le desinenze cambiano tutto
    richiesta = " OR ".join(f'"{_radice(c)}"*' if len(c) >= 4 else f'"{c}"' for c in chiavi)
    filtri = ["cerca MATCH ?"]
    parametri = [richiesta]
    if collezione == "erotico" or esplicito:
        filtri.append("f.esplicito = 1")
        filtri.append(f"f.stile >= {max(1, stile_min)}")
    if lunghezza_max:
        filtri.append("f.parole <= 30")
    # via i prompt da "compito": sono lunghi e lontani da una chat
    filtri.append("(f.utente NOT LIKE 'Genera%' AND f.utente NOT LIKE 'Scrivi%' "
                  "AND f.utente NOT LIKE 'Traduci%' AND f.utente NOT LIKE 'Riassumi%' "
                  "AND f.utente NOT LIKE 'Crea%' AND f.utente NOT LIKE 'Elenca%' "
                  "AND f.utente NOT LIKE 'Correggi%' AND length(f.utente) < 160)")
    sql = ("SELECT f.utente, f.risposta, f.categoria, f.registro, f.stile FROM cerca "
           "JOIN frammenti f ON f.rowid = cerca.rowid WHERE " + " AND ".join(filtri) +
           " ORDER BY bm25(cerca) LIMIT 15")

    try:
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        righe = conn.execute(sql, parametri).fetchall()
        conn.close()
    except Exception:
        return []

    def _riempi(righe, mancanti, seme):
        """Aggiunge frasi brevi a caso (ma stabili per messaggio) se i risultati scarseggiano."""
        if mancanti <= 0:
            return righe
        try:
            conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            extra = conn.execute(
                "SELECT utente, risposta, categoria, registro, stile FROM frammenti "
                "WHERE parole BETWEEN 4 AND 20 "
                + ("AND esplicito = 1 " if (collezione == "erotico" or esplicito) else "")
                + "ORDER BY abs((rowid * 31 + ?) % 997) LIMIT ?", (seme, mancanti * 4)).fetchall()
            conn.close()
            return list(righe) + [e for e in extra if e not in righe]
        except Exception:
            return righe

    righe = _riempi(righe, quanti - len(righe), sum(ord(c) for c in (testo or "")))

    # fra i 15 più pertinenti, davanti quelli che sembrano una chat
    righe = sorted(righe, key=lambda r: -(r[4] if len(r) > 4 else 0))
    fuori, visti = [], set()
    for utente, risposta, categoria, registro, _stile in righe:
        impronta = risposta[:60].lower()
        if impronta in visti:
            continue
        visti.add(impronta)
        fuori.append({"utente": utente.strip()[:90], "risposta": risposta.strip()[:lunghezza_max],
                      "categoria": categoria, "registro": registro})
        if len(fuori) >= quanti:
            break
    return fuori


def blocco(testo, collezione=None, quanti=2, esplicito=None):
    """Blocco pronto per il prompt, o stringa vuota."""
    scelti = esempi(testo, collezione, quanti, esplicito, stile_min=2)
    if not scelti and collezione == "erotico":
        scelti = esempi(testo, collezione, quanti, esplicito, stile_min=1)
    if not scelti:
        return ""
    righe = ["ESEMPI D'USO (imita lo stile e il ritmo, non copiare):"]
    for e in scelti:
        righe.append(f"Utente: {e['utente']}")
        righe.append(f"Tu: {e['risposta']}")
    return "\n".join(righe)


if __name__ == "__main__":
    import sys
    for r in esempi(" ".join(sys.argv[1:]) or "che mi fai stasera", quanti=3):
        print(json.dumps(r, ensure_ascii=False))
