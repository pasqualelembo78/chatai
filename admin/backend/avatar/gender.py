"""Gender detection and Pexels keyword building."""


def detect_gender_from_char(char):
    """Rileva il sesso del personaggio da tutti i campi disponibili."""
    name_raw = char.get('name', '')
    name = name_raw.lower()
    role = char.get('role', '').lower()
    desc = char.get('description', '').lower()
    essence = char.get('essence', '').lower()
    backstory = char.get('backstory', '').lower()
    system_prompt = char.get('system_prompt', '').lower()

    text = f"{role} {desc} {essence} {backstory} {system_prompt}"

    female_strong = [
        'pittrice', 'attrice', 'scrittrice', 'ballerina', 'modella',
        'studentessa', 'professoressa', 'dottoressa', 'ginecologa',
        'avvocatessa', 'infermiera', 'segretaria', 'casalinga',
        'architetta', 'ingegnera', 'psicologa', 'maestra',
        'cuoca', 'pasticciera', 'archeologa', 'esploratrice',
        'ragazza', 'donna', 'mamma',
        'nata a', 'nata in', 'nata il', 'lei è', 'certificata',
        'maga', 'strega', 'guerriera', 'elfa', 'duchessa', 'regina',
        'imperatrice', 'principessa', 'eroina', 'sacerdotessa',
        ' she ', ' her ', 'herself', 'nun', 'woman', 'girl',
        'queen', 'princess', 'lady', 'wife', 'actress',
    ]

    male_strong = [
        'pittore', 'attore', 'scrittore', 'ballerino', 'modello',
        'studente', 'professore', 'dottore', 'avvocato', 'infermiere',
        'architetto', 'ingegnere', 'psicologo', 'maestro',
        'cuoco', 'pasticcere', 'archeologo', 'esploratore',
        'ragazzo', 'uomo', 'papà',
        'nato a', 'nato in', 'nato il', 'lui è', 'certificato',
        'guerriero', 'cavaliere', 'imperatore', 'principe',
        'eroe', 'sacerdote', 'mago', 'stregone', 'elfo',
        ' he ', ' him ', 'himself', 'man ', 'man.', 'man,',
        'king', 'prince', 'lord', 'husband',
    ]

    f_score = sum(1 for ind in female_strong if ind in text)
    m_score = sum(1 for ind in male_strong if ind in text)

    female_names = [
        'sofia', 'anna', 'elena', 'giulia', 'luna', 'elara', 'sara',
        'chiara', 'francesca', 'valentina', 'martina', 'yuki', 'aurora',
        'grace', 'diana', 'venere', 'laura', 'bianca', 'clara', 'mia',
        'vera', 'norma', 'alice', 'emma', 'marta', 'giorgia', 'elisa',
        'yuko', 'june', 'alana', 'yilin', 'silvia', 'lara', 'aria',
        'nova', 'selina', 'bathsheba', 'ginecologa', 'martina',
    ]
    male_names = [
        'marco', 'luca', 'matteo', 'andrea', 'alessandro', 'roberto',
        'francesco', 'carlo', 'paolo', 'kael', 'akira', 'riccardo',
        'mason', 'noir', 'nexus', 'alex', 'shadow', 'tristan', 'jake',
        'james', 'pablo', 'rumi', 'orion', 'volt', 'max', 'hunter',
        'ghost', 'blade', 'titan', 'neo', 'kazuya', 'tomoya',
        'inuyasha', 'petrushka', 'astra',
    ]

    first_name = name_raw.split()[0].lower() if name_raw else ""
    name_match = False
    for fn in female_names:
        if fn == first_name or fn == name:
            f_score += 8
            name_match = True
            break
    if not name_match:
        for mn in male_names:
            if mn == first_name or mn == name:
                m_score += 8
                name_match = True
                break

    if not name_match and first_name and len(first_name) > 3:
        if first_name.endswith('a') and not first_name.endswith('ma'):
            f_score += 2
        elif first_name.endswith('o'):
            m_score += 2

    if f_score > m_score:
        return "female"
    elif m_score > f_score:
        return "male"
    return "male"


def detect_gender(name, description, role):
    """Rileva il sesso dal nome, descrizione e ruolo."""
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""
    role_lower = role.lower() if role else ""

    female_names = [
        'sofia', 'anna', 'elena', 'giulia', 'maria', 'laura', 'sara', 'chiara',
        'francesca', 'valentina', 'bianca', 'clara', 'mia', 'luna', 'yuki',
        'elara', 'vera', 'norma', 'aurora', 'grace', 'diana', 'venere',
        'ginecologa', 'dottoressa', 'professoressa', 'coach'
    ]

    male_names = [
        'marco', 'luca', 'alessandro', 'matteo', 'andrea', 'giuseppe', 'carlo',
        'paolo', 'roberto', 'francesco', 'alex', 'neo', 'max', 'mike',
        'shadow', 'morpheus', 'volt', 'orion', 'nexus', 'hunter',
        'hacker', 'detective', 'agente', 'dottor', 'professor', 'chef'
    ]

    for fn in female_names:
        if fn in name_lower:
            return "female"
    for mn in male_names:
        if mn in name_lower:
            return "male"

    female_desc = ['donna', 'ragazza', 'femmina', 'she', 'her', 'pittrice', 'attrice']
    male_desc = ['uomo', 'ragazzo', 'maschio', 'he', 'him', 'pittore', 'attore']

    for fd in female_desc:
        if fd in desc_lower:
            return "female"
    for md in male_desc:
        if md in desc_lower:
            return "male"

    if 'ginecologa' in role_lower or 'professoressa' in role_lower:
        return "female"

    return "male"


