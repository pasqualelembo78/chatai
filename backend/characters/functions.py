# Auto-generated - Utility pure (no dipendenze da CHARACTERS)

import random
import logging

logger = logging.getLogger(__name__)


def _is_english(text):
    """Heuristic: detect if a short text is primarily in English."""
    if not text:
        return False
    english_words = {"the", "is", "a", "an", "and", "or", "of", "in", "for",
                     "who", "that", "with", "from", "this", "was", "are",
                     "has", "known", "its", "his", "her", "one", "main",
                     "created", "series", "young", "world", "power", "fight"}
    words = set(text.lower().split())
    overlap = len(words & english_words)
    return overlap >= 3


_ITALIAN_DESC_TRANSLATIONS = {
    "a young": "un giovane",
    "known for": "conosciuto per",
    "is the main": "è il principale",
    "is a ": "è un/una ",
    "from the": "dalla",
    "series": "serie",
    "created by": "creato da",
    "powerful": "potente",
    "fight": "lottare",
    "courageous": "coraggioso",
    "adventure": "avventura",
    "world": "mondo",
    "hero": "eroe",
    "villain": "villain",
    "superhero": "supereroe",
    "magic": "magia",
    "ancient": "antico",
    "legendary": "leggendario",
    "mysterious": "misterioso",
    "brave": "coraggioso",
    "strong": "forte",
    "young": "giovane",
    "old": "vecchio",
    "power": "potere",
    "dark": "oscuro",
    "light": "luce",
    "death": "morte",
    "life": "vita",
    "love": "amore",
    "war": "guerra",
    "peace": "pace",
}


def _quick_translate_desc(desc, name):
    """Quick heuristic translation of short English descriptions to Italian."""
    result = desc
    for eng, ita in _ITALIAN_DESC_TRANSLATIONS.items():
        result = result.replace(eng, ita)
    # If still mostly English, provide a simple Italian fallback
    if _is_english(result):
        return f"Personaggio con una storia unica da scoprire"
    return result


def _quick_translate_essence(essence, name):
    """Quick heuristic translation of English essence to Italian."""
    result = essence
    for eng, ita in _ITALIAN_DESC_TRANSLATIONS.items():
        result = result.replace(eng, ita)
    if _is_english(result):
        # Extract the "Sei X" part and add Italian description
        if "Sei " in essence:
            prefix = essence.split(".")[0] + "."
            return prefix + " Un personaggio affascinante con una storia da scoprire."
        return f"Sei {name}. Un personaggio affascinante."
    return result


_MALE_NAMES = {
    "marco", "luca", "andrea", "matteo", "giovanni", "paolo", "roberto",
    "giuseppe", "antonio", "francesco", "alessandro", "davide", "simone",
    "daniele", "federico", "lorenzo", "vittorio", "michele", "riccardo",
    "alberto", "carlo", "marcello", "massimo", "fabio", "filippo", "gabriele",
    "emanuele", "leonardo", "nicolo", "pietro", "raffaele", "salvatore",
    "tommaso", "valentino", "vincenzo", "cristiano", "diego", "enrico",
    "dario", "dennis", "edoarda", "eleuterio", "emanuele", "emilio",
    "ercole", "ettore", "ezio", "fausto", "felice", "fernando", "fiorenzo",
    "flavio", "florestano", "fontana", "fortunato", "fossi", "franco",
    "gabriello", "gaetano", "gennaro", "gerardo", "germania", "giacomo",
    "giampaolo", "giampiero", "giancarlo", "gianfranco", "gianluca",
    "gianmarco", "gianmaria", "gianni", "gido", "gilberto", "giorgio",
    "giovambattista", "giuliano", "giulio", "giuseppe", "giuseppino",
    "glauco", "goffredo", "gualtiero", "guerriero", "guido", "helio",
    "hugo", "ignazio", "iker", "ilario", "indo", "ireneo", "isaia",
    "ivy", "jack", "jacopo", "jader", "jari", "jason", "jean", "jerome",
    "jesse", "jil", "jimmie", "jin", "jochen", "joel", "jonas", "jorge",
    "jose", "josh", "juan", "julian", "jurgen", "justin", "kevin",
    "kiliano", "lamberto", "lancillotto", "lapis", "lars", "laura",
    "leandro", "leo", "leone", "leopoldo", "libero", "livio", "lorenzo",
    "loris", "luigi", "lyubomyr", "maksim", "manuele", "marcello",
    "marco", "mario", "massimiliano", "matteo", "matthias", "maurizio",
    "max", "melecio", "michele", "mirco", "mirko", "mohamed", "nathan",
    "nazzareno", "nelson", "neodanio", "nico", "nicola", "nicolo",
    "nio", "noble", "olivier", "omero", "osvaldo", "ottavio", "ottone",
    "otto", "pablo", "panfilo", "paolo", "pasquale", "patrick", "patrick",
    "piero", "pino", "pisana", "pitagora", "ponzio", "raffaele", "raimondo",
    "raoul", "riccardo", "richard", "roberto", "rocco", "rolando", "roman",
    "romano", "romeo", "romolo", "ron", "rosario", "ruben", "rudi", "ruggero",
    "ruggiero", "rui", "ruslan", "sabino", "samuele", "sandro", "santeri",
    "santino", "saul", "scarpa", "sebastiano", "sergio", "seth", "silvio",
    "simone", "simonluca", "stefano", "steve", "steven", "syd", "tarcisio",
    "teodoro", "thomas", "tiberio", "timothy", "tiziano", "tommaso", "tonino",
    "tony", "tosco", "tullio", "tyler", "umberto", "uriele", "valentino",
    "valerio", "valter", "vannio", "vedovato", "velio", "venanzio",
    "vincenzo", "viorel", "vito", "vittorio", "werner", "william", "wladimiro",
    "wojciech", "xavier", "zakaria", "zhang",
}



