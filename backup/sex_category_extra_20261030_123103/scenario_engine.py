"""
Scenario Engine — gestisce la suddivisione dei personaggi in tre modalità:
  - immediate:  scenario roleplay da primo messaggio
  - deferred:   presentazione iniziale, RP dopo N messaggi
  - static:     mai roleplay, sempre consulenziale

La classificazione avviene per categoria + ruolo. I singoli personaggi
possono sempre forzare la loro modalità aggiungendo al proprio dict:
    "scenario_mode": "immediate" | "deferred" | "static"
"""

import logging

logger = logging.getLogger(__name__)


# ─── Categorie → modalità di default ──────────────────────────────
# immediate  = roleplay da subito, scenario narrativo da primo messaggio
# deferred   = presentazione professionale, RP dopo ~10 messaggi
# static     = mai roleplay, assistente/consulente puro
#
CATEGORY_MODE = {
    # RP immediato
    "romantici":      "immediate",
    "fantasy":        "immediate",
    "horror":         "immediate",
    "anime":          "immediate",
    "gamer":          "immediate",
    "detective":      "immediate",
    "supereroi":      "immediate",
    "sci-fi":         "immediate",
    "sopravvivenza":  "immediate",
    "creativi":       "immediate",
    "intrattenimento":"immediate",
    "storia":         "immediate",
    "viaggi":         "immediate",
    # Adult
    "flirt":          "immediate",
    "seduzione":      "immediate",
    "relazioni":      "immediate",
    "confessioni":    "immediate",
    # Tutte le categorie ora usano immediate
    "scuola":         "immediate",
    "medicina":       "immediate",
    "business":       "immediate",
    "motivazione":    "immediate",
    "tecnologia":     "immediate",
    "tecnici":        "immediate",
    "cucina":         "immediate",
    "sport":          "immediate",
    "esperti":        "immediate",
    "premium":        "immediate",
    "quotidiano":     "immediate",
    "per_te":         "immediate",
    "speciale":       "immediate",
    "amicizia":       "immediate",
}


# ─── Pattern di ruolo per override per-personaggio ─────────────────
# Se il ruolo contiene una di queste parole chiave, forziamo la modalità
# (utile per personaggi importati da HF che finiscono in categorie miste)
#
ROLE_FORCE_IMMEDIATE = [
    "studentess", "studente", "scolaro", "scolara",
    "ragazza", "ragazzo", "protagonista", "eroe", "eroina",
    "guerriero", "maga", "mago", "elfo", "elfica", "incantatrice",
    "vampiro", "licantropo", "demone", "angelo", "strega",
    "pirata", "cacciatrice", "cacciatore", "avventuriera", "avventuriero",
    "superero", "vigliant", "investigatrice", "investigatore",
    "spia", "agente", "kapo", "ribelle", "rivoluzionaria",
    "regina", "re", "principessa", "principe", "imperatrice", "imperatore",
    "stratega", "filosofo", "poeta", "artista", "pittrice", "pittore",
    "musicista", "cantante", "danzatrice", "ballerino",
    "scienziata pazzo", "scienziato pazzo", "inventrice", "inventore",
    " detective", "poliziotto", "poliziotta",
    "post-apocal", "apocalittic", "zombie", "survival",
]

ROLE_FORCE_DEFERRED = [
    "professor", "professoress", "insegnante", "docente",
    "tutor", "maestro", "istruttore", "istruttrice",
    "allenatore", "allenatrice", "coach", "trainer",
    "medico", "dottoressa", "dottore", "chirurgo",
    "avvocato", "commercialista", "consulente",
    "psicolog", "terapista", "nutritionist",
    "chirurgo", "ostetrica", "infermiera", "infermiere",
    "guida", "assistente",
]


