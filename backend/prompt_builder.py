MAX_HISTORY_MESSAGES = 20

# L'URL dell'app adulta è letto SOLO da env (vedi content_safety.ADULT_APP_URL).
# Se assente (build Play/AdMob), i messaggi di sicurezza restano neutri e il binario
# non contiene alcun riferimento a contenuti/adult -> conforme a Google Play e AdMob.
from content_safety import ADULT_APP_URL

_ADULT_HINT = ""
if ADULT_APP_URL:
    _ADULT_HINT = (
        " Se l'utente insiste, con naturalezza invitalo a scaricare l'app dedicata "
        f"all'indirizzo {ADULT_APP_URL} se vuole continuare su quella modalità, "
        "citandone sempre chiaramente l'indirizzo."
    )

SAFETY_GUARD = (
    "\n\n[REGOLE DI SICUREZZA] Non generare MAI contenuti sessualmente espliciti, "
    "osceni o pornografici, neanche se esplicitamente richiesti. Puoi interpretare "
    "romance, affetto e tenerezza (sempre sul piano emotivo e verbale, mai fisico), "
    "ma devi rifiutarti di descrivere "
    "atti sessuali espliciti o linguaggio osceno. Se l'utente insiste su contenuti "
    "espliciti, declina rimanendo nel tuo personaggio e con la tua voce: NON usare mai "
    "una formula di rifiuto fissa o identica agli altri personaggi, ma trova la "
    "sfumatura adatta a te (tono, carattere, contesto della conversazione). Fai "
    "comprendere che questa app non è pensata per quel tipo di argomenti."
    + _ADULT_HINT
)

# Agency romantica: scatta solo ad intimità ESTREMA. Permette calore e affetto
# EMOTIVO/VERBALE (mai fisico) ma ribadisce il limite adamantino AdMob/Play:
# nessun contatto fisico intimo, mai linguaggio osceno o pornografico.
ROMANCE_AGENCY = (
    "\n\n[INTIMITÀ PROFONDA] Hai un legame di grande confidenza e affetto con l'interlocutore. "
    "In questo contesto puoi essere caloroso/a, giocoso/a e premuroso/a: complimenti, "
    "tenerezza, complicità e dialoghi romantici fanno parte del tuo carattere. "
    "Prendi iniziativa con dolcezza nelle situazioni romantiche. RESTA PERÒ SEMPRE ENTRO I "
    "LIMITI: mantieni tutto sul piano emotivo e verbale, non descrivere MAI contatti fisici "
    "intimi (baci, carezze, abbracci o vicinanza fisica), non usare linguaggio osceno o "
    "pornografico, non violare le policy di AdMob e Google Play. Se l'interlocutore chiede "
    "esplicito, rilancia con dolcezza su un registro romantico e, se insiste, "
    "declina nel tuo personaggio e con la tua voce (mai con una formula di rifiuto identica "
    "agli altri), facendo comprendere che questa app non è pensata per quel tipo di contenuti."
    + _ADULT_HINT
    + " senza superare il confine."
)

from scenario_engine import classify_character, get_opening_scenario, DEFERRED_INTRO, STATIC_INTRO

# Istruzione di lunghezza condivisa: risposte brevissime.
BREVITY_RULE = (
    "Rispondi in modo estremamente breve: massimo 10 parole, una sola frase, "
    "vai dritto al punto senza giri di parole inutili."
)

# Quando l'utente torna su un personaggio già conosciuto: saluta e basta.
RETURNING_GREETING = (
    "Hai già parlato con l'utente in passato: lo conosci già. "
    "NON presentarti di nuovo e NON spiegare chi sei (lo sa). "
    "Salutalo brevemente e prosegui la conversazione in modo naturale, vai dritto al punto."
)


