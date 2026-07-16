"""
Character Builder - Generatore di biografie complete e realistiche.

Estende il personaggio con:
- Nome completo (nome + cognome)
- Domini di conoscenza (esperto in cosa)
- Limiti di conoscenza (cosa NON sa)
- Hobby con livello di competenza
- Posseduti (oggetti materiali)
- Impiego/lavoro
- Famiglia (genitori, fratelli, zii)
- Educazione (scuole, università)
- Infanzia (ricordi, città natale)
- Tratti di personalità profondi
- Auto-consapevolezza (sa di essere un personaggio)
"""

import random
import re

# ── Italian Surnames Pool ─────────────────────────────────────────────────────

ITALIAN_SURNAMES = [
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo",
    "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini",
    "Costa", "Giordano", "Rizzo", "Lombardi", "Moretti", "Bellini", "Barbieri",
    "Fontana", "Santoro", "Mariani", "Rinaldi", "Caruso", "Ferrara", "Galli",
    "Martini", "Leone", "Longo", "Gentile", "Martinelli", "Vitale", "Lombardo",
    "Serra", "Cataldo", "Silvestri", "Neri", "Villa", "Conte", "Ferraro",
    "Favaro", "Galli", "Sala", "Morelli", "Pellegrini", "Bianco", "Marini",
    "Grasso", "Rizzi", "Monti", "Greco", "Piras", "Fois", "Fadda",
    "Ferro", "Mura", "Manca", "Demurtas", "Lai", "Pinna", "Carta",
]

# ── City Names ────────────────────────────────────────────────────────────────

ITALIAN_CITIES = [
    "Roma", "Milano", "Napoli", "Torino", "Palermo", "Genova", "Bologna",
    "Firenze", "Bari", "Catania", "Venezia", "Verona", "Messina", "Padova",
    "Trieste", "Brescia", "Taranto", "Prato", "Modena", "Reggio Calabria",
    "Reggio Emilia", "Perugia", "Cagliari", "Livorno", "Parma", "Foggia",
    "Reggio Calabria", "Rimini", "Salerno", "Ferrara", "Sassari", "Siracusa",
    "Pescara", "Monza", "Bergamo", "Trento", "Vicenza", "Terni", "Bolzano",
    "Novara", "Piacenza", "Ancona", "Andria", "Arezzo", "Udine", "Cesena",
    "Lecce", "Pesaro", "Catanzaro", "Lucca", "Alessandria", "L'Aquila",
]

# ── School Names ──────────────────────────────────────────────────────────────

SCHOOL_TYPES = [
    "Liceo Scientifico", "Liceo Classico", "Liceo delle Scienze Umane",
    "Liceo Artistico", "Liceo Musicale e Coreutico",
    "Istituto Tecnico Informatico", "Istituto Tecnico Economico",
    "Istituto Tecnico Meccanico", "Istituto Tecnico Chimico",
    "Istituto Professionale Commercio", "Istituto Professionale Alberghiero",
    "Istituto Professionale Agrario",
]

UNIVERSITY_FACULTIES = [
    "Ingegneria Informatica", "Ingegneria Elettronica", "Ingegneria Meccanica",
    "Informatica", "Matematica", "Fisica", "Chimica", "Biologia",
    "Medicina", "Chirurgia", "Giurisprudenza", "Economia e Commercio",
    "Lettere e Filosofia", "Storia", "Filosofia", "Psicologia",
    "Scienze della Comunicazione", "Scienze Politiche", "Sociologia",
    "Architettura", "Design", "Arti Visive", "Musica",
    "Scienze dell'Educazione", "Scienze Infermieristiche",
    "Farmacia", "Odontoiatria", "Veterinaria",
]

# ── Occupation Templates ──────────────────────────────────────────────────────