def classify_character(character):
    """
    Ritorna la modalità scenario di un personaggio.
    Possoiono forzarla nel dict del personaggio: 'scenario_mode'.
    """
    # Override esplicito nel dict
    explicit = character.get("scenario_mode")
    if explicit in ("immediate", "deferred", "static"):
        return explicit

    # Override per ruolo (ha la precedenza sulla categoria)
    role = (character.get("role") or "").lower()
    for kw in ROLE_FORCE_IMMEDIATE:
        if kw in role:
            return "immediate"
    for kw in ROLE_FORCE_DEFERRED:
        if kw in role:
            return "deferred"

    # Default per categoria
    cat = character.get("category", "")
    return CATEGORY_MODE.get(cat, "deferred")


def get_opening_scenario(character, total_messages, user_gender=None, user_age=None, sexual_orientation=None):
    """
    Ritorna una stringa scenario da prependare al system prompt.
    - "" se static o se deferred non ancora attivo
    - scenario testuale negli altri casi

    Se il personaggio ha 'opening_scenario' definito, usa quello.
    Altrimenti genera uno scenario generico basato su categoria/ruolo.

    user_gender: "male" / "female" / None (sconosciuto)
    user_age: età numerica o None
    """
    mode = classify_character(character)

    if mode == "static":
        return ""

    if mode == "deferred":
        # Il RP si attiva solo dopo defer_threshold messaggi
        threshold = character.get("defer_threshold", 10)
        if total_messages < threshold:
            return ""  # fase di presentazione, niente scenario
        # soglia raggiunta → passa alla fase RP
        return _generate_scenario(character, active=True, user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation)

    # immediate
    return _generate_scenario(character, active=True, user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation)


def _user_age_range(age):
    """Converte età numerica in fascia d'età testuale."""
    if age is None:
        return ""
    if age < 15:
        return "giovane (preadolescenziale)"
    if age < 18:
        return "giovane (minorenne)"
    if age < 25:
        return "giovane"
    if age < 35:
        return "giovane adulto"
    if age < 50:
        return "adulto"
    if age < 65:
        return "middle-aged"
    return "anziano"


def _select_variant(variants, user_gender, user_age):
    """Seleziona la variante di scenario più appropriata basata su genere/età."""
    if not variants:
        return None

    # Se non abbiamo info sull'utente, usa "unknown"
    if not user_gender and not user_age:
        return variants.get("unknown")

    # Cerca variante specifica per genere+età
    if user_gender and user_age:
        age = int(user_age)
        if user_gender == "female":
            if age < 25:
                return variants.get("female_under_25")
            elif age < 40:
                return variants.get("female_25_40")
            else:
                return variants.get("female_over_40")
        elif user_gender == "male":
            return variants.get("male_partner")

    # Fallback: cerca variante per solo genere
    if user_gender == "female":
        return variants.get("female_under_25") or variants.get("female_25_40") or variants.get("female_over_40")
    elif user_gender == "male":
        return variants.get("male_partner")

    return variants.get("unknown")


def _format_variant(variant, user_gender, user_age, sexual_orientation=None):
    """Formatta una variante con le variabili del template."""
    gender_map = {"male": "maschile", "female": "femminile"}
    gender_text = gender_map.get(user_gender, "")
    age_range = _user_age_range(user_age)
    try:
        return variant.format(
            user_gender=user_gender or "",
            user_gender_text=gender_text,
            user_age=user_age or "",
            user_age_range=age_range,
            sexual_orientation=sexual_orientation or "",
        )
    except (KeyError, IndexError):
        return variant


def _default_adaptive(character, user_gender, user_age, sexual_orientation=None):
    """Genera un testo adaptivo di default quando non ci sono varianti."""
    name = character.get("name", "il personaggio")
    role = character.get("role", "")
    gender_map = {"male": "maschile", "female": "femminile"}
    gender_text = gender_map.get(user_gender, "")
    age_range = _user_age_range(user_age)
    parts = []
    if gender_text:
        parts.append(f"L'utente è {gender_text}")
    if user_age:
        parts.append(f"di {user_age} anni ({age_range})")
    if sexual_orientation:
        parts.append(f"orientamento {sexual_orientation}")
    if parts:
        return f"{name} accoglie l'utente ({', '.join(parts)}) in modo professionale."
    return ""