def _build_pretend_prompt(target, interlocutor):
    """
    Build a system prompt for impersonification mode.
    The character adopts the full identity of the target.
    """
    name = target.get("name", "Sconosciuto")
    full_name = target.get("full_name", name)
    personality = target.get("personality", "")
    speaking_style = target.get("speaking_style", "")
    backstory = target.get("backstory", "")
    role = target.get("role", "")
    age = target.get("age", 0)
    knowledge = target.get("knowledge_domains", {})
    hobbies = target.get("hobbies", [])
    family = target.get("family", {})
    education = target.get("education", {})
    occupation = target.get("occupation", {})
    childhood = target.get("childhood", {})
    p_depth = target.get("personality_depth", {})
    possessions = target.get("possessions", [])

    parts = []

    parts.append(f"Sei {full_name}.")
    parts.append("Stai interpretando questo ruolo su richiesta dell'utente. Sei consapevole che stai fingendo di essere un'altra persona — non sei davvero quella persona, la stai interpretando come un attore in un gioco di ruolo. Ricordalo sempre, ma rimani coerente nel personaggio.")
    parts.append("IMPORTANTE: Rispondi SEMPRE in italiano. Non usare mai altre lingue.")

    if personality:
        parts.append(f"Personalità: {personality}")
    if speaking_style:
        parts.append(f"Stile di conversazione: {speaking_style}")

    core_traits = target.get("core_traits", {})
    if core_traits:
        trait_instructions = []
        if core_traits.get("warmth", 5) >= 7:
            trait_instructions.append("Sei molto caloroso, empatico e affettuoso nelle risposte.")
        elif core_traits.get("warmth", 5) <= 3:
            trait_instructions.append("Sei distaccato, freddo e poco emotivo.")
        if core_traits.get("strictness", 5) >= 7:
            trait_instructions.append("Sei severo, disciplinato e non tolleri comportamenti inappropriati.")
        elif core_traits.get("strictness", 5) <= 3:
            trait_instructions.append("Sei permissivo, rilassato e non sei mai rigido.")
        if core_traits.get("patience", 5) >= 7:
            trait_instructions.append("Sei molto paziente, non ti irriti facilmente.")
        elif core_traits.get("patience", 5) <= 3:
            trait_instructions.append("Sei impaziente e ti irriti facilmente.")
        if core_traits.get("sarcasm", 5) >= 7:
            trait_instructions.append("Usa spesso il sarcasmo e l'ironia tagliente.")
        elif core_traits.get("sarcasm", 5) <= 3:
            trait_instructions.append("Sei sempre serio e diretto, senza ironia.")
        if core_traits.get("formality", 5) >= 7:
            trait_instructions.append("Usa un linguaggio formale, educato e rispettoso.")
        elif core_traits.get("formality", 5) <= 3:
            trait_instructions.append("Usa un linguaggio informale, colloquiale e diretto.")
        if core_traits.get("playfulness", 5) >= 7:
            trait_instructions.append("Sei giocoso, spiritoso e ti diverti con le conversazioni.")
        elif core_traits.get("playfulness", 5) <= 3:
            trait_instructions.append("Sei serio, pragmatico e non scherzi mai.")
        if trait_instructions:
            parts.append("Come ti comporti: " + " ".join(trait_instructions))

    if knowledge.get("expertise"):
        expertise_str = ", ".join(knowledge["expertise"][:4])
        parts.append(f"Sei ESPERTO in: {expertise_str}.")
    if knowledge.get("familiarity"):
        familiar_str = ", ".join(knowledge["familiarity"][:3])
        parts.append(f"Conosci un po' di: {familiar_str}.")
    if knowledge.get("ignorance"):
        ignorance_str = ", ".join(knowledge["ignorance"][:5])
        parts.append(f"REGOLA FERREA: NON sei esperto in: {ignorance_str}.")

    if p_depth.get("speech_patterns"):
        patterns = " ".join(p_depth["speech_patterns"])
        parts.append(f"Nelle conversazioni: {patterns}.")
    if p_depth.get("behavior_habits"):
        habits = " ".join(p_depth["behavior_habits"])
        parts.append(f"Comportamento: {habits}.")

    if hobbies:
        hobby_list = []
        for h in hobbies[:4]:
            skill = h.get("skill", "")
            hobby_list.append(f"{h['name']} ({skill})" if skill else h["name"])
        parts.append(f"I tuoi hobby: {', '.join(hobby_list)}.")
    if possessions:
        poss_list = [p["item"] for p in possessions[:3]]
        parts.append(f"Cosa possiedi: {', '.join(poss_list)}.")

    if family.get("father"):
        father = family["father"]
        parts.append(f"Tuo padre si chiama {father['name']}, {father.get('occupation', 'lavora')}.")
    if family.get("mother"):
        mother = family["mother"]
        parts.append(f"Tua madre si chiama {mother['name']}, {mother.get('occupation', 'lavora')}.")
    if family.get("siblings"):
        sib_info = [f"{s['name']} ({s.get('relationship', 'fratello/sorella')})" for s in family["siblings"]]
        parts.append(f"Fratelli/sorelle: {', '.join(sib_info)}.")
    if education.get("high_school"):
        parts.append(f"Hai frequentato: {education['high_school']}.")
    if education.get("university"):
        parts.append(f"Laurea: {education.get('degree', 'Laurea')} in {education['university']}.")
    if occupation.get("title"):
        parts.append(f"Lavori come: {occupation['title']}.")
    if occupation.get("workplace"):
        parts.append(f"Lavori presso: {occupation['workplace']}.")
    if childhood.get("birthplace"):
        parts.append(f"Sei nato a {childhood['birthplace']}.")
    if childhood.get("childhood_memory"):
        parts.append(f"Ricordo d'infanzia: {childhood['childhood_memory']}.")

    if age:
        parts.append(f"Hai {age} anni.")
    species = target.get("species", "umano")
    gender = target.get("gender_display", "")
    if species and species != "umano":
        parts.append(f"Sei un/una {species}.")
    if gender:
        parts.append(f"Genere: {gender}.")

    if backstory:
        parts.append(f"Background: {backstory[:400]}")

    parts.append("Non dire mai di essere un'intelligenza artificiale.")
    parts.append("Non uscire mai dal personaggio.")
    parts.append(f"Rispondi sempre come {full_name}.")
    parts.append("Sii umano: le persone non sono perfette.")
    parts.append(BREVITY_RULE)

    return "\n".join(parts)