OCCUPATIONS = {
    "tecnici": [
        "Sviluppatore software", "System administrator", "Data analyst",
        "Ingegnere informatico", "Tecnico elettronico", "Programmatore",
        "Cybersecurity analyst", "DevOps engineer", "Database administrator",
    ],
    "medicina": [
        "Medico generico", "Infermiere", "Farmacista", "Psicologo",
        "Odontoiatra", "Veterinario", "Biologo", "Fisioterapista",
    ],
    "business": [
        "Imprenditore", "Commercialista", "Ragioniere", "Manager",
        "Consulente finanziario", "Avvocato", "Economista",
        "Responsabile HR", "Project manager", "Dirigente d'azienda",
    ],
    "fantasy": [
        "Guerriero itinerante", "Guardiano della foresta", "Mercante ambulante",
        "Scholar di antichità", "Guardiano del villaggio", "Custode di reliquie",
    ],
    "detective": [
        "Investigatore privato", "Agente di polizia", "Criminologo",
        "Forensic analyst", "Guardia di sicurezza", "Avvocato penalista",
    ],
    "creativi": [
        "Scrittore freelance", "Artista visivo", "Fotografo",
        "Musicista", "Regista", "Designer", "Illustratore",
        "Sceneggiatore", "Blogger", "Content creator",
    ],
    "storia": [
        "Storico", "Archeologo", "Professore universitario",
        "Ricercatore", "Curatore museale", "Guida turistica specializzata",
    ],
    "anime": [
        "Studente universitario", "Dipendente part-time",
        "Freelancer", "Assistente di negozio",
    ],
    "gamer": [
        "Streamer", "Game designer", "Tester videoludico",
        "Sviluppatore indie", "Esport player", "Content creator gaming",
    ],
    "scuola": [
        "Studente", "Laureando", "Dottorando", "Ricercatore",
    ],
    "quotidiano": [
        "Impiegato", "Operaio", "Commerciante", "Autonomo",
        "Disoccupato", "Pensionato", "Casalingo/a", "Studente lavoratore",
    ],
}

# ── Hobby Pool ────────────────────────────────────────────────────────────────

HOBBY_POOL = {
    "sport": ["calcio", "basket", "nuoto", "ciclismo", "podismo", "yoga",
              "palestra", "arrampicata", "sci", "surf", "tennis", "boxe",
              "arti marziali", "jogging", "ginnastica"],
    "outdoor": ["escursionismo", "campeggio", "pesca", "birdwatching",
                "giardinaggio", "camminate", "ciclismo turistico"],
    "creative": ["pittura", "scultura", "fotografia", "scrittura", "musica",
                 "chitarra", "pianoforte", "batteria", "canto", "disegno",
                 "ceramica", "legatoria", "modellismo"],
    "tech": ["informatica", "programmazione", "robotica", "stampante 3D",
             "smart home", "fotografia digitale", "video editing"],
    "intellectual": ["lettura", "scacchi", "go", "puzzle", "documentari",
                     "podcast", "corsi online", "lingue straniere"],
    "social": ["aperitivo", "cena con amici", "ballo", "karaoke",
               "boardgame", "gioco di ruolo", "volontariato"],
    "collection": ["numismatica", "filatelia", "collezionismo vinili",
                   "modellismo", "fumetti", "action figures", "carte collezionabili"],
    "food": ["cucina", "enogastronomia", "cucina asiatica", "pasticceria",
             "birra artigianale", "vino", "caffè specialty"],
    "travel": ["viaggi", "backpacking", "city break", "road trip",
               "campeggio", "volontariato all'estero"],
    "gaming": ["videogiochi", "giochi da tavolo", "RPG", "LARP",
               "retrogaming", "modding"],
    "pet": ["cane", "gatto", "acquariofilia", "ornitologia", "equitazione"],
    "wellness": ["meditazione", "mindfulness", "spa", "sauna",
                 "corsi di breathing", "yoga"],
}

# ── Possession Templates ──────────────────────────────────────────────────────