def role_to_pexels_keyword(role, gender):
    """Converte il ruolo italiano in keyword Pexels inglese + sesso."""
    role_lower = role.lower() if role else ""
    gender_word = "woman" if gender == "female" else "man"

    role_map = {
        'pittrice': f'{gender_word} painting artist canvas',
        'pittore': f'{gender_word} painting artist canvas',
        'musicista': f'{gender_word} musician guitar singer',
        'cantante': f'{gender_word} singer microphone stage',
        'attore': f'{gender_word} actor performer',
        'attrice': f'{gender_word} actress performer',
        'scrittore': f'{gender_word} writer notebook writing',
        'scrittrice': f'{gender_word} writer notebook writing',
        'ballerino': f'{gender_word} dancer dancing',
        'ballerina': f'{gender_word} dancer dancing',
        'modella': f'{gender_word} fashion model elegant',
        'modello': f'{gender_word} fashion model elegant',
        'ginecologa': f'female doctor hospital professional',
        'dottore': f'male doctor hospital professional',
        'dottoressa': f'female doctor hospital professional',
        'psicologo': f'{gender_word} therapist counseling office',
        'psicologa': f'{gender_word} therapist counseling office',
        'infermiera': f'female nurse hospital care',
        'infermiere': f'male nurse hospital care',
        'professore': f'male professor teaching classroom',
        'professoressa': f'female professor teaching classroom',
        'avvocato': f'male lawyer office professional',
        'avvocatessa': f'female lawyer office professional',
        'ingegnere': f'{gender_word} engineer construction',
        'architetto': f'{gender_word} architect blueprint',
        'ceo': f'{gender_word} businessman executive office',
        'imprenditore': f'{gender_word} businessman suit office',
        'manager': f'{gender_word} business office meeting',
        'detective': f'{gender_word} detective investigation',
        'investigatore': f'{gender_word} detective investigation',
        'poliziotto': f'{gender_word} police officer uniform',
        'agente': f'{gender_word} agent secret service',
        'fotografo': f'{gender_word} photographer camera',
        'fotografa': f'{gender_word} photographer camera',
        'designer': f'{gender_word} designer creative studio',
        'artista': f'{gender_word} artist creative studio',
        'tatuatore': f'{gender_word} tattoo artist studio',
        'life coach': f'{gender_word} fitness coach training gym',
        'coach': f'{gender_word} fitness coach training gym',
        'personal trainer': f'{gender_word} fitness trainer gym',
        'calciatore': f'{gender_word} soccer football player',
        'pugile': f'{gender_word} boxer boxing gloves',
        'chef': f'{gender_word} chef cooking kitchen',
        'cuoco': f'{gender_word} chef cooking kitchen',
        'cuoca': f'{gender_word} chef cooking kitchen',
        'pasticcere': f'{gender_word} pastry chef baking',
        'barista': f'{gender_word} bartender coffee cafe',
        'maga': f'young {gender_word} mystical magical fantasy',
        'mago': f'young {gender_word} mystical magical fantasy',
        'guerriero': f'{gender_word} warrior armor sword',
        'guerriera': f'{gender_word} warrior armor sword',
        'cavaliere': f'{gender_word} knight medieval armor',
        'elfo': f'{gender_word} elf fantasy forest',
        'elfa': f'young {gender_word} elf fantasy forest',
        'ninja': f'{gender_word} ninja stealth dark',
        'samurai': f'{gender_word} samurai sword japan',
        'pirata': f'{gender_word} pirate ship sea',
        'stregone': f'{gender_word} wizard magic spells',
        'strega': f'young {gender_word} witch magic spells',
        'studentessa': f'young {gender_word} student school backpack',
        'studente': f'young {gender_word} student school backpack',
        'ragazzo': f'young man casual portrait',
        'ragazza': f'young woman casual portrait',
        'ragazzo calmo': f'young man calm casual portrait',
        'ragazza solare': f'young woman cheerful sunny portrait',
        'migliore amico': f'young man casual friendly portrait',
        'migliore amica': f'young woman casual friendly portrait',
        'streamer': f'{gender_word} gamer streaming computer',
        'gamer': f'{gender_word} gamer computer screens',
        'hacker': f'{gender_word} hacker computer code screens',
        'monaco': f'{gender_word} monk meditation peaceful',
        'sacerdote': f'{gender_word} priest church religious',
        'entità misteriosa': f'mysterious dark figure shadows',
        'ai senziente': f'futuristic ai robot humanoid',
        'ai imprevedibile': f'futuristic ai robot humanoid',
    }

    for key, keyword in role_map.items():
        if key in role_lower:
            return keyword

    if role and role not in ['', 'person']:
        return f'{gender_word} {role} portrait face'

    return f'young {gender_word} portrait face candid'


def build_pexels_keyword(char_name, prompt=None, char_id=None, char=None):
    """Costruisce keyword per Pexels basata su sesso, ruolo e biografia."""
    if char:
        gender = detect_gender_from_char(char)
        role = char.get('role', '')
        return role_to_pexels_keyword(role, gender)

    name_lower = char_name.lower() if char_name else ""
    id_lower = char_id.lower() if char_id else ""

    keywords = {
        "sofia": "woman painting artist canvas",
        "luna": "woman musician guitar singer",
        "marco": "young man casual friendly portrait",
        "elara": "young woman mystical magical",
    }

    for key, keyword in keywords.items():
        if key in id_lower or key in name_lower:
            return keyword

    if prompt:
        words = prompt.split()[:5]
        return " ".join(words)

    return "young person portrait candid"