_FEMALE_NAMES = {
    "anna", "laura", "giulia", "sara", "elena", "chiara", "francesca",
    "valentina", "silvia", "roberta", "cristina", "alessandra", "paola",
    "stefania", "monica", "claudia", "maria", "rosa", "teresa", "simona",
    "nadina", "patrizia", "sandra", "daniela", "lucia", "raffaella",
    "giovanna", "marina", "sabrina", "serena", "beatrice", "alice",
    "martina", "gaia", "ginevra", "viola", "ludovica", "aurora", "greta",
    "sofia", "luna", "celeste", "matilde", "vittoria", "camilla", "noemi",
    "liliana", "elsa", "flora", "nunzia", "rosanna", "rosaria", "rosina",
    "rosa", "rossana", "rossella", "sabatina", "sabrina", "sandra",
    "sara", "selvaggia", "serena", "simona", "simonetta", "sofia", "sonia",
    "stefania", "susanna", "tamara", "tera", "teresa", "teresina",
    "teresina", "torquata", "tullia", "valentina", "valeria", "valerie",
    "vana", "vania", "vanina", "venere", "vienna", "violetta", "virginia",
    "vittoria", "viviana", "yun", "zita",
    "alana", "astra", "lara", "mia", "eva", "clara", "bianca", "valentina",
    "emma", "iris", "nova", "aria", "nina", "sophie", "sophia",
}



_FEMALE_KEYWORDS = {
    "una musicista", "una pittrice", "una maga", "una studentessa",
    "una ragazza", "una donna", "una professoressa", "un'insegnante",
    "una scienziata", "una detective", "una avventuriera",
    "donna", "ragazza", "studentessa", "professoressa",
    "lei ", "ella ", "ha detto che lei",
}



_MALE_KEYWORDS = {
    "un musicista", "un guerriero", "un professore", "un ragazzo",
    "un uomo", "un detective", "un avventuriero", "un cavaliere",
    "un imprenditore", "un hacker", "un ingegnere",
    "lui ", "egli ",
}



_DEFAULT_EVOLUTION_STAGES = [
    {"id": "base", "name": "Conoscenza", "min_messages": 0, "unlocks": ["presentazione"], "trait_bonus": {}},
    {"id": "confidenza", "name": "Confidenza", "min_messages": 10, "unlocks": ["backstory_base"], "trait_bonus": {"warmth": 1}},
    {"id": "intima", "name": "Confidenza Intima", "min_messages": 40, "unlocks": ["backstory_profonda"], "trait_bonus": {"warmth": 2, "patience": 1}},
    {"id": "profonda", "name": "Relazione Profonda", "min_messages": 100, "unlocks": ["memoria_condivisa"], "trait_bonus": {"warmth": 3}},
]



_DEFAULT_EVOLUTION_MILESTONES = [
    {"id": "prima_confidenza", "condition": {"type": "keyword", "value": ["ti racconto", "non lo sa nessuno", "segreto", "confido"]}, "effect": {"trust": 4, "affinity": 2}, "one_shot": True, "dialog": "Ti ascolta con attenzione."},
    {"id": "momento_difficile", "condition": {"type": "keyword", "value": ["non sto bene", "triste", "aiutami", "paura", "problema"]}, "effect": {"trust": 3, "affinity": 2}, "one_shot": True, "dialog": "Si avvicina preoccupato e ti offre il suo sostegno."},
    {"id": "complimento", "condition": {"type": "keyword", "value": ["bravo", "brava", "bello", "bella", "simpatico"]}, "effect": {"affinity": 2}, "cooldown_messages": 15, "dialog": "Sorride e ringrazia, visibilmente contento."},
]