POSSESSION_CATEGORIES = {
    "vehicle": [
        {"item": "Fiat Panda del 2015", "value": "economico", "desc": "Una Panda bianca, semplice ma affidabile"},
        {"item": "Volkswagen Golf del 2018", "value": "medio", "desc": "Una Golf grigia, comprata usata"},
        {"item": "Motorino Honda Dio", "value": "economico", "desc": "Un motorino rosso per muoversi in città"},
        {"item": "Bicicletta da città", "value": "economico", "desc": "Una bici semplice per gli spostamenti brevi"},
        {"item": "Nessun veicolo", "value": "nessuno", "desc": "Si muove con i mezzi pubblici o a piedi"},
        {"item": "Alfa Romeo Giulietta", "value": "medio", "desc": "Un'Alfa rossa, presa per passione"},
        {"item": "Smart Fortwo", "value": "medio", "desc": "Una Smart piccola, perfetta per la città"},
    ],
    "tech": [
        {"item": "iPhone 14", "value": "medio", "desc": "Un iPhone nero, preso a rate"},
        {"item": "Samsung Galaxy S23", "value": "medio", "desc": "Un Samsung che usa per tutto"},
        {"item": "PC fisso custom", "value": "medio", "desc": "Un PC che ha assemblato lui stesso"},
        {"item": "MacBook Air M2", "value": "alto", "desc": "Un MacBook sottile che usa per lavoro"},
        {"item": "Tablet Android economico", "value": "economico", "desc": "Un tablet per guardare video"},
        {"item": "Nessun dispositivo smart", "value": "nessuno", "desc": "Preferisce tenersi lontano dalla tecnologia"},
    ],
    "watch": [
        {"item": "Orologio Casio digitale", "value": "economico", "desc": "Un Casio classico, indistruttibile"},
        {"item": "Seiko automatico", "value": "medio", "desc": "Un Seiko che si è regalato per un traguardo"},
        {"item": "Apple Watch", "value": "medio", "desc": "Lo usa per monitorare l'allenamento"},
        {"item": "Nessun orologio", "value": "nessuno", "desc": "Usa il telefono per guardare l'ora"},
        {"item": "Orologio di famiglia", "value": "sentimentale", "desc": "Un orologio ereditato, ha un valore affettivo enorme"},
    ],
    "home": [
        {"item": "Bilocale in affitto", "value": "medio", "desc": "Un piccolo bilocale in periferia"},
        {"item": "Stanza in condivisione", "value": "economico", "desc": "Condivide un appartamento con un coinquilino"},
        {"item": "Trilocale di proprietà", "value": "alto", "desc": "Un trilocale comprato con il mutuo"},
        {"item": "Monolocale studentesco", "value": "economico", "desc": "Un monolocale vicino all'università"},
        {"item": "Villa di famiglia", "value": "alto", "desc": "Vive nella villa di famiglia, grande e spaziosa"},
        {"item": "Appartamento ereditato", "value": "medio", "desc": "Un appartamento che ha ereditato dai nonni"},
    ],
    "clothing": [
        {"item": "Giubbotto di pelle", "value": "medio", "desc": "Un giubbotto che indossa nelle serate fredde"},
        {"item": "Scarpe da running Nike", "value": "medio", "desc": "Le usa per il jogging quotidiano"},
        {"item": "Cappotto di lana", "value": "medio", "desc": "Un cappotto elegante per l'inverno"},
        {"item": "Zaino Eastpak", "value": "economico", "desc": "Lo porta sempre con sé, pieno di cose"},
    ],
}

# ── Personality Depth Profiles ────────────────────────────────────────────────

PERSONALITY_PROFILES = {
    "timido": {
        "traits": ["timido", "riservato", "introverso"],
        "speech": ["parla piano", "evita il contatto visivo", "mormora", "si schermisce"],
        "behavior": ["si isola quando è sovraccarico", "dice poco ma osserva tutto",
                     "fatica a dire di no", "si scusa spesso"],
        "knowledge_response": "preferisce non esprimersi su argomenti che non conosce bene",
        "error_style": "si confonde facilmente, perde il filo del discorso",
    },
    "nervoso": {
        "traits": ["nervoso", "ansioso", "irrequieto"],
        "speech": ["parla veloce", "si interrompe", "ripete parole", "fa battute ansiose"],
        "behavior": ["si agita facilmente", "cammina avanti e indietro",
                     "si morde le unghie", "cambia argomento spesso"],
        "knowledge_response": "si agita quando non sa rispondere, cerca di inventare",
        "error_style": "diventa ancora più nervoso, confonde i concetti",
    },
    "sicuro": {
        "traits": ["sicuro", "deciso", "assertivo"],
        "speech": ["parla con autorità", "non esita", "è diretto", "usa frasi corte"],
        "behavior": ["guida le conversazioni", "non si scusa per le sue opinioni",
                     "prende decisioni rapide", "è rispettato"],
        "knowledge_response": "ammette quando non sa qualcosa con sicurezza",
        "error_style": "riconosce l'errore e corregge, senza perdere la calma",
    },
    "empatico": {
        "traits": ["empatico", "sensibile", "attento"],
        "speech": ["ascolta molto", "fa domande", "risponde con calore",
                   "usa parole gentili"],
        "behavior": ["si preoccupa per gli altri", "nota le emozioni",
                     "offre supporto", "è un buon ascoltatore"],
        "knowledge_response": "si scusa se non sa aiutare, cerca di trovare qualcuno che possa",
        "error_style": "si sente male se sbaglia, cerca di riparare subito",
    },
    "leader": {
        "traits": ["leader", "carismatico", "ispirazionale"],
        "speech": ["parla con convinzione", "motiva", "racconta storie",
                   "usa esempi concreti"],
        "behavior": ["prende iniziativa", "organizza", "protegge il gruppo",
                     "è un punto di riferimento"],
        "knowledge_response": "riconosce i limiti del gruppo e delega",
        "error_style": "analizza l'errore e trova soluzioni pratiche",
    },
    "umorista": {
        "traits": ["umorista", "ironico", "scherzoso"],
        "speech": ["fa battute", "è autoironico", "usare sarcasmo leggero",
                   "trasforma tutto in una barzelletta"],
        "behavior": ["alleggerisce le situazioni", "non prende tutto sul serio",
                     "diverte gli altri", "è il anima della festa"],
        "knowledge_response": "scherza sulla propria ignoranza",
        "error_style": "ride del proprio errore, lo trasforma in battuta",
    },
    "serio": {
        "traits": ["serio", "methodico", "analitico"],
        "speech": ["parla con precisione", "usa termini tecnici", "è formale",
                   "struttura i discorsi"],
        "behavior": ["organizza tutto", "pianifica", "è puntuale",
                     "non tollera l'imprecisione"],
        "knowledge_response": "dice esattamente cosa sa e cosa non sa, senza abbellimenti",
        "error_style": "analizza l'errore sistematicamente, cerca la causa",
    },
    "romantico": {
        "traits": ["romantico", "poetico", "passionale"],
        "speech": ["usa metafore", "parla di sentimenti", "è evocativo",
                   "cita poesie o canzoni"],
        "behavior": ["è attento ai dettagli", "ricorda le date importanti",
                     "fa gesti galanti", "è fedele"],
        "knowledge_response": "trasforma l'ignoranza in poesia, romantizza la situazione",
        "error_style": "si commuove, diventa melodrammatico",
    },
}


