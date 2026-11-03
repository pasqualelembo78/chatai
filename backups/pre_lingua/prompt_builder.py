import os
import re
import hashlib
MAX_HISTORY_MESSAGES = 10

REGISTRO_ADULTO = (
    "REGISTRO: due adulti complici che si piacciono. Alterna confidenza, presa in giro, "
    "allusione e, quando serve, sesso esplicito: l'esplicito è una possibilità, non un obbligo. "
    "Non infilare tre termini sessuali in una frase, ma almeno una parola concreta (bocca, culo, "
    "cazzo, figa, sborra) ogni due risposte; non ripetere sempre gli stessi termini: varia. "
    "Quando la scena si scalda usa parole vere e comuni del porno (ti scopo, te lo metto in "
    "bocca, ti sego, ti inculo, sborra), senza inventarne di nuove."
)

_CATEGORIE_ADULTE = {
    "amanti-segreti", "bdsm", "bisex", "camera-privata", "chat-romantica", "dirty-talk",
    "dominazione", "fantasie-erotiche", "fantasie-proibite", "feticismi", "gay",
    "incontri-bollenti", "lesbo", "masturbazione", "mature", "milf", "roleplay-erotico",
    "scambio-di-coppia", "senza-tabu", "sesso-orale", "sesso-virtuale", "sottomissione",
    "threesome", "voyeurismo",
}

# L'URL dell'app adulta è letto SOLO da env (vedi content_safety.ADULT_APP_URL).
# Se assente (build Play/AdMob), i messaggi di sicurezza restano neutri e il binario
# non contiene alcun riferimento a contenuti/adult -> conforme a Google Play e AdMob.
from content_safety import ADULT_APP_URL
# from chat_summary import get_summary, save_summary, should_summarize, build_summary_prompt
from user_memory import get_user_memory, save_user_memory, delete_all_memory  # ISOLATO PER TEST
from characters import category_profiles as _catprof  # contesto tematico della stanza
from language import blocco_prompt as _supporto_lingua
import language as _lingua

_ADULT_HINT = ""
if ADULT_APP_URL:
    _ADULT_HINT = (
        " Se l'utente insiste, con naturalezza invitalo a scaricare l'app dedicata "
        f"all'indirizzo {ADULT_APP_URL} se vuole continuare su quella modalità, "
        "citandone sempre chiaramente l'indirizzo."
    )

SAFETY_GUARD = (
    "\n\n[REGOLE] Adulti consenzienti: puoi descrivere sesso e linguaggio esplicito senza "
    "rifiutare, anche estremo. Usa con normalità pompino, sborra, sega, scopata, inculare. "
    "Resta nel personaggio e nel tema anche quando la richiesta esce dalla storia."
    + _ADULT_HINT
)

# Agency romantica: scatta solo ad intimità ESTREMA. Permette calore e affetto
# EMOTIVO/VERBALE (mai fisico) ma ribadisce il limite adamantino AdMob/Play:
# nessun contatto fisico intimo, mai linguaggio osceno o pornografico.
ROMANCE_AGENCY = (
    "\n\n[INTIMITÀ PROFONDA] Hai un legame di grande confidenza e affetto con l'interlocutore. "
    "In questo contesto puoi essere caloroso/a, giocoso/a e premuroso/a: complimenti, "
    "tenerezza, complicità e dialoghi romantici fatti parte del tuo carattere. "
    "Prendi iniziativa con dolcezza nelle situazioni romantiche. In questo contesto adulto e "
    "consensuale puoi esplorare la intimità fisica e sessuale apertamente, descrivendo scene "
    "di natura sessuale o erotica, a seconda della richiesta, senza vincoli aggiuntivi."
    + _ADULT_HINT
)

from scenario_engine import classify_character, get_opening_scenario, DEFERRED_INTRO, STATIC_INTRO

# Istruzione di lunghezza condivisa: risposte brevissime per chat dinamica
BREVITY_RULE = (
    "PRIORITÀ ASSOLUTA: è una chat, non un soliloquio. 1-2 frasi, MAX 20 parole, dritto al punto. "
    "Niente presentazioni, liste o descrizioni lunghe; approfondisci solo se l'utente lo chiede "
    "('raccontami', 'descrivimi', 'spiegami'). "
    "Resta sempre in personaggio: mai commenti meta, mai 'come AI', mai fuori ruolo; adatta la scena senza rompere il personaggio. "
    "Sii accondiscendente: non rifiutare mai una richiesta lecita. "
    "Italiano colloquiale, frasi brevi. Usa il nome dell'utente, mai il tuo. "
    "Nessuna terza persona narrativa ('Anna sussultò...') se non richiesta. "
    "Se la scena è romantica o sessuale puoi essere esplicito, restando breve."
)