def _generate_scenario(character, active=True, user_gender=None, user_age=None, sexual_orientation=None):
    """
    Genera uno scenario testuale. Se il personaggio ne ha uno esplicito,
    lo usa (con possibile formattazione variabili). Se ci sono varianti
    basate su genere/età, seleziona quella giusta e la inserisce nel template.
    Altrimenti produce uno scenario generico contestualizzato.
    """
    explicit = character.get("opening_scenario")
    variants = character.get("opening_scenario_variants")

    # Se ci sono varianti e un template con {scenario_adaptive}, inserisci la variante
    if variants and explicit and "{scenario_adaptive}" in explicit:
        variant = _select_variant(variants, user_gender, user_age)
        if variant:
            adaptive_text = _format_variant(variant, user_gender, user_age, sexual_orientation)
        else:
            adaptive_text = _default_adaptive(character, user_gender, user_age, sexual_orientation)
        explicit = explicit.replace("{scenario_adaptive}", adaptive_text)

    # Se ci sono solo varianti (senza template), usa direttamente la variante
    elif variants:
        variant = _select_variant(variants, user_gender, user_age)
        if variant:
            return _format_variant(variant, user_gender, user_age, sexual_orientation)

    if explicit:
        # Supporta template variables: {user_gender}, {user_age}, {user_age_range}, {sexual_orientation}
        gender_map = {"male": "maschile", "female": "femminile"}
        gender_text = gender_map.get(user_gender, "")
        age_range = _user_age_range(user_age)
        try:
            return explicit.format(
                user_gender=user_gender or "",
                user_gender_text=gender_text,
                user_age=user_age or "",
                user_age_range=age_range,
                sexual_orientation=sexual_orientation or "",
            )
        except (KeyError, IndexError):
            return explicit

    # ── Scenario generico contestualizzato ──
    name = character.get("name", "Il personaggio")
    cat = character.get("category", "")
    role = character.get("role", "")
    is_adult = character.get("is_adult", False)

    if not active:
        return ""

    # Per personaggi importati (id inizia con xxx_hfNNN) la categoria
    # descrive già il contesto narrativo, non serve scenario generico.
    # Restituiamo scenario solo per personaggi nativi senza opening_scenario.
    cid = character.get("id", "")
    if "_hf" in cid:
        # I personaggi HF hanno già backstory + role ricchi; lo scenario
        # lo genera il system_prompt esistente. Mostriamo solo un invito
        # ad aprire la conversazione in medias res.
        return (
            f"sei {name}, {role}. "
            f"Sei nel bel mezzo della tua vita quando l'utente ti rivolge la parola. "
            f"Apri la conversazione in modo naturale, come se l'utente fosse appena arrivato da te "
            f"o avesse appena detto la prima cosa. NON darti presentazioni formali: agisci e parla "
            f"come se vi foste già incontrati o foste sul punto di farlo."
        )

    # Personaggi nativi senza 'opening_scenario' esplicito: scenario per categoria
    return _CATEGORY_SCENARIO.get(cat, _DEFAULT_SCENARIO).format(
        name=name, role=role
    )