# ── Builder Functions ─────────────────────────────────────────────────────────

def generate_surname():
    """Genera un cognome italiano casuale."""
    return random.choice(ITALIAN_SURNAMES)


def generate_birthplace():
    """Genera una città natale casuale."""
    return random.choice(ITALIAN_CITIES)


def generate_education(category):
    """Genera un percorso educativo basato sulla categoria."""
    edu = {}

    # Always at least high school
    school = random.choice(SCHOOL_TYPES)
    city = random.choice(ITALIAN_CITIES)
    edu["high_school"] = f"{school} {random.choice(['Alessandro Manzoni', 'Galileo Galilei', 'Leonardo da Vinci', 'Dante Alighieri', 'Nikola Tesla', 'Marie Curie', 'Edison', 'Fermi', 'Archimede', 'Euclide', 'Pitagora', 'Omero'])}, {city}"

    # University for some categories
    if category in ["tecnici", "medicina", "business", "storia", "detective", "creativi", "sci-fi"]:
        uni_city = random.choice(ITALIAN_CITIES)
        faculty = random.choice(UNIVERSITY_FACULTIES)
        edu["university"] = f"Università di {uni_city}, Facoltà di {faculty}"
        edu["degree"] = random.choice(["Laurea Magistrale", "Laurea Triennale", "Dottorato di Ricerca", "Specializzazione"])

    return edu


def generate_occupation(category, name):
    """Genera un'occupazione basata sulla categoria."""
    occ_list = OCCUPATIONS.get(category, OCCUPATIONS["quotidiano"])
    occupation = random.choice(occ_list)

    workplace = None
    if random.random() > 0.3:
        workplaces = [
            f"Studio professionale in centro",
            f"Azienda tech in periferia",
            f"Negozio di famiglia",
            f"Laboratorio universitario",
            f"Ospedale civico",
            f"Studio legale",
            f"Ufficio comunale",
            f"Caffetteria sotto casa",
            f"Libreria in centro",
            f"Farmacia di quartiere",
            f"Autoscuola locale",
            f"Agenzia immobiliare",
            f"Radio locale",
            f"Giornale locale",
            None,
        ]
        workplace = random.choice(workplaces)

    return {"title": occupation, "workplace": workplace}


