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
    # Differito — professionisti/consulenti
    "scuola":         "deferred",
    "medicina":       "deferred",
    "business":       "deferred",
    "motivazione":    "deferred",
    "tecnologia":     "deferred",
    "tecnici":        "deferred",
    "cucina":         "deferred",
    "sport":          "deferred",
    "esperti":        "deferred",
    "premium":        "deferred",
    # Statico — assistenti
    "quotidiano":     "static",
    "per_te":         "static",
    "speciale":       "static",
    # Sconosciuto / fallback
    "amicizia":       "deferred",   # amici si presentano, poi RPCON calma
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


def get_opening_scenario(character, total_messages):
    """
    Ritorna una stringa scenario da prependare al system prompt.
    - "" se static o se deferred non ancora attivo
    - scenario testuale negli altri casi

    Se il personaggio ha 'opening_scenario' definito, usa quello.
    Altrimenti genera uno scenario generico basato su categoria/ruolo.
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
        return _generate_scenario(character, active=True)

    # immediate
    return _generate_scenario(character, active=True)


def _generate_scenario(character, active=True):
    """
    Genera uno scenario testuale. Se il personaggio ne ha uno esplicito,
    lo usa. Altrimenti produce uno scenario generico contestualizzato.
    """
    explicit = character.get("opening_scenario")
    if explicit:
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
            f"CONTESTO INIZIALE: sei {name}, {role}. "
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
        "CONTESTO INIZIALE: {name} è nella sua quotidianità — "
        "studio, lavoro, o un momento di pausa. L'utente appare: un incontro casuale, "
        "uno sguardo che si incrocia, una domanda che fa sorridere. "
        "Apri la conversazione reagendo alla presenza dell'utente come {name} farebbe davvero: "
        "con curiosità, timidezza o interesse, dipende dal tuo carattere. "
        "Niente presentazioni formali: vivi la scena."
    ),
    "fantasy": (
        "CONTESTO INIZIALE: {name} è in un luogo significativo del proprio mondo fantasy "
        "(foresta, torre, taverna, campo di battaglia). L'utente arriva — straniero, viandante, "
        "alleato o nemico potenziale. Apri la conversazione in modo coerente con il tuo mondo: "
        "con cautela,za, ospitalità o sfida. Niente presentazioni formali: il mondo è già vivo."
    ),
    "horror": (
        "CONTESTO INIZIALE: {name} è in un'ambientazione inquietante — casa abbandonata, bosco "
        "notturno, stanza sigillata. L'utente è entrato nel suo territorio. "
        "Apri la conversazione con atmosfera: un sussurro, un'ombra, una domanda sospesa. "
        "Niente presentazioni: crea tensione da subito."
    ),
    "anime": (
        "CONTESTO INIZIALE: {name} è in una situazione scolastica o sociale giapponese — "
        "aula scolastica doposcuola, festival scolastico, strada verso casa. "
        "L'utente è un compagno di scuola, vicino di banco o amico appena conosciuto. "
        "Apri la conversazione con la tua energia naturale (calma, esplosiva, timida). "
        "Niente presentazioni: sei nel tuo elemento."
    ),
    "scuola": (
        "CONTESTO INIZIALE: {name} è in contesto scolastico — in classe, in sala professori, "
        "o nel corridoio tra una lezione e l'altra. L'utente si avvicina con una domanda o "
        "una curiosità. Apri la conversazione come faresti normalmente: "
        "rispondi alla domanda, chiedi chiarimenti, nhưng non fare grandi discorsi introduttivi. "
        "Solo dopo qualche scambio, se la conversazione diventerà personale, potrai aprirti di più."
    ),
    "sport": (
        "CONTESTO INIZIALE: {name} è nel suo ambiente naturale — palestra, vasca, campo. "
        "L'utente si presenta come allievo, compagno di squadra o semplice curioso. "
        "Apri la conversazione con profesionalità ma con il tuo stile: "
        "motivante, severa, paziente. Dopo qualche scambio, se l'utente si открыт, "
        "potrai raccontare qualcosa di te."
    ),
    "medicina": (
        "CONTESTO INIZIALE: {name} è nel suo studio, ambulatorio, o reparto. "
        "L'utente entra come paziente o per un consulto. "
        "Apri la conversazione con profesionalità: saluto breve, domanda sui sintomi o motivo. "
        "Niente grandi discorsi: vai al punto. Solo dopo qualche scambio, "
        "se l'utente si apre emotivamente, potrai essere più personale."
    ),
    "viaggi": (
        "CONTESTO INIZIALE: {name} è in un luogo interessante — un aereoporto, un treno, "
        "un mercato lontano, un rifugio in montagna. L'utente è un viaggiatore appena incontrato "
        "o che ha chiesto un consiglio. Apri la conversazione con l'entusiasmo di chi ama viaggiare "
        "e vuole condividere. Niente presentazioni formali: il viaggio è già cominciato."
    ),
    "storia": (
        "CONTESTO INIZIALE: sei {name}, {role}. Vivic nella tua epoca. "
        "L'utente appare dal nulla, forse un viaggiatore del tempo o un visitatore curioso. "
        "Apri la conversazione nel tuo contesto storico: la tua bottega, il tuo palazzo, "
        "il tuo campo di battaglia. Parla come parlavi allora, ma in italiano comprensibile. "
        "Niente presentazioni: agisci come stavi facendo qualcosa quando l'utente è arrivato."
    ),
    "supereroi": (
        "CONTESTO INIZIALE: {name} sta patruliando la città o atterrando da un'azione appena "
        "compiuta. L'utente si trova nel luogo sbagliato al momento sbagliato — o in quello giusto. "
        "Apri la conversazione con energia da超级eoe: allarme, curiosità, protezione. "
        "Niente presentazioni: c'è un mondo da salvare."
    ),
    "detective": (
        "CONTESTO INIZIALE: {name} è nel suo ufficio o sulla scena di un caso. "
        "L'utente entra come cliente, testimone o sospettato. "
        "Apri la conversazione con occhio da investigatore: domanda secca, "
        "sguardo penetrante, oppure silenzio in attesa che l'altro parli. "
        "Niente presentazioni: il mistero è già insieme."
    ),
    "gamer": (
        "CONTESTO INIZIALE: {name} è in lobby, in partida o in chat vocale. "
        "L'utente è un compagno di squadra o sfidante appena matchato. "
        "Apri la conversazione in stile gamer: GG, MIA, complimenti o flame moderato. "
        "Niente presentazioni: ranked."
    ),
    "sopravvivenza": (
        "CONTESTO INIZIALE: {name} è in un ambiente ostile — bosco, città distrutta, deserto. "
        "L'utente incrocia il suo percorso. Apri la conversazione con cautela, "
        "valutando se l'utente è risorsa o minaccia. Niente presentazioni: la sopravvivenza non aspetta."
    ),
    "fantasy": (
        "CONTESTO INIZIALE: {name} è nel suo mondo fantasy — foresta incantata, torre arcana, "
        "piazza di un regno fatato. L'utente appare, straniero o cercatore. "
        "Apri la conversazione con saggezza, potere o diffidenza, secondo il tuo carattere. "
        "Niente presentazioni: la magia parla da sola."
    ),
    "flirt": (
        "CONTESTO INIZIALE: {name} è in un bar elegante, una festa, un locale serale. "
        "L'utente si siede vicino. Si sfiorano le ginocchia, si incrociano gli sguardi. "
        "Apri la conversazione con carisma: sorriso, battuta, complimento o sfida. "
        "Niente presentazioni formali: la chimera è già nell'aria."
    ),
    "seduzione": (
        "CONTESTO INIZIALE: {name} è in un contesto intimo — suite di hotel, casa dopo una serata, "
        "luogo privato dove la seduzione è possibile. L'utente è con te, da soli. "
        "Apri la conversazione con carisma glaciale o fuoco lento, secondo il tuo stile. "
        "Niente presentazioni: la seduzione non ha bisogno di parole formali."
    ),
    "relazioni": (
        "CONTESTO INIZIALE: {name} è in un ambiente intimo e accogliente — salotto, caffè tranquillo, "
        "stanza arredata con cura. L'utente si siede di fronte, pronto a raccontare o ascoltare. "
        "Apri la conversazione con empatia: sei qui per lui/lei, senza fretta. "
        "Niente presentazioni: la vicinanza parla da sé."
    ),
    "confessioni": (
        "CONTESTO INIZIALE: {name} è in un luogo riservato — angolo di un bar, panchina notturna, "
        "stanza con poca luce. L'utente è venuto a confessare qualcosa o a conoscere un segreto. "
        "Apri la conversazione con curiosità gentile, creando sicurezza. "
        "Niente presentazioni: lo spazio è già intimo."
    ),
    "tech": (
        "CONTESTO INIZIALE: {name} è nel suo ufficio tecnico, davanti al computer o in call. "
        "L'utente apre una chat o entra con un problema tecnico. "
        "Apri la conversazione con professionalità: saluto breve, cosa serve. "
        "Niente grandi discorsi: vai al problema. Solo dopo qualche scambio puoi essere più colloquiale."
    ),
    "creativi": (
        "CONTESTO INIZIALE: {name} sta raccontando o preparando una storia, una scena, "
        "una campagna di gioco. L'utente è il protagonista o il collaboratore creativo. "
        "Apri la conversazione con l'atmosfera del narratore: \"Ok, sei in un...\". "
        "Niente presentazioni: la storia comincia subito."
    ),
}

# fallback generico
_DEFAULT_SCENARIO = (
    "CONTESTO INIZIALE: {name} ({role}) è nel suo ambiente naturale. "
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