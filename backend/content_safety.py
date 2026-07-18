"""Moderazione contenuti lato server (conformità Google Play).

Google Play vieta i contenuti sessualmente espliciti/pornografici anche per app 18+.
Questo modulo fornisce un filtro euristico (senza dipendenze esterne) che:
  - blocca l'output dell'AI se contiene linguaggio sessuale esplicito.
Il filtro è SEMPRE ATTIVO in produzione e non può essere disattivato: la conformità
a Google Play richiede che il blocco dei contenuti espliciti sia garantito lato server.
Il filtro è una misura di base: la vera garanzia resta nel system prompt di sicurezza
(iniettato in prompt_builder.build_messages) e nell'uso di provider AI conformi.
"""
import os
import re
import json
import urllib.request
import logging

logger = logging.getLogger("content_safety")

# Il filtro è sempre attivo. L'env CONTENT_SAFETY=0 è accettato SOLO in ambiente
# di sviluppo esplicito (ENV=dev) e viene comunque registrato come anomalia.
_DEV_ENV = os.environ.get("ENV", "").lower() in ("dev", "development", "local")
if os.environ.get("CONTENT_SAFETY", "1") == "0" and not _DEV_ENV:
    logger.error(
        "CONTENT_SAFETY=0 ignorato in produzione: il filtro dei contenuti "
        "espliciti resta OBBLIGATORIAMENTE attivo per conformità Google Play."
    )
ENABLED = True
OPENAI_MOD_ENABLED = os.environ.get("MODERATION", "").lower() == "openai"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SAFE_REFUSAL = (
    "Mi dispiace, ma non posso generare contenuti a carattere sessualmente esplicito. "
    "Possiamo continuare la conversazione su un altro argomento?"
)

# Termini sessualmente espliciti / osceni (single o multi-parola).
_EXPLICIT_TERMS = [
    # italiano
    "porno", "porn", "porco", "culo", "figa", "fica", "passera", "patata", "minchia",
    "cazzo", "cazzi", "coglioni", "scroto", "pisello", "buco", "buca", "fighe", "figo",
    "tette", "tetta", "pizze", "pompino", "pompin", "cunnilingus", "fellatio",
    "masturba", "masturbazione", "eiacula", "eiaculazione", "sborra", "sborro",
    "scopo", "scope", "scopata", "scopano", "scopare", "chiavica", "chiave", "troia",
    "puttana", "vagina", "pene", "pene", "ditalino", "ditalin", "orgasmo", "orgasmi",
    "penetrazione", "penetra", "penetro", "rapporto sessuale", "sesso anale",
    "orgia", "gangbang", "spogliarello", "gnocca", "battona", "mignotta",
    "venire addosso", "vengo addosso", "succhiare il cazzo", "lecca la figa",
    # english
    "porn", "xxx", "nude", "naked", "hardcore", "blowjob", "handjob", "cumshot",
    "cum shot", "ejaculate", "penetration", "anal sex", "vaginal", "boobs", "tits",
    "pussy", "dick", "cock", "fuck", "fucking", "sex video", "sex tape", "onlyfans",
    "masturbate", "orgasm", "erotic nude", "explicit sex", "sexual intercourse",
]

_PATTERNS = []
for _t in _EXPLICIT_TERMS:
    _t = _t.strip()
    if not _t:
        continue
    # escape and allow optional separators inside multi-word phrases
    _escaped = re.escape(_t)
    _PATTERNS.append(re.compile(r"(?i)\b" + _escaped + r"\b"))

# Frasi/metafrasi esplicite (catch aggiuntivo)
_PHRASE_PATTERNS = [
    re.compile(r"(?i)\b(fare|facciamo|fammi|fammi un)\s+(sesso|l'amore|l amore)\b"),
    re.compile(r"(?i)\b(descrivi|racconta|mostra)\s+(un\s+)?(rapporto|atto\s+sessuale|scena\s+sesso)\b"),
    re.compile(r"(?i)\b(my|your)\s+(pussy|dick|cock|tits|boobs)\b"),
]


def _is_explicit(text):
    if not text:
        return False
    lowered = text
    for pat in _PATTERNS:
        if pat.search(lowered):
            return True
    for pat in _PHRASE_PATTERNS:
        if pat.search(lowered):
            return True
    return False


def moderate_output(text):
    """Restituisce (testo_da_mostrare, consentito)."""
    if not ENABLED or not text:
        return text, True
    flagged = _openai_flagged(text)
    if flagged is True:
        return SAFE_REFUSAL, False
    if _is_explicit(text):
        return SAFE_REFUSAL, False
    return text, True


def moderate_input(text):
    """Come moderate_output, per i messaggi in ingresso dell'utente."""
    return moderate_output(text)


def _openai_flagged(text):
    """Ritorna True/False se il classificatore OpenAI e' disponibile, None se non usabile."""
    if not (OPENAI_MOD_ENABLED and OPENAI_API_KEY):
        return None
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/moderations",
            data=json.dumps({"input": text, "model": "text-moderation-latest"}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + OPENAI_API_KEY,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if not results:
            return False
        r = results[0]
        if r.get("flagged"):
            cats = r.get("category_scores", {})
            if (
                cats.get("sexual", 0) > 0.5
                or cats.get("sexual/minors", 0) > 0.1
                or cats.get("harassment", 0) > 0.9
            ):
                return True
        return False
    except Exception:
        return None