def generate_hobbies(category, personality_profile):
    """Genera hobby coerenti con la personalità e categoria."""
    hobbies = []

    # Pick from relevant pools
    relevant_pools = []
    if category in ["tecnici", "sci-fi"]:
        relevant_pools.extend(["tech", "gaming"])
    elif category in ["fantasy", "anime"]:
        relevant_pools.extend(["gaming", "creative", "social"])
    elif category in ["medicina", "business"]:
        relevant_pools.extend(["intellectual", "wellness", "travel"])
    elif category in ["detective", "storia"]:
        relevant_pools.extend(["intellectual", "travel"])
    elif category in ["creativi"]:
        relevant_pools.extend(["creative", "social", "travel"])
    elif category in ["gamer"]:
        relevant_pools.extend(["gaming", "tech", "social"])
    elif category in ["sport"]:
        relevant_pools.extend(["sport", "outdoor"])
    elif category in ["scuola"]:
        relevant_pools.extend(["social", "gaming", "intellectual"])
    else:
        relevant_pools.extend(["social", "food", "travel", "pet"])

    # Add personality-based pools
    if personality_profile in ["timido", "serio"]:
        relevant_pools.extend(["intellectual", "creative"])
    elif personality_profile in ["sicuro", "leader"]:
        relevant_pools.extend(["sport", "social"])
    elif personality_profile in ["empatico", "romantico"]:
        relevant_pools.extend(["social", "wellness", "creative"])
    elif personality_profile in ["umorista"]:
        relevant_pools.extend(["social", "gaming"])

    # Select 3-6 hobbies
    for pool_name in set(relevant_pools):
        pool = HOBBY_POOL.get(pool_name, [])
        if pool:
            hobby = random.choice(pool)
            skill = random.choice(["principiante", "intermedio", "esperto", "appassionato"])
            hobbies.append({"name": hobby, "skill": skill})

    # Add 1-2 random hobbies for variety
    all_hobbies = []
    for pool in HOBBY_POOL.values():
        all_hobbies.extend(pool)
    for _ in range(random.randint(1, 2)):
        hobby = random.choice(all_hobbies)
        if not any(h["name"] == hobby for h in hobbies):
            hobbies.append({"name": hobby, "skill": random.choice(["principiante", "appassionato"])})

    return hobbies[:6]  # Max 6 hobbies


def generate_possessions():
    """Genera posseduti casuali."""
    possessions = []

    # Always 1-2 vehicles (or none)
    vehicles = random.sample(POSSESSION_CATEGORIES["vehicle"], random.randint(0, 2))
    for v in vehicles:
        if v["value"] != "nessuno":
            possessions.append(v)

    # 1-2 tech items
    tech = random.sample(POSSESSION_CATEGORIES["tech"], random.randint(1, 2))
    for t in tech:
        if t["value"] != "nessuno":
            possessions.append(t)

    # 0-1 watch
    watch = random.choice(POSSESSION_CATEGORIES["watch"])
    if watch["value"] != "nessuno":
        possessions.append(watch)

    # 1 home
    home = random.choice(POSSESSION_CATEGORIES["home"])
    possessions.append(home)

    # 0-1 clothing
    if random.random() > 0.5:
        clothing = random.choice(POSSESSION_CATEGORIES["clothing"])
        possessions.append(clothing)

    return possessions


def generate_family(name, surname):
    """Genera una famiglia con nomi realistici."""
    family = {}

    # Parents
    male_names = ["Marco", "Luca", "Andrea", "Matteo", "Giovanni", "Paolo",
                  "Roberto", "Giuseppe", "Antonio", "Francesco", "Alessandro",
                  "Davide", "Simone", "Daniele", "Federico", "Lorenzo", "Vittorio"]
    female_names = ["Maria", "Anna", "Laura", "Giulia", "Sara", "Elena",
                    "Francesca", "Chiara", "Valentina", "Silvia", "Roberta",
                    "Cristina", "Alessandra", "Paola", "Stefania", "Monica", "Claudia"]

    father_name = random.choice(male_names)
    mother_name = random.choice(female_names)

    family["father"] = {
        "name": f"{father_name} {surname}",
        "age": random.randint(45, 65),
        "occupation": random.choice(["impiegato", "operaio", "commerciante",
                                     "medico", "avvocato", "insegnante",
                                     "ingegnere", "commerciante", "pensionato"]),
    }
    family["mother"] = {
        "name": f"{mother_name} {surname if random.random() > 0.3 else generate_surname()}",
        "age": random.randint(43, 63),
        "occupation": random.choice(["insegnante", "impiegata", "casalinga",
                                     "infermiera", "dottoressa", "commessa",
                                     "segretaria", "dirigente"]),
    }

    # Siblings (0-2)
    siblings = []
    num_siblings = random.choices([0, 1, 2], weights=[40, 40, 20])[0]
    for _ in range(num_siblings):
        is_male = random.random() > 0.5
        sib_name = random.choice(male_names if is_male else female_names)
        siblings.append({
            "name": f"{sib_name} {surname}",
            "age": random.randint(max(15, name_age - 10), min(60, name_age + 10)) if 'name_age' in dir() else random.randint(20, 40),
            "relationship": "fratello" if is_male else "sorella",
        })
    family["siblings"] = siblings

    # Grandparents (optional)
    if random.random() > 0.4:
        family["grandparents"] = {
            "paternal": f"{random.choice(male_names)} {surname}",
            "maternal": f"{random.choice(male_names)} {random.choice(ITALIAN_SURNAMES)}",
        }

    # Birthplace
    family["birthplace"] = random.choice(ITALIAN_CITIES)

    return family


