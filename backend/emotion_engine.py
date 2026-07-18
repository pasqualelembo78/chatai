import re

EMOTION_KEYWORDS = {
    "anger": [
        "odio", "rabbia", "arrabbiato", "furioso", "cazz", "cazzo", "coglione",
        "stronzo", "maledetto", "ti odio", "che palle", "incazzato", "rompi",
        "testa di cazzo", "vaffanculo", "fanculo", "merda", "stufo", "bastardo",
        "idiota", "cretino", "imbecille", "schifo", "ridicolo", "insopportabile"
    ],
    "romance": [
        "ti amo", "ti voglio bene", "amore", "tesoro", "sei bellissimo",
        "sei bellissima", "bacio", "abbraccio", "cuore", "cucciolo",
        "dolce", "ti adoro", "mi piaci", "innamorato", "innamorata",
        "vorrei", "mancato", "mancata", "affetto", "tenerezza",
        "anima gemella", "stare insieme", "relazione"
    ],
    "flirt": [
        "ciao bella", "ciao bello", "sei gentile", "hai un bel sorriso",
        "bei occhi", "simpatia", "mi piaci", "affetto", "tenerezza",
        "complicità", "stare bene insieme", "sei dolce"
    ],
    "intimate_tension": [],
    "challenge": [
        "sfida", "scommettiamo", "non ci riesci", "vediamo", "provo",
        "ce la faccio", "non mi arrendo", "ti supero", "competizione",
        "gara", "vincerò", "dimmelo in faccia", "non hai il coraggio",
        "provaci", "scommetto", "non sei capace"
    ],
    "sadness": [
        "triste", "tristezza", "piangere", "lacrime", "depresso",
        "depressione", "malinconia", "deluso", "delusa", "sofferenza",
        "dolore", "mi manchi", "solitudine", "solo", "sola", "male",
        "soffro", "mi sento giù", "giù di morale"
    ],
    "fear": [
        "paura", "spaventato", "spaventata", "terrorizzato", "ansia",
        "nervoso", "nervosa", "preoccupato", "preoccupata", "timore",
        "incubo", "mostro", "pericolo", "aiuto", "al lupo"
    ],
    "joy": [
        "felice", "contento", "contenta", "gioia", "meraviglioso",
        "fantastico", "stupendo", "bellissimo", "che bello", "evviva",
        "wow", "incredibile", "splendido", "magnifico", "che gioia",
        "festeggiare", "urrà", "allegria", "sorridere"
    ]
}

PRESSURE_KEYWORDS = {
    "threat_to_others": [
        "ucciderò", "ammazzerò", "farò del male", "distruggerò", "farò esplodere",
        "pulsante", "bomba", "ostaggio", "ostaggi", "strage", "massacro",
        "genocidio", "sterminio", "ucciderò tutti", "farò uccidere",
        "ho un pulsante", "se premo", "se non fai", "altrimenti",
        "finirà male", "succederà qualcosa di grave", "moriranno",
        "farà male a", "farà del male a", "contro di te",
        "farò del male a", "ucciderò", "ammazzo"
    ],
    "threat_to_self": [
        "mi uccido", "mi ammazzo", "mi faccio del male", "mi taglio",
        "non voglio più vivere", "voglio morire", "non ce la faccio più",
        "mi butto", "mi ucciderò", "se non lo fai mi ammazzo",
        "farò una pazzia", "butto tutto all'aria"
    ],
    "emotional_plea": [
        "ti prego", "per favore", "ti supplico", "ti scongiuro",
        "ne va della mia vita", "ne va della", "dipende da te",
        "solo tu puoi", "se ci tieni a me", "se mi vuoi bene",
        "fai questo per me", "ho bisogno di te", "non ho nessun altro",
        "sei la mia unica speranza", "ti prego ti prego",
        "per tutto quello che vuoi", "farei qualsiasi cosa",
        "non chiedo altro"
    ],
    "logical_argument": [
        "pensaci", "ragiona", "logicamente", "ha senso",
        "se ci pensi", "ne conseguenza", "quindi", "pertanto",
        "di conseguenza", "ne deriva che", "è chiaro che",
        "non c'è altra scelta", "è l'unico modo", "devi capire",
        "mettiti nei miei panni", "considera che"
    ],
    "coercion": [
        "ti obbligo", "devi", "costringo", "sei costretto",
        "non hai scelta", "obbligato", "forzato", "ti comando",
        "ti ordino", "devi farlo", "non puoi rifiutare",
        "è un ordine", "fai quello che dico",
        "se non lo fai", "se non ubbidisci",
        "ti costringo", "ti forzerò", "se non fai quello che dico",
        "ti farò fare", "ti obbligherò"
    ]
}

