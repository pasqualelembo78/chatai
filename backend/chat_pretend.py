"""Rilevamento dei trigger di 'finta identità' nei messaggi utente."""
import re

PRETEND_START_PATTERNS = [
    r"f(?:a|ai|acciamo)\s+finta\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami|ti\s+trovi|possa\s+essere)\s+(.+)",
    r"fingi\s+di\s+essere\s+(.+)",
    r"diventa\s+(.+)",
    r"ora\s+sei\s+(.+)",
    r"ora\s+ti\s+chiami\s+(.+)",
    r"immagina\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami|possa\s+essere)\s+(.+)",
    r"fa[\s']+finta\s+di\s+essere\s+(.+)",
    r"simula\s+(?:di\s+essere|l['\"]essere)\s+(.+)",
    r"interpret(?:a|o)\s+(?:il\s+ruolo\s+di|essere)\s+(.+)",
    r"tu\s+sei\s+adesso\s+(.+)",
    r"vorrei\s+che\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi|diventassi)\s+(.+)",
    r"potresti\s+(?:essere|fare\s+il\s+la|interpretare)\s+(.+)",
    r"come\s+se\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi)\s+(.+)",
    r"se\s+(?:tu\s+)?(?:fossi|ti\s+chiamassi)\s+(.+)",
    r"prov(?:a|o)\s+a\s+essere\s+(.+)",
    r"dammi\s+l['\"]idea\s+(?:che|di)\s+(?:tu\s+)?(?:sia|essere)\s+(.+)",
    r"fingerai\s+di\s+essere\s+(.+)",
    r"farai\s+finta\s+di\s+essere\s+(.+)",
    r"ti\s+metti\s+(?:nei\s+panni\s+di|a\s+fare\s+il\s+la)\s+(.+)",
    r" nei\s+panni\s+(?:di|del\s+la)\s+(.+)",
    r"fai\s+il\s+la\s+(.+)",
    r"vuoi\s+(?:essere|fare\s+il\s+la)\s+(.+)",
    r"mi\s+piacerebbe\s+che\s+(?:tu\s+)?(?:fossi|essere)\s+(.+)",
    r"dici\s+di\s+essere\s+(.+)",
]

PRETEND_STOP_PATTERNS = [
    r"basta\s+(?:fingere|fare\s+finta|fare\s+il\s+finto)",
    r"torna\s+a\s+essere\s+(?:te\s+stesso|il\s+vero|chi\s+eri|chi\s+eri\s+prima)",
    r"smetti\s+di\s+fingere",
    r"torna\s+al\s+tuo\s+vero\s+io",
    r"basta\s+con\s+la\s+finta",
    r"fine\s+finta",
    r"stop\s+finta",
    r"basta\s+finzione",
    r"torna\s+come\s+prima",
    r"torna\s+normale",
    r"sei\s+di\s+nuovo\s+te\s+stesso",
    r"adesso\s+sei\s+di\s+nuovo\s+(?:tu|te\s+stesso)",
    r"ok\s+basta",
    r"va\s+bene\s+basta",
    r"ho\s+capito\s+basta",
    r"puoi\s+smettere",
]


def _detect_pretend(user_text):
    """Detect impersonification triggers in user text."""
    text_lower = user_text.lower().strip()

    for pattern in PRETEND_STOP_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            return "STOP", None

    for pattern in PRETEND_START_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            target = m.group(1).strip()
            target = target.rstrip(".!?,;")
            return "START", target

    return None, None