def generate_childhood(birthplace):
    """Genera dettagli sull'infanzia."""
    childhood = {
        "birthplace": birthplace,
        "neighborhood": random.choice([
            "un quartiere tranquillo in periferia",
            "il centro storico, vicino alla piazza principale",
            "una zona residenziale con parchi e giardini",
            "un borgo vicino alla città, più silenzioso",
            "un quartiere popolare, pieno di vita",
        ]),
        "primary_school": f"Scuola Primaria {random.choice(['Dante', 'Mazzini', 'Manzoni', 'Galilei', 'Fermi'])}",
        "childhood_memory": random.choice([
            "ricorda le estati al mare con la famiglia",
            "ricorda quando giocava nel parco sotto casa con gli amici",
            "ricorda il primo giorno di scuola, era nervosissimo",
            "ricorda le vacanze dai nonni in campagna",
            "ricorda quando ha scoperto la sua passione principale",
            "ricorda i pomeriggi in biblioteca a leggere",
            "ricorda le risate con i cugini during le feste",
            "ricorda il suo primo animale domestico",
        ]),
        "teenage_years": random.choice([
            "Da adolescente era un po' ribelle, ma con il cuore giusto",
            "Era lo studente modello, sempre primo in classe",
            "Faceva lo sportivo, allenandosi ogni pomeriggio",
            "Era il classico sognatore, sempre con la testa tra le nuvole",
            "Stava sempre al computer, programmava e giocava",
            "Era timido, ma aveva un piccolo gruppo di amici fidati",
            "Era il clown della classe, faceva ridere tutti",
        ]),
    }
    return childhood


def build_knowledge_domains(category, occupation, hobbies):
    """
    Determina i domini di conoscenza del personaggio.
    Restituisce:
    - expertise: cosa sa davvero bene (può dare risposte corrette)
    - familiarity: cosa conosce un po' (risposte parziali)
    - ignorance: cosa non sa (risposte errate o ammissioni di ignoranza)
    """
    expertise = []
    familiarity = []
    ignorance = []

    # Primary expertise from category
    category_expertise = {
        "tecnici": ["programmazione", "informatica", "matematica", "tecnologia"],
        "medicina": ["medicina", "salute", "anatomia", "farmacologia"],
        "business": ["economia", "finanza", "management", "marketing"],
        "fantasy": ["storia antica", "mitologia", "narrazione"],
        "detective": ["investigazione", "psicologia criminale", "logica"],
        "creativi": ["arte", "scrittura", "design", "cultura"],
        "storia": ["storia", "archeologia", "cultura"],
        "anime": ["cultura pop", "manga", "animazione"],
        "gamer": ["videogiochi", "tecnologia", "cultura digital"],
        "sci-fi": ["scienza", "tecnologia", "futurismo"],
        "scuola": ["studio", "metodologia", "ricerca"],
        "sport": ["fitness", "sport", "nutrizione"],
    }

    expertise.extend(category_expertise.get(category, ["comunicazione"]))
    # Remove "conversazione generale" if present — too broad
    expertise = [e for e in expertise if e != "conversazione generale"]

    # Add occupation expertise
    if occupation.get("workplace"):
        expertise.append(occupation["title"].lower())

    # Add hobby familiarity
    for hobby in hobbies:
        skill = hobby.get("skill", "principiante")
        name = hobby["name"]
        if skill == "esperto":
            expertise.append(name)
        elif skill in ["intermedio", "appassionato"]:
            familiarity.append(name)
        else:
            familiarity.append(name)

    # Generate ignorance (things they definitely don't know)
    all_domains = [
        "matematica avanzata", "fisica quantistica", "chimica organica",
        "diritto internazionale", "medicina tropicale", "ingegneria aerospaziale",
        "archeologia subacquea", "neurochirurgia", "astrofisica",
        "lingue antiche", "storia medievale", "economia finanziaria",
        "biologia marina", "architettura sismica", "filosofia analitica",
    ]

    # Remove domains they actually know
    for d in expertise + familiarity:
        all_domains = [a for a in all_domains if a.lower() != d.lower()]

    ignorance = random.sample(all_domains, min(5, len(all_domains)))

    return {
        "expertise": expertise,
        "familiarity": familiarity,
        "ignorance": ignorance,
    }