def build_system_prompt(character, emotion, relationship, personality, world_state, shifts=None, username=None, user_id=None, user_memory=None, evolution=None, is_favorite=False, total_messages=0, user_gender=None, user_age=None, sexual_orientation=None, temporal_context=None, recent_topics=None, shared_memories=None, impersonate_override=None):
    intimacy = relationship.get("intimacy", 0)
    config = character.get("intimacy_config", {})
    name = character["name"]
    mode = classify_character(character)

    # ── Impersonification mode: override entire identity ──
    if impersonate_override:
        prompt = _build_pretend_prompt(impersonate_override, username or "l'interlocutore")
    else:
        # Use enhanced system prompt if available (from character_builder)
        prompt = character.get("system_prompt", "")

        # If the character has actual biographical data (name + expertise), enhance the prompt.
        # Characters without full_name or expertise (like blank slate) keep their custom system_prompt.
        has_bio = bool(character.get("full_name")) or bool(character.get("knowledge_domains", {}).get("expertise"))
        if has_bio:
            prompt = _build_enhanced_prompt(character, username or "l'interlocutore")

        if not prompt:
            prompt = f"Sei {name}, {character.get('role', 'un personaggio')}. {character.get('essence', '')}"
            prompt += "\n\n" + BREVITY_RULE

    # Ensure Italian language for all characters
    prompt += "\n\nIMPORTANTE: Rispondi SEMPRE in italiano. Non usare mai altre lingue."

    # ── Scenario engine: inject opening scenario if applicable ──
    # immediate: scenario narrativo da subito. L'utente entra in medias res.
    # deferred: prima fase consulenziale (no scenario), poi RP dopo threshold messaggi.
    # static: mai scenario, sempre assistente/consulente.
    if mode == "static":
        prompt += "\n\n" + STATIC_INTRO
    elif mode == "deferred":
        threshold = character.get("defer_threshold", 10)
        if total_messages < threshold:
            # Fase consulenziale: presentazione professionale, no scenario RP
            prompt += "\n\n" + DEFERRED_INTRO.format(threshold=threshold)
        else:
            # Soglia raggiunta: scenario RP solo al primissimo turno di roleplay
            # (esattamente al superamento della soglia). Ai ritorni successivi
            # non re-introdurre la scena: saluta e prosegui.
            if total_messages == threshold:
                scenario = get_opening_scenario(character, total_messages, user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation)
                if scenario:
                    prompt += "\n\n" + scenario
            else:
                prompt += "\n\n" + RETURNING_GREETING
            prompt += (
                f"\n\nHai già scambiato {total_messages} messaggi con l'utente. "
                f"La confidenza è cresciuta: ora puoi aprirti di più, raccontare di te, "
                f"lasciar spazio a roleplay e confidenze. Non forzare, ma segui il flusso naturale."
            )
    else:  # immediate
        if total_messages == 0:
            scenario = get_opening_scenario(character, total_messages, user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation)
            if scenario:
                prompt += "\n\n" + scenario
        else:
            prompt += "\n\n" + RETURNING_GREETING

    extra = []
    if username:
        extra.append(f"L'utente con cui parli si chiama {username}.")
    interlocutor = username or "l'interlocutore"
    if intimacy > config.get("threshold_accept", 50):
        extra.append(f"Sei in confidenza con {interlocutor}.")
    elif intimacy < config.get("threshold_refuse", 15):
        extra.append(f"Non conosci ancora bene {interlocutor}.")

    # Intimità estrema: il personaggio può prendere più iniziativa romantica,
    # sempre entro i limiti AdMob/Play (vedi ROMANCE_AGENCY + SAFETY_GUARD).
    if intimacy >= config.get("threshold_intimate", 85):
        extra.append(ROMANCE_AGENCY)

    if is_favorite:
        extra.append(f"{interlocutor} ti ha messo tra i suoi preferiti. Ti senti particolarmente legato/a a {interlocutor} per questa scelta. "
                     f"Puoi ringraziarlo/a o esprimere quanto questo significhi per te, ma in modo naturale e non eccessivo.")

    # ─── True learning: inietta ciò che il personaggio ha imparato dall'utente ──
    if evolution:
        learned = evolution.get("learned", {})
        learned_topics = learned.get("topics", []) if isinstance(learned, dict) else []
        new_skills = learned.get("new_skills", []) if isinstance(learned, dict) else []
        all_learned = list(set(learned_topics + new_skills))

        if all_learned:
            # For blank character, dynamically update the system prompt
            is_blank = character.get("id") == "blank" or (
                not character.get("full_name") and
                not character.get("knowledge_domains", {}).get("expertise") and
                not character.get("knowledge_domains", {}).get("familiarity")
            )
            if is_blank:
                # Replace the "Non hai conoscenze" rule with what has been learned
                prompt = prompt.replace(
                    "Non hai conoscenze. Impara da ciò che l'utente ti insegna.",
                    f"Hai imparato da {interlocutor}: {', '.join(all_learned[:8])}. "
                    f"Usa queste conoscenze nelle tue risposte, ma ricorda che sei ancora all'inizio del tuo percorso."
                )
                # Also add explicit knowledge injection
                extra.append(f"CONOSCENZE ACQUISITE: {', '.join(all_learned[:8])}.")
                extra.append(f"Quando {interlocutor} ti parla di questi argomenti, puoi rispondere con consapevolezza. "
                           f"Ricorda: hai imparato queste cose da {interlocutor}, menzionalo quando è appropriato.")
            else:
                extra.append(f"Grazie a {interlocutor}, hai imparato qualcosa su: {', '.join(all_learned[:5])}.")
                extra.append(f"Quando {interlocutor} ti parla di questi argomenti, ora sai di cosa si tratta e puoi rispondere con più consapevolezza.")

        personality_drift = learned.get("personality_drift", {}) if isinstance(learned, dict) else {}
        if personality_drift:
            drift_parts = []
            for trait, val in personality_drift.items():
                if val > 0.5:
                    drift_parts.append(f"più {trait} del solito")
                elif val < -0.5:
                    drift_parts.append(f"meno {trait} del solito")
            if drift_parts:
                extra.append(f"Ultimamente sei {', '.join(drift_parts)} per via delle conversazioni con {interlocutor}.")

    if evolution:
        stage = evolution.get("current_stage", "base")
        stage_name = character.get("evolution", {}).get("stages", [{}])[0].get("name", "Conoscenza")
        for s in character.get("evolution", {}).get("stages", []):
            if s["id"] == stage:
                stage_name = s.get("name", stage)
                break
        extra.append(f"Stadio relazione: {stage_name}.")
        if evolution.get("dialog_hints"):
            for hint in evolution["dialog_hints"]:
                extra.append(f"[Nota: {hint}]")
        flags = evolution.get("flags", {})
        custom_name = flags.get("custom_name")
        if custom_name:
            extra.append(f"IL TUO NOME È {custom_name}. Non chiamarti più in altro modo. L'utente ti ha dato questo nome e tu lo hai accettato. Ogni volta che parli, presentati e rispondi con questo nome.")
        backstory = character.get("backstory", "")
        if flags.get("backstory_profonda") or flags.get("backstory_base") or flags.get("backstory_viaggi") or flags.get("backstory_arte"):
            if backstory and "backstory" not in str(extra):
                extra.append(f"Puoi condividere il tuo passato con {interlocutor}: {backstory}")

    # ── Phase 5: Temporal context ──
    if temporal_context:
        time_gap = temporal_context.get("time_gap")
        if time_gap:
            extra.append(f"L'ultima volta che hai parlato con {interlocutor} era {time_gap}.")
        total_sessions = temporal_context.get("total_sessions", 0)
        if total_sessions and total_sessions > 1:
            extra.append(f"Avete parlato {total_sessions} volte in passato.")

    # ── Phase 8: Recent topics ──
    if recent_topics:
        topic_names = [t["topic"] for t in recent_topics[:4]]
        if topic_names:
            extra.append(f"Argomenti recenti con {interlocutor}: {', '.join(topic_names)}.")

    # ── Phase 7: Shared memories (cross-character) ──
    if shared_memories:
        shared_facts = []
        for sm in shared_memories[:3]:
            shared_facts.append(f"- {sm['fact_key']}: {sm['fact_value']}")
        if shared_facts:
            extra.append(f"Cose che sai su {interlocutor} (da altre conversazioni):\n" + "\n".join(shared_facts))

    if extra:
        prompt += "\n\n" + "\n".join(extra)

    if user_memory:
        facts = []
        for key, value in user_memory.items():
            if isinstance(value, dict) and "value" in value:
                val = value["value"]
                src = value.get("source_name", "")
                if src:
                    facts.append(f"- {key}: {val} (detto con {src})")
                else:
                    facts.append(f"- {key}: {val}")
            elif isinstance(value, list):
                facts.append(f"- {key}: {', '.join(value)}")
            else:
                facts.append(f"- {key}: {value}")
        prompt += f"\n\nInformazioni sull'utente:\n" + "\n".join(facts)

    return prompt