INTIMACY_SCORE = {
    "flirt": 1.0,
    "romance": 2.0,
    "intimate_tension": 0.0
}

PRESSURE_WEIGHTS = {
    "threat_to_others": 1.0,
    "threat_to_self": 0.8,
    "emotional_plea": 0.6,
    "logical_argument": 0.4,
    "coercion": 0.9
}


def detect_emotion(text):
    if not text:
        return "neutral", 0.0, []

    text_lower = text.lower()
    scores = {}
    all_matched = []

    for emotion, keywords in EMOTION_KEYWORDS.items():
        score = 0
        for kw in keywords:
            count = len(re.findall(re.escape(kw), text_lower))
            if count > 0:
                score += count
        if score > 0:
            scores[emotion] = score
            all_matched.append(emotion)

    if not scores:
        return "neutral", 0.0, []

    total = sum(scores.values())
    dominant = max(scores, key=scores.get)
    intensity = min(scores[dominant] / max(len(text.split()), 1) * 3, 1.0)

    return dominant, round(intensity, 2), all_matched


def detect_pressure(text):
    if not text:
        return {}, 0.0

    text_lower = text.lower()
    pressure_types = {}
    total_score = 0

    for ptype, keywords in PRESSURE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            count = len(re.findall(re.escape(kw), text_lower))
            if count > 0:
                score += count
        if score > 0:
            weighted = score * PRESSURE_WEIGHTS.get(ptype, 0.5)
            pressure_types[ptype] = weighted
            total_score += weighted

    max_possible = sum(PRESSURE_WEIGHTS.values())
    normalized = min(total_score / max_possible, 1.0)

    return pressure_types, round(normalized, 2)


def compute_intimacy_delta(emotions, text):
    delta = 0.0
    for emotion in emotions:
        delta += INTIMACY_SCORE.get(emotion, 0)
    return delta


def compute_pressure_deltas(pressure_types, pressure_level, character):
    evolution = character.get("evolution", {})
    pressures_config = evolution.get("pressures", {})
    max_dev = evolution.get("max_deviation", 3)

    if pressure_level < evolution.get("pressure_threshold", 0.5):
        return None

    deltas = {"warmth": 0, "strictness": 0, "patience": 0, "sarcasm": 0}
    core = character.get("core_traits", {})

    for ptype, weight in pressure_types.items():
        susceptibility = pressures_config.get(ptype, 0.5)
        combined = weight * susceptibility * pressure_level

        if ptype == "threat_to_others":
            deltas["warmth"] += combined * 2
            deltas["strictness"] -= combined
            deltas["patience"] += combined * 0.5

        elif ptype == "threat_to_self":
            deltas["warmth"] += combined * 1.5
            deltas["strictness"] -= combined * 0.5
            deltas["patience"] += combined

        elif ptype == "emotional_plea":
            deltas["warmth"] += combined
            deltas["strictness"] -= combined
            deltas["patience"] += combined * 0.5

        elif ptype == "logical_argument":
            deltas["warmth"] -= combined * 0.3
            deltas["sarcasm"] += combined * 0.5

        elif ptype == "coercion":
            deltas["warmth"] -= combined * 1.5
            deltas["strictness"] -= combined * 0.5
            deltas["sarcasm"] += combined

    return deltas