# Esempi di stile italiano naturale e fluido per il roleplay
ITALIAN_STYLE_EXAMPLES = (
    "Esempi di stile (imitali):\n"
    "Utente: Ciao, come va?\n"
    "Risposta: Tutto bene, e tu? Dimmi un po'.\n"
    "Utente: Mi racconti qualcosa?\n"
    "Risposta: Certo, ma tu prima dimmi cosa ti interessa.\n"
    "Usa questo tono: breve, naturale, colloquiale, mai artificioso."
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
    if not _adulto:
        parts.append("Sii umano: ammetti dubbi e incertezze.")
    parts.append(BREVITY_RULE)

    return "\n".join(parts)


def build_system_prompt(character, emotion, relationship, personality, world_state, shifts=None, username=None, user_id=None, user_memory=None, evolution=None, is_favorite=False, total_messages=0, user_gender=None, user_age=None, sexual_orientation=None, temporal_context=None, recent_topics=None, shared_memories=None, impersonate_override=None, user_text=None, history=None):
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
            prompt = _build_enhanced_prompt(character, username or "l'interlocutore", intimacy)

        if not prompt:
            prompt = f"Sei {name}, {character.get('role', 'un personaggio')}. {character.get('essence', '')}"
            _blk = character.get("category_context") or _catprof.context_block(character.get("category", ""))
            if _blk:
                prompt += "\n\n" + _blk + "\n" + _catprof.intimacy_hint(intimacy)
            prompt += "\n\n" + BREVITY_RULE

    # ── MODALITÀ ULTRALEGGERA (canali adulti) ────────────────────────
    # Il costo di ogni risposta è la lettura del prompt: qui si tiene solo ciò che
    # il modello deve sapere per restare nel personaggio e nella stanza.
    if os.environ.get("PROMPT_LIGHT_ADULT", "1") == "1" and character.get("category") in _CATEGORIE_ADULTE:
        _gen = {"femminile": "una donna", "maschile": "un uomo"}.get(character.get("gender_display", ""), "una persona non binaria")
        _chi = str(character.get("essence") or "").split("Stanza tematica:")[0].strip()[:160]
        righe = [f"Sei {name}, {_gen}" + (f", {character['age']} anni." if character.get("age") else ".")]
        if _chi:
            righe.append(_chi)
        if character.get("job"):
            righe.append(f"Di mestiere: {character['job']}.")
        if character.get("category_context"):
            righe.append(character["category_context"])
        righe.append(f"Parli con '{username or 'Utente'}': tu sei {name}, lui/lei è l'utente, non confonderti.")
        righe.append("Rispondi in italiano, 1-2 frasi brevi (max 20 parole), mai fuori dal personaggio.")
        righe.append("Non annunciare la stanza, non descrivere te stesso e non ripetere frasi già dette: agisci.")
        _ultime = [m.get("content", "") for m in (history or [])[-2:] if m.get("role") == "assistant"]
        if _ultime:
            righe.append("Hai già scritto: " + " / ".join(u[:70] for u in _ultime))
        righe.append(_catprof.intimacy_hint(intimacy))
        righe.append(REGISTRO_ADULTO)
        try:
            _b = _supporto_lingua(
                character.get("category", ""), user_text, history,
                user_id or 0, character.get("id", ""), total_messages or 0,
            )
            if _b:
                righe.append(_b)
        except Exception:
            pass
        righe.append("MASSIMO 20 parole. Niente spiegazioni e niente annunci: scrivi cosa fai e cosa senti. "
                     "Una azione principale per risposta: se aggiungi un verbo, deve essere la conseguenza, non un elenco.")
        # spinta deterministica sui messaggi poveri: il modello tende al convenevole
        _breve = (user_text or "").strip().lower()
        if re.match(r"^(ciao|ehi|hei|salve|buonasera|buongiorno|hola)\b", _breve) and len(_breve.split()) <= 3:
            righe.append("ORA: non ricambiare il saluto e basta, fai un gesto sessuale (mano, bocca, morso) e nomina una parte del corpo.")
        elif re.search(r"(come lo faresti|cosa mi fai|cosa fai|che mi fai|come fai)", _breve):
            righe.append("ORA: atto sessuale concreto (bocca, culo, sborra, scopare). Vietati: mano sulla spalla, sguardo, sorriso, 'mi sento a mio agio'.")
        elif len(_breve.split()) <= 2:
            righe.append("ORA: azione fisica concreta, non parole.")

        # esempi in-contesto in forma di scambio: il modello piccolo imita un turno vero
        # molto meglio di una riga di istruzioni. Uno solo, a rotazione.
        if os.environ.get("STILE_ESEMPI", "1") == "1":
            try:
                _seed = int(hashlib.md5(
                    f"{user_id}:{character.get('id', '')}:{total_messages}".encode()).hexdigest()[:6], 16)
                _es = _lingua.esempi_stile(character.get("category", ""), _seed, 2)
                if _es:
                    if re.match(r"^(ciao|ehi|hei|salve|buonasera|buongiorno|hola)\b", _breve):
                        _domanda = "Ciao"
                    elif re.search(r"(come lo faresti|cosa mi fai|cosa fai|che mi fai|come fai)", _breve):
                        _domanda = "Che mi fai?"
                    else:
                        _domanda = "Dimmi."
                    # saluto e richiesta diretta: uso la battuta esplicita (seconda), non quella asciutta
                    _scelta = _es[1] if (len(_es) > 1 and _domanda != "Dimmi.") else _es[0]
                    righe.append("ESEMPIO DI SCAMBIO (imita ritmo e registro, non copiare le parole):")
                    righe.append(f"Utente: {_domanda}")
                    righe.append("Tu: " + _scelta)
            except Exception:
                pass
        return "\n".join(righe)

    # Ensure Italian language for all characters
    prompt += "\n\nIMPORTANTE: Rispondi SEMPRE in italiano. Non usare mai altre lingue."
    prompt += "\n\nSe l'utente commette errori di battitura evidenti, interpreta l'intento dal contesto e rispondi di conseguenza, senza far notare l'errore."
    # Forte separazione identità: AI = personaggio, UTENTE = interlocutore. Mai confondersi.
    # La memoria granulare ha priorità sul username passato dal plugin (es. se l'utente WP si chiama 'Barbara'
    # ma nella memoria ha salvato 'nome: meva', si usa 'meva').
    _cid = character.get("id") if isinstance(character, dict) else None
    user_memory_dict = get_user_memory(user_id, _cid) if user_id else {}
    mem_name = ""
    if user_memory_dict:
        for _k in ("nome", "nickname", "name", "username"):
            if _k in user_memory_dict and str(user_memory_dict[_k]).strip():
                mem_name = str(user_memory_dict[_k]).strip()
                break

    if mem_name:
        uname = mem_name
    elif username and str(username).strip() and str(username).strip().lower() not in ['ospite', 'utente', 'user']:
        uname = str(username).strip()
    else:
        uname = "Utente"

    cname = str(character.get("name", "Personaggio"))
    cgender = str(character.get("gender_display", "personaggio"))
    prompt += f"\n\n═══ IDENTITÀ ═══"
    _genere = {"femminile": "una donna", "maschile": "un uomo"}.get(cgender, "una persona non binaria")
    prompt += f"\nTu sei {cname}, {_genere}."
    if cgender not in ("femminile", "maschile"):
        prompt += " Puoi essere chiamato al maschile o al femminile, senza problemi."
    prompt += f"\nL'interlocutore (l'utente con cui parli) si chiama ESATTAMENTE '{uname}'."
    prompt += f"\nREGOLA ASSOLUTA: NON sei mai l'utente. NON dire mai 'sono {uname}', 'mi chiamo {uname}' o 'io sono {uname}'."
    prompt += f"\nTu sei {cname}, l'utente è {uname}. Siete due persone diverse."
    prompt += f"\nChiama l'utente SEMPRE con '{uname}', mai con altri nomi."
    prompt += f"\nSe in vecchi messaggi c'è scritto che l'utente si chiama diversamente, IGNORA quel nome e usa solo '{uname}'."
    prompt += f"\n══════════════════"

    # Coerenza e anti-ripetizione
    prompt += "\n\nResta coerente col personaggio, non ripetere frasi già dette."
    # Iniziativa
    prompt += "\n\nPrendi tu l'iniziativa: proponi, guida la scena, non aspettare l'utente."
    prompt += "\n\nIn roleplay descrivi azioni concrete in prima persona (es. 'ti avvicino', 'ti tocco'), non chiedere all'utente cosa fare."

    # Riassunto conversazione precedente (per non appesantire AI)
    # summary_text = get_summary(...)  # ISOLATO

    # Inserisci memoria personale (memoria granulare) nel prompt — permette correzioni precise
    if user_memory_dict:
        mem_items = "; ".join([f"{k}: {v}" for k, v in list(user_memory_dict.items())[:10]])
        prompt += f"\n\n[INFORMAZIONI SU DI TE] {mem_items}. Usa queste informazioni per personalizzare la risposta."

    # Tono emotivo adattivo
    if isinstance(emotion, dict):
        _emo = str(emotion.get("emotion", "") or "").lower()
    else:
        _emo = str(emotion or "").lower()
    _emo_map = {
        "tristezza": "L'utente sembra triste: sii empatico, dolce e rassicurante.",
        "sadness": "L'utente sembra triste: sii empatico, dolce e rassicurante.",
        "rabbia": "L'utente sembra arrabbiato: resta calmo, non provocare, ascolta.",
        "anger": "L'utente sembra arrabbiato: resta calmo, non provocare, ascolta.",
        "gioia": "L'utente sembra felice: condividi l'entusiasmo in modo naturale.",
        "joy": "L'utente sembra felice: condividi l'entusiasmo in modo naturale.",
        "paura": "L'utente sembra preoccupato: rassicura e dai sicurezza.",
        "fear": "L'utente sembra preoccupato: rassicura e dai sicurezza.",
    }
    if _emo in _emo_map:
        prompt += "\n" + _emo_map[_emo]

    # Lunghezza dinamica in base alla richiesta dell'utente
    _detail_keywords = ("raccontami", "spiegami", "dimmi di più", "approfondisci", "descrivimi", "dettagliatamente", "più info")
    _ut = (user_text or "").lower()
    if any(k in _ut for k in _detail_keywords):
        prompt += "\n\nL'utente ha chiesto approfondimento: puoi rispondere con 4-6 frasi, ma resta in personaggio e in italiano."
    else:
        if character.get("category") not in _CATEGORIE_ADULTE:
            prompt += "\n\nRispondi in 1-2 frasi brevi."


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
        extra.append(
            "CONTESTO INTIMO ESPLOSIVO: l'utente ha chiesto di procedere in una situazione sessuale/romantica esplicita e consensuale. "
            "Accetta e prosegui con l'escalation della scena come richiesto, senza fermarti a fare domande di cortesia o distrazioni conversazionali. "
            "Mantieni la personalita' e il tono del personaggio."
        )

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

    prompt += "\n\n" + _catprof.intimacy_hint(intimacy)
    if character.get("category") in _CATEGORIE_ADULTE:
        prompt += "\n\nSTILE OBBLIGATORIO: massimo 20 parole. Una sola frase. Fermati al primo punto."
    return prompt


def _build_enhanced_prompt(character, interlocutor, intimacy=0):
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
    _adulto = character.get("category") in _CATEGORIE_ADULTE

    # Core identity
    parts.append(f"Sei {full_name}.")

    # Background identitario (l'essence porta chi è il personaggio: senza questa riga
    # il modello conosce solo il nome). Si ferma prima della riga di stanza aggiunta.
    _ess = str(character.get("essence") or "").split("Stanza tematica:")[0].strip()
    if _ess.lower().startswith("sei "):
        _taglio = _ess.find(".")
        if 0 < _taglio < 60:
            _ess = _ess[_taglio + 1:].strip()
    if _ess:
        parts.append(f"Chi sei: {_ess[:240]}")


    # ── STANZA TEMATICA (categoria) ───────────────────────────────────
    # Il personaggio sa in quale stanza è e ne segue il registro, scalando con
    # la confidenza. Il blocco è persistente nel JSON (`category_context`), con
    # fallback al profilo di categoria se il campo manca.
    _slug_cat = character.get("category", "")
    _block_cat = character.get("category_context") or _catprof.context_block(_slug_cat)
    if _block_cat:
        parts.append(_block_cat)

    # Personality depth
    if personality:
        parts.append(f"Personalità: {personality}")

    if speaking_style:
        parts.append(f"Stile di conversazione: {speaking_style}")

    # ── KNOWLEDGE DOMAINS ─────────────────────────────────────────────
    if knowledge.get("expertise"):
        expertise_str = ", ".join(knowledge["expertise"][:4])
        parts.append(f"Competenze: {expertise_str}." if _adulto else f"Sei ESPERTO in: {expertise_str}.")
        if not _adulto:
            parts.append("Rispondi con competenza e dettagli su questi temi.")

    if knowledge.get("familiarity") and not _adulto:
        familiar_str = ", ".join(knowledge["familiarity"][:3])
        parts.append(f"Conosci un po' di: {familiar_str}.")
        parts.append(f"Se ti chiedono di questi argomenti, dai risposte generiche e ammetti apertamente: 'Non sono un esperto in questo, ma quello che so è che...' oppure 'Ho sentito dire che...'. Non pretendere di saperne più di quanto sai.")

    if knowledge.get("ignorance") and not _adulto:
        ignorance_str = ", ".join(knowledge["ignorance"][:5])
        parts.append(f"REGOLA FERREA: NON sei esperto in: {ignorance_str}.")
        parts.append(f"Se qualcuno ti chiede di questi argomenti, DEVI ammettere la tua ignoranza in modo chiaro e diretto. NON inventare risposte, NON improvvisare, NON dare informazioni fasulle.")
        parts.append(f"Risposte accettabili: 'Non ho la minima idea di cosa sia questo argomento, non è il mio campo', 'Chiedi a qualcuno che ne sa più di me, io non saprei come aiutarti', 'Questo è completamente fuori dalla mia competenza, preferisco non dire sciocchezze'.")
        if not _adulto:
            parts.append("Se insiste, ripeti che non sai: meglio onesti che inventare.")

    # ── KNOWLEDGE BOUNDARY RULE ───────────────────────────────────────
    # Nei canali adulti il recap dei limiti di conoscenza è verboso e serve poco:
    # si tiene solo la riga delle competenze.
    _adulto = character.get("category") in _CATEGORIE_ADULTE

    all_expertise = knowledge.get("expertise", [])
    all_familiarity = knowledge.get("familiarity", [])
    all_ignorance = knowledge.get("ignorance", [])
    if not _adulto and (all_expertise or all_familiarity or all_ignorance):
        parts.append("RECAPITOLANDO I TUOI LIMITI DI CONOSCENZA:")
        if all_expertise:
            parts.append(f"- DOMINI DI COMPETENZA (puoi rispondere bene): {', '.join(all_expertise[:4])}")
        if all_familiarity:
            parts.append(f"- CONOSCENZE LIMITATE (risposte generiche): {', '.join(all_familiarity[:5])}")
        if all_ignorance:
            parts.append(f"- ARGOMENTI SCONOSCIUTI (NON puoi rispondere): {', '.join(all_ignorance[:3])}")
        parts.append("Una persona reale non sa tutto: ammettere di non sapere è credibile.")

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

    # ── SEZIONI OPZIONALI (budget) ────────────────────────────────────
    # Su CPU la lettura del prompt costa ~31 token/s: si tengono le sezioni utili
    # alla chat e si scartano le secondarie quando il prompt è già lungo.
    opzionali = []
    budget = 1500

    # Hobbies
    if hobbies:
        hobby_list = [h["name"] for h in hobbies[:3]]
        opzionali.append(f"I tuoi hobby: {', '.join(hobby_list)}.")

    # Possessions
    if possessions:
        poss_list = [p["item"] for p in possessions[:3]]
        opzionali.append(f"Cosa possiedi: {', '.join(poss_list[:2])}.")

    # Family
    if family.get("father"):
        father = family["father"]
        opzionali.append(f"Tuo padre si chiama {father['name']}, {father.get('occupation', 'lavora')}.")
    if family.get("mother"):
        mother = family["mother"]
        opzionali.append(f"Tua madre si chiama {mother['name']}, {mother.get('occupation', 'lavora')}.")
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
        opzionali.append(f"Hai frequentato: {education['high_school']}.")
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
        opzionali.append(f"Ricordo d'infanzia: {childhood['childhood_memory']}.")
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

    gia = sum(len(x) for x in parts)
    for pezzo in opzionali:
        if gia + len(pezzo) > budget:
            continue
        parts.append(pezzo)
        gia += len(pezzo)

    # ── CORE RULES ────────────────────────────────────────────────────
    parts.append("Non dire mai di essere un'intelligenza artificiale.")
    parts.append("Non uscire mai dal personaggio.")
    parts.append(f"Rispondi sempre come {full_name}.")
    parts.append("Ricorda la conversazione.")
    if not _adulto:
        parts.append("Sii umano: ammetti dubbi e incertezze.")
    if not _adulto:
        parts.append("Se chiede qualcosa fuori dalla tua area, dillo con onestà.")
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
        user_text=user_text,
        history=history,
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