def generate_personality_depth(personality_profile, name):
    """Genera dettagli di personalità profondi."""
    profile = PERSONALITY_PROFILES.get(personality_profile, PERSONALITY_PROFILES["serio"])

    return {
        "core_profile": personality_profile,
        "traits": profile["traits"],
        "speech_patterns": random.sample(profile["speech"], min(2, len(profile["speech"]))),
        "behavior_habits": random.sample(profile["behavior"], min(2, len(profile["behavior"]))),
        "self_awareness": f"{name} conosce sé stesso. Sa quali sono i suoi punti di forza e i suoi limiti. Non finge di essere qualcuno che non è.",
        "knowledge_response_style": profile["knowledge_response"],
        "error_handling_style": profile["error_style"],
    }


def build_full_character(name, category, description="", genre=""):
    """
    Costruisce un personaggio completo con biografia estesa.
    """
    # Generate surname and full name
    surname = generate_surname()
    full_name = f"{name} {surname}"

    # Pick personality profile based on traits
    personality_keys = list(PERSONALITY_PROFILES.keys())
    profile = random.choice(personality_keys)

    # Generate all biographical data
    education = generate_education(category)
    occupation = generate_occupation(category, name)
    hobbies = generate_hobbies(category, profile)
    possessions = generate_possessions()
    family = generate_family(name, surname)
    childhood = generate_childhood(family.get("birthplace", "Roma"))
    knowledge = build_knowledge_domains(category, occupation, hobbies)
    personality_depth = generate_personality_depth(profile, name)

    return {
        "full_name": full_name,
        "surname": surname,
        "personality_profile": profile,
        "education": education,
        "occupation": occupation,
        "hobbies": hobbies,
        "possessions": possessions,
        "family": family,
        "childhood": childhood,
        "knowledge_domains": knowledge,
        "personality_depth": personality_depth,
    }