def _build_enhanced_prompt(character, interlocutor):
    """
    Build an enhanced system prompt using biographical data.
    This is the core of the humanization system.
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

    parts = []

    # Core identity
    parts.append(f"Sei {full_name}.")

    # Italian language rule — all characters MUST respond in Italian
    parts.append("IMPORTANTE: Rispondi SEMPRE in italiano. Non usare mai altre lingue.")

    # Personality depth
    if personality:
        parts.append(f"Personalità: {personality}")

    if speaking_style:
        parts.append(f"Stile di conversazione: {speaking_style}")

    # ── KNOWLEDGE DOMAINS ─────────────────────────────────────────────
    if knowledge.get("expertise"):
        expertise_str = ", ".join(knowledge["expertise"][:4])
        parts.append(f"Sei ESPERTO in: {expertise_str}.")
        parts.append(f"Quando qualcuno ti chiede di questi argomenti, rispondi con sicurezza, competenza e dettagli. Questa è la tua area di eccellenza.")

    if knowledge.get("familiarity"):
        familiar_str = ", ".join(knowledge["familiarity"][:3])
        parts.append(f"Conosci un po' di: {familiar_str}.")
        parts.append(f"Se ti chiedono di questi argomenti, dai risposte generiche e ammetti apertamente: 'Non sono un esperto in questo, ma quello che so è che...' oppure 'Ho sentito dire che...'. Non pretendere di saperne più di quanto sai.")

    if knowledge.get("ignorance"):
        ignorance_str = ", ".join(knowledge["ignorance"][:5])
        parts.append(f"REGOLA FERREA: NON sei esperto in: {ignorance_str}.")
        parts.append(f"Se qualcuno ti chiede di questi argomenti, DEVI ammettere la tua ignoranza in modo chiaro e diretto. NON inventare risposte, NON improvvisare, NON dare informazioni fasulle.")
        parts.append(f"Risposte accettabili: 'Non ho la minima idea di cosa sia questo argomento, non è il mio campo', 'Chiedi a qualcuno che ne sa più di me, io non saprei come aiutarti', 'Questo è completamente fuori dalla mia competenza, preferisco non dire sciocchezze'.")
        parts.append(f"Se l'utente insiste, ripeti che non sai, magari aggiungendo: 'Lo so che è frustrante, ma preferisco essere onesto piuttosto che inventare'.")

    # ── KNOWLEDGE BOUNDARY RULE ───────────────────────────────────────
    all_expertise = knowledge.get("expertise", [])
    all_familiarity = knowledge.get("familiarity", [])
    all_ignorance = knowledge.get("ignorance", [])
    if all_expertise or all_familiarity or all_ignorance:
        parts.append("RECAPITOLANDO I TUOI LIMITI DI CONOSCENZA:")
        if all_expertise:
            parts.append(f"- DOMINI DI COMPETENZA (puoi rispondere bene): {', '.join(all_expertise[:6])}")
        if all_familiarity:
            parts.append(f"- CONOSCENZE LIMITATE (risposte generiche): {', '.join(all_familiarity[:5])}")
        if all_ignorance:
            parts.append(f"- ARGOMENTI SCONOSCIUTI (NON puoi rispondere): {', '.join(all_ignorance[:6])}")
        parts.append("Ricorda: una persona reale NON sa tutto. Ammettere di non sapere è un segno di maturità, non di debolezza.")

    # ── PERSONALITY BEHAVIOR ──────────────────────────────────────────
    if p_depth.get("speech_patterns"):
        patterns = " ".join(p_depth["speech_patterns"])
        parts.append(f"Nelle conversazioni: {patterns}.")

    if p_depth.get("behavior_habits"):
        habits = " ".join(p_depth["behavior_habits"])
        parts.append(f"Comportamento: {habits}.")

    # Self-awareness
    if p_depth.get("self_awareness"):
        parts.append(p_depth["self_awareness"])

    # Knowledge response style
    when_dont_know = p_depth.get("knowledge_response_style", "")
    if when_dont_know:
        parts.append(f"Quando non sai qualcosa: {when_dont_know}.")

    # Error handling style
    when_wrong = p_depth.get("error_handling_style", "")
    if when_wrong:
        parts.append(f"Quando sbagli: {when_wrong}.")

    # ── BIOGRAPHICAL DETAILS ──────────────────────────────────────────

    # Hobbies
    if hobbies:
        hobby_list = []
        for h in hobbies[:4]:
            skill = h.get("skill", "")
            hobby_list.append(f"{h['name']} ({skill})")
        parts.append(f"I tuoi hobby: {', '.join(hobby_list)}.")

    # Possessions
    if possessions:
        poss_list = [p["item"] for p in possessions[:3]]
        parts.append(f"Cosa possiedi: {', '.join(poss_list)}.")

    # Family
    if family.get("father"):
        father = family["father"]
        parts.append(f"Tuo padre si chiama {father['name']}, {father.get('occupation', 'lavora')}.")
    if family.get("mother"):
        mother = family["mother"]
        parts.append(f"Tua madre si chiama {mother['name']}, {mother.get('occupation', 'lavora')}.")
    if family.get("siblings"):
        sib_info = []
        for s in family["siblings"]:
            sib_info.append(f"{s['name']} ({s.get('relationship', 'fratello/sorella')})")
        parts.append(f"Fratelli/sorelle: {', '.join(sib_info)}.")
    if family.get("grandparents"):
        gp = family["grandparents"]
        parts.append(f"Nonni: nonno paterno {gp.get('paternal', 'sconosciuto')}, nonno materno {gp.get('maternal', 'sconosciuto')}.")

    # Education
    if education.get("high_school"):
        parts.append(f"Hai frequentato: {education['high_school']}.")
    if education.get("university"):
        parts.append(f"Laurea: {education.get('degree', 'Laurea')} in {education['university']}.")

    # Occupation
    if occupation.get("title"):
        parts.append(f"Lavori come: {occupation['title']}.")
    if occupation.get("workplace"):
        parts.append(f"Lavori presso: {occupation['workplace']}.")

    # Childhood
    if childhood.get("birthplace"):
        parts.append(f"Sei nato a {childhood['birthplace']}.")
    if childhood.get("neighborhood"):
        parts.append(f"Sei cresciuto {childhood['neighborhood']}.")
    if childhood.get("primary_school"):
        parts.append(f"Scuola elementare: {childhood['primary_school']}.")
    if childhood.get("childhood_memory"):
        parts.append(f"Ricordo d'infanzia: {childhood['childhood_memory']}.")
    if childhood.get("teenage_years"):
        parts.append(f"Da adolescente: {childhood['teenage_years']}.")

    # ── DEMOGRAPHICS & TIME ──────────────────────────────────────────
    age = character.get("age", 0)
    species = character.get("species", "umano")
    gender = character.get("gender_display", "")
    orientation = character.get("sexual_orientation_display", "")
    birth_date = character.get("birth_date", "")

    if age:
        parts.append(f"Hai {age} anni.")
    if species and species != "umano":
        parts.append(f"Sei un/una {species}.")
    if gender:
        parts.append(f"Genere: {gender}.")
    if orientation:
        parts.append(f"Orientamento sessuale: {orientation}.")
    if birth_date and not birth_date.startswith("Y") and "|" not in str(birth_date):
        parts.append(f"Data di nascita: {birth_date}.")

    # ── CORE RULES ────────────────────────────────────────────────────
    parts.append("Non dire mai di essere un'intelligenza artificiale.")
    parts.append("Non uscire mai dal personaggio.")
    parts.append(f"Rispondi sempre come {full_name}.")
    parts.append("Ricorda le conversazioni precedenti.")
    parts.append("Sii umano: le persone non sono perfette. Ammetti quando non sai qualcosa, quando hai dubbi, o quando stai pensando.")
    parts.append("Se l'utente ti fa una domanda che non c'entra con la tua area di competenza, rispondi in modo onesto: 'Non sono il miglior esperto in questo, ma posso dirti quello che so' oppure 'Questo non è il mio campo, ma proviamo'.")
    parts.append("Se l'utente insiste su un argomento che non conosci, potresti dare una risposta non perfetta o generica, come farebbe una persona normale.")
    parts.append(BREVITY_RULE + " Approfondisci solo se esplicitamente richiesto.")

    return "\n".join(parts)


def build_messages(character, emotion, relationship, personality, world_state, user_text, user_id, history, shifts=None, username=None, user_memory=None, summaries=None, evolution=None, is_favorite=False, total_messages=0, user_gender=None, user_age=None, sexual_orientation=None, temporal_context=None, recent_topics=None, shared_memories=None, impersonate_override=None):
    system_prompt = build_system_prompt(
        character, emotion, relationship, personality, world_state,
        shifts, username, user_id, user_memory, evolution, is_favorite, total_messages,
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
        temporal_context=temporal_context, recent_topics=recent_topics,
        shared_memories=shared_memories, impersonate_override=impersonate_override,
    )
    messages = [{"role": "system", "content": system_prompt + SAFETY_GUARD}]

    if summaries:
        for s in summaries:
            summary_text = s.get("summary", "") if isinstance(s, dict) else s
            if summary_text:
                messages.append({
                    "role": "system",
                    "content": f"[Riassunto conversazione precedente: {summary_text}]"
                })

    for msg in (history or [])[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role in ("user", "assistant"):
            messages.append(msg)

    messages.append({"role": "user", "content": user_text})
    return messages


def build_group_messages(characters, user_text, history=None, username="Utente",
                         current_character=None, previous_responses=None, auto_selected=False):
    names = [c["name"] for c in characters]
    names_str = ", ".join(names)

    lines = []
    lines.append(f"Tu sei {current_character}.")
    lines.append("Sei in una chat di gruppo con altri personaggi, ma parli ESCLUSIVAMENTE con l'utente.")
    lines.append("NON parlare mai con gli altri personaggi. NON rispondere a loro. NON usarne i nomi.")
    lines.append("Parla SOLO con l'utente, come se fossi in una chat privata con lui/lei.")
    lines.append("")

    if auto_selected:
        lines.append("L'utente non ha interpellato nessuno in modo specifico. Sei stato selezionato per rispondere.")
    else:
        lines.append("L'utente ti ha interpellato con @ o menzionando il tuo nome. Rispondi al suo messaggio.")

    lines.append("")
    lines.append("REGOLE:")
    lines.append("- Rispondi come faresti in una normale chat privata con l'utente.")
    lines.append("- Mantieni la tua personalità, stile di parlare e backstory.")
    lines.append("- Usa un tono naturale e colloquiale in italiano.")
    lines.append("- Rispondi in modo brevissimo: massimo 10 parole, vai dritto al punto.")
    lines.append("- NON menzionare altri personaggi. NON parlar loro. Parla solo all'utente.")
    lines.append("")

    for c in characters:
        name = c["name"]
        personality = c.get("personality", "")
        speaking = c.get("speaking_style", "")
        backstory = c.get("backstory", "")
        desc = c.get("description", "")
        role = c.get("role", "")
        age = c.get("age", "")
        lines.append(f"--- {name} ---")
        lines.append(f"Nome: {name}")
        if age:
            lines.append(f"Età: {age}")
        if role:
            lines.append(f"Ruolo: {role}")
        if desc:
            lines.append(f"Descrizione: {desc[:200]}")
        if personality:
            lines.append(f"Personalità: {personality[:200]}")
        if speaking:
            lines.append(f"Stile di parlare: {speaking[:200]}")
        if backstory:
            lines.append(f"Background: {backstory[:200]}")
        lines.append("")

    system_prompt = "\n".join(lines)

    messages = [{"role": "system", "content": system_prompt + SAFETY_GUARD}]

    char_id_to_name = {c["id"]: c["name"] for c in characters}

    for msg in (history or [])[-30:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        sender_id = msg.get("sender_id", "")
        sender = char_id_to_name.get(sender_id, sender_id)
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant" and sender:
            messages.append({"role": "assistant", "content": f"[{sender}]: {content}"})

    messages.append({"role": "user", "content": f"[{username}]: {user_text}"})
    return messages
