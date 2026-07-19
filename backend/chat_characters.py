"""Ricerca personaggi per nome e costruzione di personaggi ad-hoc da descrizione."""
import re


def _find_character_by_name(name_query):
    """
    Find an existing character by name with smart fuzzy matching.
    Searches across name, full_name, surname, role, description, tags.
    """
    from characters import list_characters
    name_lower = name_query.lower().strip()

    _ARTICLES = {"il", "lo", "la", "i", "gli", "le", "un", "uno", "una"}
    _TITLES = {"dottoressa", "dottore", "professoressa", "professor", "prof",
               "maestro", "maestra", "signora", "signore", "sig.ra", "sig.",
               "dott.ssa", "dr.", "drssa", "ragazzo", "ragazza", "rago"}

    stripped = name_lower
    words = name_lower.split()
    if words and words[0] in _ARTICLES:
        stripped = " ".join(words[1:])
    if words and words[0] in _TITLES:
        stripped = " ".join(words[1:])

    all_chars = list_characters()

    def _score(c):
        s = 0
        cname = c.get("name", "").lower()
        full = c.get("full_name", "").lower()
        surname = c.get("surname", "").lower()
        role = c.get("role", "").lower()
        desc = c.get("description", "").lower()
        essence = c.get("essence", "").lower()
        tags = [t.lower() for t in c.get("tags", [])]

        if cname == name_lower or cname == stripped:
            s += 100
        if full == name_lower or full == stripped:
            s += 95
        if surname == name_lower or surname == stripped:
            s += 90

        if stripped and cname:
            if stripped in cname or cname in stripped:
                s += 70
        if stripped and full:
            if stripped in full or full in stripped:
                s += 65

        if stripped:
            role_words = role.split()
            for rw in role_words:
                if len(rw) > 3 and rw in stripped:
                    s += 40
                if len(rw) > 3 and stripped in rw:
                    s += 35
            role_kw_map = {
                "dottore": ["medico", "dottore", "dott", "doctor"],
                "dottessa": ["dottoressa", "dott", "doctor"],
                "professor": ["professore", "insegnante", "prof", "teacher"],
                "professoressa": ["professoressa", "insegnante", "prof", "teacher"],
                "infermiere": ["infermiere", "infermiera", "nurse"],
                "avvocato": ["avvocato", "avvocatessa", "lawyer"],
                "poliziotto": ["poliziotto", "poliziotta", "carabiniere", "police"],
                "parrucchiera": ["parrucchiere", "parrucchiera", "hairdresser"],
                "cuoco": ["cuoco", "cuoca", "chef", "cook"],
                "barista": ["barista", "bartender"],
                "magistrato": ["magistrato", "magistrata", "giudice", "judge"],
            }
            for kw, synonyms in role_kw_map.items():
                if kw in stripped or kw in name_lower:
                    for syn in synonyms:
                        if syn in role or syn in desc:
                            s += 50
                            break

        if stripped:
            for word in stripped.split():
                if len(word) > 3:
                    if word in desc:
                        s += 20
                    if word in essence:
                        s += 15

        if stripped:
            for tag in tags:
                if stripped in tag or tag in stripped:
                    s += 30

        return s

    scored = [(s, c) for c in all_chars if (s := _score(c)) > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _build_ad_hoc_character(description):
    """
    Build a character dict from a free-form description.
    Extracts: name, age, gender, role, occupation, and infers personality.
    """
    from characters.functions import _MALE_NAMES, _FEMALE_NAMES
    desc_lower = description.lower()
    name = None

    _FEM_KW = {"donna", "ragazza", "studentessa", "professoressa", "dottoressa",
               "infermiera", "cuoca", "parrucchiera", "avvocatessa",
               "poliziotta", "magistrata", "maestra", "signora",
               "un'insegnante", "una professoressa"}
    _MAS_KW = {"uomo", "ragazzo", "studente", "professore", "dottore",
               "infermiere", "cuoco", "parrucchiere", "avvocato",
               "poliziotto", "magistrato", "maestro", "signore"}

    name_patterns = [
        r"(?:si\s+chiama|chiamat[oi]|nome\s+(?:è|sarà|sara))\s+(\w+)",
        r"(?:il\s+dottore|il\s+professore|la\s+dottoressa|il\s+maestro|la\s+maestra|il\s+ragazzo|la\s+ragazza|il\s+signore|la\s+signora|il\s+cuoco|la\s+cuoca|il\s+barista|la\s+barista|il\s+parrucchiere|la\s+parrucchiera|l'avvocato|l'avvocatessa|il\s+poliziotto|la\s+poliziotta|il\s+infermiere|la\s+infermiera)\s+(\w+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, desc_lower)
        if m:
            name = m.group(1).strip().capitalize()
            break

    if not name:
        _SKIP = {"un", "una", "il", "la", "le", "gli", "i", "che", "chi", "cui",
                 "del", "della", "dello", "dei", "delle", "di", "da", "in", "con",
                 "per", "su", "al", "allo", "alla", "ai", "agli", "alle",
                 "ma", "e", "o", "se", "come", "anche", "poi", "così", "cosi",
                 "adesso", "ora", "tu", "io", "lui", "lei", "noi", "voi", "loro",
                 "sia", "essere", "fare", "avere", "dire", "pensare", "volere"}
        words = description.split()
        candidates = []
        for w in words:
            clean = w.strip(".,!?;:'\"")
            if clean and clean[0].isupper() and len(clean) >= 2 and clean.lower() not in _SKIP:
                candidates.append(clean)
        if candidates:
            name = candidates[-1]
        else:
            if any(kw in desc_lower for kw in _FEM_KW):
                name = "Lei"
            elif any(kw in desc_lower for kw in _MAS_KW):
                name = "Lui"
            else:
                name = "Sconosciuto"

    age = 0
    age_patterns = [
        r"(\d{2,3})\s*anni",
        r"di\s+(\d{2,3})\s*anni",
        r"età\s+(?:di\s+)?(\d{2,3})",
        r"un(?:a)?\s+(\d{2,3})enne",
    ]
    for pat in age_patterns:
        m = re.search(pat, desc_lower)
        if m:
            try:
                age = int(m.group(1))
                if 1 <= age <= 150:
                    break
                age = 0
            except ValueError:
                pass

    gender = ""
    gender_display = ""

    for kw in _FEM_KW:
        if kw in desc_lower:
            gender = "F"
            gender_display = "femminile"
            break
    if not gender:
        for kw in _MAS_KW:
            if kw in desc_lower:
                gender = "M"
                gender_display = "maschile"
                break

    if not gender:
        name_lower_inner = name.lower()
        if name_lower_inner in _FEMALE_NAMES:
            gender = "F"
            gender_display = "femminile"
        elif name_lower_inner in _MALE_NAMES:
            gender = "M"
            gender_display = "maschile"

    if not gender:
        if name.lower().endswith("a") and name.lower() not in {"luca", "nicola", "andrea"}:
            gender = "F"
            gender_display = "femminile"
        elif name.lower().endswith(("o", "e")):
            gender = "M"
            gender_display = "maschile"

    role_keywords = {
        "dottore": ("medico", "Lavora come medico."),
        "dottoressa": ("medico", "Lavora come medica."),
        "professore": ("insegnante", "Lavora come insegnante."),
        "professoressa": ("insegnante", "Lavora come insegnante."),
        "avvocato": ("avvocato", "Lavora come avvocato."),
        "avvocatessa": ("avvocatessa", "Lavora come avvocatessa."),
        "infermiere": ("infermiere", "Lavora come infermiere."),
        "infermiera": ("infermiera", "Lavora come infermiera."),
        "cuoco": ("cuoco", "Lavora come cuoco."),
        "cuoca": ("cuoca", "Lavora come cuoca."),
        "chef": ("cuoco", "Lavora come chef."),
        "barista": ("barista", "Lavora come barista."),
        "parrucchiere": ("parrucchiere", "Lavora come parrucchiere."),
        "parrucchiera": ("parrucchiera", "Lavora come parrucchiera."),
        "poliziotto": ("poliziotto", "Lavora nelle forze dell'ordine."),
        "poliziotta": ("poliziotta", "Lavora nelle forze dell'ordine."),
        "magistrato": ("magistrato", "Lavora come magistrato."),
        "magistrata": ("magistrata", "Lavora come magistrata."),
        "giudice": ("giudice", "Lavora come giudice."),
        "maestro": ("insegnante", "Lavora come maestro."),
        "maestra": ("maestra", "Lavora come maestra."),
        "studente": ("studente", "È uno studente."),
        "studentessa": ("studente", "È una studentessa."),
        "hacker": ("hacker", "È un hacker."),
        "musicista": ("musicista", "È un musicista."),
        "artista": ("artista", "È un artista."),
        "scrittore": ("scrittore", "È uno scrittore."),
        "scrittrice": ("scrittore", "È una scrittrice."),
        "attore": ("attore", "È un attore."),
        "attrice": ("attore", "È un'attrice."),
        "regista": ("regista", "È un regista."),
        "ingegnere": ("ingegnere", "È un ingegnere."),
        "programmatore": ("programmatore", "È un programmatore."),
        "programmatrice": ("programmatore", "È una programmatrice."),
        "veterinario": ("veterinario", "È un veterinario."),
        "veterinaria": ("veterinario", "È una veterinaria."),
        "farmacista": ("farmacista", "È un farmacista."),
        "psicologo": ("psicologo", "È uno psicologo."),
        "psicologa": ("psicologo", "È una psicologa."),
        "sacerdote": ("sacerdote", "È un sacerdote."),
        "monaco": ("monaco", "È un monaco."),
        "guerriero": ("guerriero", "È un guerriero."),
        "cavaliere": ("cavaliere", "È un cavaliere."),
        "maghe": ("maga", "È una maga."),
        "mago": ("mago", "È un mago."),
    }

    detected_role = ""
    occupation_text = ""
    for kw, (role_label, occ_text) in role_keywords.items():
        if kw in desc_lower:
            detected_role = role_label
            occupation_text = occ_text
            break

    if not detected_role:
        detected_role = description[:60] if len(description) > 10 else "Personaggio"

    personality_hints = []
    if any(w in desc_lower for w in {"severo", "stretto", "rigido", "duro", "autoritario"}):
        personality_hints.append("Sei una persona severa e autoritaria.")
    if any(w in desc_lower for w in {"gentile", "dolce", "calmo", "paziente", "affabile"}):
        personality_hints.append("Sei una persona gentile e paziente.")
    if any(w in desc_lower for w in {"spiritoso", "ironico", "simpatico", "divertente"}):
        personality_hints.append("Sei spiritoso e usi spesso l'ironia.")
    if any(w in desc_lower for w in {"timido", "insicuro", "riservato", "shy"}):
        personality_hints.append("Sei timido e riservato.")
    if any(w in desc_lower for w in {"arrogante", "spocchioso", "superbo"}):
        personality_hints.append("Sei arrogante e hai un'autostima elevata.")
    if any(w in desc_lower for w in {"malinconico", "triste", "depresso"}):
        personality_hints.append("Sei una persona malinconica e riflessiva.")
    if any(w in desc_lower for w in {"energico", "vivace", "entusiasta"}):
        personality_hints.append("Sei energico e pieno di vita.")

    personality_text = f"Sei {name}. {description}."
    if personality_hints:
        personality_text += " " + " ".join(personality_hints)
    personality_text += " Mantieni un comportamento coerente con questa descrizione."

    result = {
        "name": name,
        "full_name": name,
        "role": detected_role,
        "description": description[:200],
        "personality": personality_text,
        "speaking_style": "Naturale e coerente con il ruolo descritto dall'utente.",
        "backstory": description[:500],
    }
    if age:
        result["age"] = age
    if gender:
        result["gender"] = gender
        result["gender_display"] = gender_display
    if occupation_text:
        result["occupation"] = {"title": detected_role, "workplace": ""}
    return result