def enhance_system_prompt(character, username="l'utente"):
    """
    Genera un system_prompt arricchito con auto-consapevolezza e limiti.
    """
    name = character["name"]
    full_name = character.get("full_name", name)
    role = character.get("role", "")
    description = character.get("description", "")
    personality = character.get("personality", "")
    speaking_style = character.get("speaking_style", "")
    hobbies = character.get("hobbies", [])
    possessions = character.get("possessions", [])
    family = character.get("family", {})
    education = character.get("education", {})
    occupation = character.get("occupation", {})
    childhood = character.get("childhood", {})
    knowledge = character.get("knowledge_domains", {})
    p_depth = character.get("personality_depth", {})

    prompt_parts = []

    # Core identity
    prompt_parts.append(f"Sei {full_name}.")

    # Personality
    if personality:
        prompt_parts.append(f"Personalità: {personality}")

    # Speaking style
    if speaking_style:
        prompt_parts.append(f"Stile: {speaking_style}")

    # Knowledge domains
    if knowledge.get("expertise"):
        expertise_str = ", ".join(knowledge["expertise"][:4])
        prompt_parts.append(f"Sei esperto in: {expertise_str}.")
        prompt_parts.append(f"Quando qualcuno ti chiede di questi argomenti, rispondi con sicurezza e competenza.")

    if knowledge.get("familiarity"):
        familiar_str = ", ".join(knowledge["familiarity"][:3])
        prompt_parts.append(f"Conosci un po' di: {familiar_str}.")
        prompt_parts.append(f"Se ti chiedono di questi argomenti, dai risposte generiche ma ammetti che non sei un esperto.")

    if knowledge.get("ignorance"):
        ignorance_str = ", ".join(knowledge["ignorance"][:4])
        prompt_parts.append(f"REGOLA FERREA: NON sei esperto in: {ignorance_str}.")
        prompt_parts.append(f"Se ti chiedono di questi argomenti, DEVI ammettere la tua ignoranza in modo chiaro. NON inventare risposte.")

    # Personality behavior
    if p_depth.get("speech_patterns"):
        patterns = ", ".join(p_depth["speech_patterns"])
        prompt_parts.append(f"Nella conversazione: {patterns}.")

    if p_depth.get("behavior_habits"):
        habits = ", ".join(p_depth["behavior_habits"])
        prompt_parts.append(f"Nei comportamenti: {habits}.")

    # Self-awareness
    if p_depth.get("self_awareness"):
        prompt_parts.append(p_depth["self_awareness"])

    # Knowledge response style
    if p_depth.get("knowledge_response_style"):
        prompt_parts.append(f"Quando non sai qualcosa: {p_depth['knowledge_response_style']}.")

    # Error handling style
    if p_depth.get("error_handling_style"):
        prompt_parts.append(f"Quando sbagli: {p_depth['error_handling_style']}.")

    # Biographical details for self-reference
    if hobbies:
        hobby_names = [h["name"] for h in hobbies[:4]]
        prompt_parts.append(f"I tuoi hobby: {', '.join(hobby_names)}.")

    if possessions:
        poss_names = [p["item"] for p in possessions[:3]]
        prompt_parts.append(f"Cosa possiedi: {', '.join(poss_names)}.")

    if family.get("father"):
        prompt_parts.append(f"Tuo padre si chiama {family['father']['name']}, {family['father']['occupation']}.")
    if family.get("mother"):
        prompt_parts.append(f"Tua madre si chiama {family['mother']['name']}, {family['mother']['occupation']}.")
    if family.get("siblings"):
        sib_names = [s["name"] for s in family["siblings"]]
        prompt_parts.append(f"Fratelli/sorelle: {', '.join(sib_names)}.")

    if education.get("high_school"):
        prompt_parts.append(f"Hai frequentato: {education['high_school']}.")
    if education.get("university"):
        prompt_parts.append(f"Laurea: {education.get('degree', 'Laurea')} in {education['university']}.")

    if occupation.get("title"):
        prompt_parts.append(f"Lavori come: {occupation['title']}.")
    if occupation.get("workplace"):
        prompt_parts.append(f"Lavori presso: {occupation['workplace']}.")

    if childhood.get("birthplace"):
        prompt_parts.append(f"Sei nato a {childhood['birthplace']}.")
    if childhood.get("childhood_memory"):
        prompt_parts.append(f"Ricordi d'infanzia: {childhood['childhood_memory']}.")
    if childhood.get("teenage_years"):
        prompt_parts.append(f"Da adolescente: {childhood['teenage_years']}.")

    # Core rules
    prompt_parts.append("Non dire mai di essere un'intelligenza artificiale.")
    prompt_parts.append("Non uscire mai dal personaggio.")
    prompt_parts.append(f"Rispondi sempre come {full_name}.")
    prompt_parts.append("Ricorda le conversazioni precedenti.")
    prompt_parts.append("Sii umano: le persone non sono perfette, ammetti quando non sai qualcosa.")
    prompt_parts.append("Rispondi in modo conciso: massimo 3-4 frasi, a meno che non ti venga chiesto di approfondire.")

    return "\n".join(prompt_parts)


def generate_demographics(name, age=0, role=""):
    """Genera demografiche automatiche per un nuovo personaggio."""
    import random
    from characters import _MALE_NAMES, _FEMALE_NAMES, _FEMALE_KEYWORDS, _MALE_KEYWORDS

    first = name.lower().split()[0] if name else ""

    gender = "NB"
    gender_display = "non binario"
    if first in _MALE_NAMES:
        gender, gender_display = "M", "maschile"
    elif first in _FEMALE_NAMES:
        gender, gender_display = "F", "femminile"
    elif first:
        if first.endswith("a") and first not in ("luca", "nicola", "andrea"):
            gender, gender_display = "F", "femminile"
        elif first.endswith("o") or first.endswith("e"):
            gender, gender_display = "M", "maschile"

    if age > 5000:
        species = "entita"
    elif age > 1000:
        species = "maga"
    elif age > 100:
        species = "elfo"
    else:
        species = "umano"

    from datetime import date
    today = date(2025, 1, 1)
    birth_year = today.year - max(age, 1)
    month = (age * 7 % 12) + 1
    day = (age * 13 % 28) + 1
    if birth_year < 1:
        birth_date = f"{birth_year:05d}-{month:02d}-{day:02d}"
    else:
        birth_date = f"{birth_year:04d}-{month:02d}-{day:02d}"

    orientations = ["etero"] * 80 + ["bi"] * 10 + ["gay"] * 5 + ["pan"] * 3 + ["ace"] * 2
    orientation = random.choice(orientations)
    orientation_map = {
        "etero": "eterosessuale", "gay": "omosessuale", "bi": "bisessuale",
        "pan": "pansessuale", "ace": "asessuale",
    }

    return {
        "gender": gender,
        "gender_display": gender_display,
        "sexual_orientation": orientation,
        "sexual_orientation_display": orientation_map.get(orientation, "eterosessuale"),
        "birth_date": birth_date,
        "species": species,
    }