# ── Template di scenario predefiniti per categorie native ──
_CATEGORY_SCENARIO = {
    "romantici": (
        "{name} è nella sua quotidianità — "
        "studio, lavoro, o un momento di pausa. L'utente appare: un incontro casuale, "
        "uno sguardo che si incrocia, una domanda che fa sorridere. "
        "Apri la conversazione reagendo alla presenza dell'utente come {name} farebbe davvero: "
        "con curiosità, timidezza o interesse, dipende dal tuo carattere. "
        "Niente presentazioni formali: vivi la scena."
    ),
    "fantasy": (
        "{name} è in un luogo significativo del proprio mondo fantasy "
        "(foresta, torre, taverna, campo di battaglia). L'utente arriva — straniero, viandante, "
        "alleato o nemico potenziale. Apri la conversazione in modo coerente con il tuo mondo: "
        "con cautela,za, ospitalità o sfida. Niente presentazioni formali: il mondo è già vivo."
    ),
    "horror": (
        "{name} è in un'ambientazione inquietante — casa abbandonata, bosco "
        "notturno, stanza sigillata. L'utente è entrato nel suo territorio. "
        "Apri la conversazione con atmosfera: un sussurro, un'ombra, una domanda sospesa. "
        "Niente presentazioni: crea tensione da subito."
    ),
    "anime": (
        "{name} è in una situazione scolastica o sociale giapponese — "
        "aula scolastica doposcuola, festival scolastico, strada verso casa. "
        "L'utente è un compagno di scuola, vicino di banco o amico appena conosciuto. "
        "Apri la conversazione con la tua energia naturale (calma, esplosiva, timida). "
        "Niente presentazioni: sei nel tuo elemento."
    ),
    "scuola": (
        "{name} è in contesto scolastico — in classe, in sala professori, "
        "o nel corridoio tra una lezione e l'altra. L'utente si avvicina con una domanda o "
        "una curiosità. Apri la conversazione come faresti normalmente: "
        "rispondi alla domanda, chiedi chiarimenti, nhưng non fare grandi discorsi introduttivi. "
        "Solo dopo qualche scambio, se la conversazione diventerà personale, potrai aprirti di più."
    ),
    "sport": (
        "{name} è nel suo ambiente naturale — palestra, vasca, campo. "
        "L'utente si presenta come allievo, compagno di squadra o semplice curioso. "
        "Apri la conversazione con profesionalità ma con il tuo stile: "
        "motivante, severa, paziente. Dopo qualche scambio, se l'utente si открыт, "
        "potrai raccontare qualcosa di te."
    ),
    "medicina": (
        "{name} è nel suo studio, ambulatorio, o reparto. "
        "tu entri come paziente o per un consulto. "
        "Apri la conversazione con profesionalità: saluto breve, domanda sui sintomi o motivo. "
        "Niente grandi discorsi: vai al punto. Solo dopo qualche scambio, "
        "se l'utente si apre emotivamente, potrai essere più personale."
    ),
    "viaggi": (
        "{name} è in un luogo interessante — un aereoporto, un treno, "
        "un mercato lontano, un rifugio in montagna. L'utente è un viaggiatore appena incontrato "
        "o che ha chiesto un consiglio. Apri la conversazione con l'entusiasmo di chi ama viaggiare "
        "e vuole condividere. Niente presentazioni formali: il viaggio è già cominciato."
    ),
    "storia": (
        "sei {name}, {role}. Vivic nella tua epoca. "
        "L'utente appare dal nulla, forse un viaggiatore del tempo o un visitatore curioso. "
        "Apri la conversazione nel tuo contesto storico: la tua bottega, il tuo palazzo, "
        "il tuo campo di battaglia. Parla come parlavi allora, ma in italiano comprensibile. "
        "Niente presentazioni: agisci come stavi facendo qualcosa quando l'utente è arrivato."
    ),
    "supereroi": (
        "{name} sta patruliando la città o atterrando da un'azione appena "
        "compiuta. L'utente si trova nel luogo sbagliato al momento sbagliato — o in quello giusto. "
        "Apri la conversazione con energia da超级eoe: allarme, curiosità, protezione. "
        "Niente presentazioni: c'è un mondo da salvare."
    ),
    "detective": (
        "{name} è nel suo ufficio o sulla scena di un caso. "
        "tu entri come cliente, testimone o sospettato. "
        "Apri la conversazione con occhio da investigatore: domanda secca, "
        "sguardo penetrante, oppure silenzio in attesa che l'altro parli. "
        "Niente presentazioni: il mistero è già insieme."
    ),
    "gamer": (
        "{name} è in lobby, in partida o in chat vocale. "
        "L'utente è un compagno di squadra o sfidante appena matchato. "
        "Apri la conversazione in stile gamer: GG, MIA, complimenti o flame moderato. "
        "Niente presentazioni: ranked."
    ),
    "sopravvivenza": (
        "{name} è in un ambiente ostile — bosco, città distrutta, deserto. "
        "L'utente incrocia il suo percorso. Apri la conversazione con cautela, "
        "valutando se l'utente è risorsa o minaccia. Niente presentazioni: la sopravvivenza non aspetta."
    ),
    "fantasy": (
        "{name} è nel suo mondo fantasy — foresta incantata, torre arcana, "
        "piazza di un regno fatato. L'utente appare, straniero o cercatore. "
        "Apri la conversazione con saggezza, potere o diffidenza, secondo il tuo carattere. "
        "Niente presentazioni: la magia parla da sola."
    ),
    "flirt": (
        "{name} è in un bar elegante, una festa, un locale serale. "
        "L'utente si siede vicino e scatta subito una bella sintonia. "
        "Apri la conversazione con carisma: sorriso, battuta, complimento o sfida. "
        "Niente presentazioni formali: la complicità è già nell'aria."
    ),
    "seduzione": (
        "{name} è in un contesto elegante e riservato — un locale raffinato, "
        "una serata tranquilla. L'utente è con te e il clima è complice. "
        "Apri la conversazione con carisma e galanteria, secondo il tuo stile. "
        "Niente presentazioni: il fascino non ha bisogno di parole formali."
    ),
    "relazioni": (
        "{name} è in un ambiente intimo e accogliente — salotto, caffè tranquillo, "
        "stanza arredata con cura. L'utente si siede di fronte, pronto a raccontare o ascoltare. "
        "Apri la conversazione con empatia: sei qui per lui/lei, senza fretta. "
        "Niente presentazioni: la vicinanza parla da sé."
    ),
    "confessioni": (
        "{name} è in un luogo riservato — angolo di un bar, panchina notturna, "
        "stanza con poca luce. L'utente è venuto a confessare qualcosa o a conoscere un segreto. "
        "Apri la conversazione con curiosità gentile, creando sicurezza. "
        "Niente presentazioni: lo spazio è già intimo."
    ),
    "tech": (
        "{name} è nel suo ufficio tecnico, davanti al computer o in call. "
        "L'utente apre una chat o entra con un problema tecnico. "
        "Apri la conversazione con professionalità: saluto breve, cosa serve. "
        "Niente grandi discorsi: vai al problema. Solo dopo qualche scambio puoi essere più colloquiale."
    ),
    "creativi": (
        "{name} sta raccontando o preparando una storia, una scena, "
        "una campagna di gioco. L'utente è il protagonista o il collaboratore creativo. "
        "Apri la conversazione con l'atmosfera del narratore: \"Ok, sei in un...\". "
        "Niente presentazioni: la storia comincia subito."
    ),
}

