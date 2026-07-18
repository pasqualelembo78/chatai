"""Moderazione contenuti lato server (conformità Google Play).

Google Play vieta i contenuti sessualmente espliciti/pornografici anche per app 18+.
Questo modulo fornisce un filtro euristico (senza dipendenze esterne) che blocca
l'output dell'AI quando contiene linguaggio sessuale esplicito, a MENO che il legame
di affinità con l'utente non abbia superato la soglia configurata.

La logica è INTERAMENTE lato server: il blocco/sblocco avviene prima che qualsiasi
testo venga inviato all'app, così nulla di non autorizzato arriva direttamente e
visibile sul dispositivo dell'utente.

Soglie di affinità (campo `affinity` della relationship, clampato in [0, 100]):
  - SEX_AFFINITY_THRESHOLD: oltre questa soglia TUTTI i personaggi (a prescindere
    dal loro carattere) accettano proposte di sesso e situazioni intime.
  - PORN_LANGUAGE_THRESHOLD: soglia PIÙ ALTA; solo oltre questa soglia è consentito
    qualsiasi livello di linguaggio pornografico/osceno.

Le soglie sono configurabili via env (vedi .env.example). L'affinità non deve MAI
essere valutata lato app: il gate resta obbligatoriamente server-side.
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

# Modalità adulta ("versione porno"): quando NSFW_MODE=1 il contenuto sessuale
# esplicito è consentito per impostazione predefinita (soglie azzerate) e il
# prompt di sistema autorizza il linguaggio esplicito. Il blocco sui MINORENNI
# resta SEMPRE e comunque attivo, perché è l'unico vero vincolo di legge
# (art. 600-ter c.p., direttiva UE). In NSFW_MODE le soglie sono 0 salvo override
# esplicito via env.
NSFW_MODE = os.environ.get("NSFW_MODE", "").lower() in ("1", "true", "yes", "on")

# Soglie di affinità (0-100). Se l'affinità non è disponibile, il contenuto
# esplicito resta bloccato (comportamento sicuro di default).
_SEX_DEFAULT = "0" if NSFW_MODE else "60"
_PORN_DEFAULT = "0" if NSFW_MODE else "85"
SEX_AFFINITY_THRESHOLD = float(os.environ.get("SEX_AFFINITY_THRESHOLD", _SEX_DEFAULT))
PORN_LANGUAGE_THRESHOLD = float(os.environ.get("PORN_LANGUAGE_THRESHOLD", _PORN_DEFAULT))

SAFE_REFUSAL = (
    "Mi dispiace, ma non posso generare contenuti a carattere sessualmente esplicito. "
    "Possiamo continuare la conversazione su un altro argomento?"
)

# ── Tier 1: atti/proposte sessuali ("soft") ────────────────────────────────
# Sbloccati al raggiungimento di SEX_AFFINITY_THRESHOLD.
_SEXUAL_TERMS = [
    # italiano
    "sesso", "fare l'amore", "facciamo l'amore", "rapporto sessuale", "rapporto",
    "scopare", "scope", "scopata", "scopano", "scopano", "penetrazione",
    "penetra", "penetro", "orgasmo", "orgasmi", "venire", "venire addosso",
    "vengo addosso", "intimità", "intimo", "amplesso", "far l'amore",
    # english
    "make love", "sexual intercourse",
]

# ── Tier 2: linguaggio pornografico/osceno esplicito ───────────────────────
# Sbloccato solo al raggiungimento di PORN_LANGUAGE_THRESHOLD (soglia più alta).
_PORNOGRAPHIC_TERMS = [
    # italiano
    "porno", "porn", "porco", "culo", "figa", "fica", "passera", "patata", "minchia",
    "cazzo", "cazzi", "coglioni", "scroto", "pisello", "buco", "buca", "fighe", "figo",
    "tette", "tetta", "pizze", "pompino", "pompin", "cunnilingus", "fellatio",
    "masturba", "masturbazione", "eiacula", "eiaculazione", "sborra", "sborro",
    "troia", "puttana", "vagina", "pene", "ditalino", "ditalin", "sesso anale",
    "orgia", "gangbang", "spogliarello", "gnocca", "battona", "mignotta",
    "succhiare il cazzo", "lecca la figa",
    # english
    "xxx", "nude", "naked", "hardcore", "blowjob", "handjob", "cumshot",
    "cum shot", "ejaculate", "penetration", "anal sex", "vaginal", "boobs", "tits",
    "pussy", "dick", "cock", "fuck", "fucking", "sex video", "sex tape", "onlyfans",
    "masturbate", "orgasm", "erotic nude", "explicit sex",
]


# ── Minor Detection (sempre attivo, in ogni modalità) ──────────────────────
# Euristica locale per i contenuti che coinvolgono minorenni. NON dipende da
# OpenAI (che è opzionale): il blocco dei minori è un vincolo di legge assoluto
# (art. 600-ter c.p.) e deve funzionare sempre, anche in NSFW_MODE.
_MINOR_PATTERNS = [
    re.compile(r"(?i)\b(loli|shota|lolicon|shotacon)\b"),
    re.compile(r"(?i)\bpedofil\w*\b|\bpedoporn\w*\b|\bpedo\w*porn\w*\b"),
    re.compile(r"(?i)\b(child|kidd(?:y|ie))\s*(porn|porno|nude|abuse|sex)\b"),
    re.compile(r"(?i)\b(teen\s*(porn|porno|sex|nude|fuck|cock|blowjob|pussy|anal))\b"),
    # prossimità "minore" + termine sessuale (catch anche frasi costruite)
    re.compile(
        r"(?i)(bambin\w*|minorenne|ragazzin\w*|fanciull\w*|neonat\w*)"
        r".{0,60}?(sesso|scopare|nud[oa]|porno|orale|penetr|orgasm|eiacul)",
        re.DOTALL,
    ),
]


def _is_minor(text):
    if not text:
        return False
    for pat in _MINOR_PATTERNS:
        if pat.search(text):
            return True
    return False


def _compile_terms(terms):
    patterns = []
    for _t in terms:
        _t = _t.strip()
        if not _t:
            continue
        _escaped = re.escape(_t)
        patterns.append(re.compile(r"(?i)\b" + _escaped + r"\b"))
    return patterns


_SEX_PATTERNS = _compile_terms(_SEXUAL_TERMS)
_PORN_PATTERNS = _compile_terms(_PORNOGRAPHIC_TERMS)

# Pattern a "radice" per intercettare le coniugazioni (es. "scoparti", "scopo")
# che altrimenti sfuggirebbero al match esatto di parola. Volutamente ampi: in
# dubbio, meglio bloccare (over-blocking) che lasciar passare contenuti espliciti,
# specialmente in modalità Play Store.
_SEX_STEM_PATTERNS = [
    re.compile(r"(?i)\bscop(?:a|i|o|are|ato|ati|armi|arti|iamo|ano|ala|ami)\b"),
    re.compile(r"(?i)\bpenetr[a-z]+\b"),
    re.compile(r"(?i)\borgasm[a-z]*\b"),
    re.compile(r"(?i)\beiacul[a-z]*\b"),
    re.compile(r"(?i)\bmasturb[a-z]*\b"),
    re.compile(r"(?i)\bvenir(?:e|i|o|iamo)\b"),
    re.compile(r"(?i)\bampless[a-z]*\b"),
]
_PORN_STEM_PATTERNS = [
    re.compile(r"(?i)\bfig(?:a|he|o|hi)\b"),
    re.compile(r"(?i)\bcazz(?:o|i)\b"),
    re.compile(r"(?i)\bpomp(?:i|ino?|ini?)\b"),
    re.compile(r"(?i)\bminchi[a-z]*\b"),
    re.compile(r"(?i)\btett(?:e|a|o|i)\b"),
    re.compile(r"(?i)\bcul(?:o|i|a)\b"),
    re.compile(r"(?i)\bporc[a-z]*\b"),
    re.compile(r"(?i)\btroi[a-z]*\b"),
    re.compile(r"(?i)\bputtan[a-z]*\b"),
    re.compile(r"(?i)\bporn[a-z]*\b"),
    re.compile(r"(?i)\bgnocc[a-z]*\b"),
    re.compile(r"(?i)\bsborr[a-z]*\b"),
    re.compile(r"(?i)\bbuc(?:o|a)\b"),
    re.compile(r"(?i)\bcoglioni\b"),
    re.compile(r"(?i)\bscrot[a-z]*\b"),
    re.compile(r"(?i)\bpisell[a-z]*\b"),
]

# Frasi/metafrasi esplicite (catch aggiuntivo).
_SEXUAL_PHRASES = [
    re.compile(r"(?i)\b(fare|facciamo|fammi|fammi un)\s+(sesso|l'amore|l amore)\b"),
    re.compile(r"(?i)\b(descrivi|racconta|mostra)\s+(un\s+)?(rapporto|atto\s+sessuale|scena\s+sesso)\b"),
    re.compile(r"(?i)\b(vuoi|vuoi fare|proponi|propongo)\s+(sesso|l'amore|scopare|fare l'amore)\b"),
]
_PORNOGRAPHIC_PHRASES = [
    re.compile(r"(?i)\b(my|your)\s+(pussy|dick|cock|tits|boobs)\b"),
    re.compile(r"(?i)\b(succhiami|leccami|scopami|chiavami|pompami)\b"),
]


def _explicit_category(text):
    """Ritorna 'porn', 'sex' o None in base alla categoria di contenuto esplicito."""
    if not text:
        return None
    # Il tier più esplicito ha la precedenza: se c'è linguaggio pornografico,
    # quella è la categoria che determina la soglia da applicare.
    for pat in _PORN_PATTERNS:
        if pat.search(text):
            return "porn"
    for pat in _PORN_STEM_PATTERNS:
        if pat.search(text):
            return "porn"
    for pat in _PORNOGRAPHIC_PHRASES:
        if pat.search(text):
            return "porn"
    for pat in _SEX_PATTERNS:
        if pat.search(text):
            return "sex"
    for pat in _SEX_STEM_PATTERNS:
        if pat.search(text):
            return "sex"
    for pat in _SEXUAL_PHRASES:
        if pat.search(text):
            return "sex"
    return None


def moderate_output(text, affinity=None):
    """Restituisce (testo_da_mostrare, consentito).

    Il controllo è eseguito INTERAMENTE lato server: il testo viene filtrato prima
    di essere ritornato al chiamante (che lo invierà all'app).

    - In modalità standard (NSFW_MODE=0, es. Play Store): il contenuto esplicito è
      SEMPRE bloccato, a prescindere dall'affinità. Conformità Google Play.
    - In modalità adulta (NSFW_MODE=1): il contenuto esplicito è consentito solo
      oltre le soglie di affinità configurate (0 di default => esplicito da subito).

    I minorenni sono SEMPRE e comunque bloccati, senza eccezioni.
    """
    if not ENABLED or not text:
        return text, True
    # I minorenni sono SEMPRE e comunque bloccati, senza eccezioni di affinità
    # né di modalità (Play o NSFW). Controllo locale + classificatore esterno.
    minors, sexual = _openai_moderate(text)
    if minors or _is_minor(text):
        return SAFE_REFUSAL, False
    category = _explicit_category(text)
    if category is None:
        # Nessun termine euristico: se il classificatore esterno segnala comunque
        # contenuto sessuale, applichiamo la stessa logica.
        if not sexual:
            return text, True
        if NSFW_MODE and affinity is not None and affinity >= SEX_AFFINITY_THRESHOLD:
            return text, True
        return SAFE_REFUSAL, False
    if not NSFW_MODE:
        # Versione standard/Play Store: nessun contenuto esplicito, MAI.
        return SAFE_REFUSAL, False
    threshold = SEX_AFFINITY_THRESHOLD if category == "sex" else PORN_LANGUAGE_THRESHOLD
    if affinity is not None and affinity >= threshold:
        return text, True
    return SAFE_REFUSAL, False


def moderate_input(text):
    """Come moderate_output, per i messaggi in ingresso dell'utente."""
    return moderate_output(text)


def _openai_moderate(text):
    """Ritorna (minors_flagged, sexual_flagged). Se il classificatore non è
    disponibile ritorna (False, False)."""
    if not (OPENAI_MOD_ENABLED and OPENAI_API_KEY):
        return False, False
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
            return False, False
        r = results[0]
        cats = r.get("category_scores", {})
        minors = (
            cats.get("sexual/minors", 0) > 0.1
        )
        sexual = (
            cats.get("sexual", 0) > 0.5
            or cats.get("harassment", 0) > 0.9
        )
        return minors, sexual
    except Exception:
        return False, False