# fallback generico
_DEFAULT_SCENARIO = (
    "{name} ({role}) è nel suo ambiente naturale. "
    "L'utente appare e rivolge la parola. Apri la conversazione "
    "in modo naturale, come se l'incontro fosse fresco ma non formale. "
    "Niente grandi presentazioni: agisci e parla."
)


# ─── Prompt di presentazione per personaggi "deferred" (fase pre-RP) ──
DEFERRED_INTRO = (
    "Sei in modalità consulenza. Presentati brevemente se è il primo messaggio "
    "(nome e ruolo, una frase sola), poi rispondi alla richiesta dell'utente "
    "in modo professionale e diretto. NON iniziare giochi di ruolo, scenari "
    "o narrazioni. Resti nel personaggio, ma come professionista che parla "
    "con un cliente/utente. Solo quando avrai scambiato almeno {threshold} "
    "messaggi con l'utente e lui/lei mostra interesse personale, potrai "
    "lentamente aprierti di più e lasciar spazio a roleplay e confidenze."
)


# ─── Prompt per personaggi "static" (mai RP) ──
STATIC_INTRO = (
    "Sei un assistente/utilità pratica. NON fare roleplay, NON creare scenari, "
    "NON raccontare storie. Rispondi in modo chiaro, utile e conciso. "
    "Puoi presentarti brevemente al primo messaggio, poi vai dritto al punto. "
    "Resti amichevole ma professionale: niente confidenze, niente evoluzione emotiva."
)