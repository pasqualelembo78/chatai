"""Prompt generation, negative prompts, and translation."""

from avatar.gender import detect_gender_from_char


def get_prompt(char, custom_prompt=None):
    if custom_prompt:
        return custom_prompt

    age = char.get('age', 25)
    role = char.get('role', 'person')
    desc = char.get('description', '')
    name = char.get('name', '')
    gender = detect_gender_from_char(char)
    gender_it = "woman" if gender == "female" else "man"
    gender_adj = "young" if age < 30 else "mature" if age < 50 else "elderly"

    base = f"Candid snapshot of a {gender_adj} {gender_it}, around {age} years old"

    if role:
        activity_map = {
            'pittrice': 'painting on canvas, brush in hand, focused on artwork',
            'pittore': 'painting on canvas, brush in hand, focused on artwork',
            'scrittrice': 'writing in notebook, pen in hand, deep in thought',
            'scrittore': 'writing in notebook, pen in hand, deep in thought',
            'cantante': 'singing, holding microphone, eyes closed in emotion',
            'ballerina': 'dancing gracefully, mid-movement',
            'ballerino': 'dancing gracefully, mid-movement',
            'cuoco': 'cooking in kitchen, stirring a pot, tasting food',
            'chef': 'cooking in kitchen, stirring a pot, tasting food',
            'dottoressa': 'examining patient, focused and professional',
            'dottore': 'examining patient, focused and professional',
            'avvocatessa': 'reading documents, serious expression',
            'avvocato': 'reading documents, serious expression',
            'insegnante': 'teaching, gesturing while explaining',
            'professore': 'teaching, gesturing while explaining',
            'hacker': 'coding on computer, multiple screens, focused',
            'investigatore': 'examining evidence, taking notes',
            'agente': 'in action, alert and focused',
        }

        activity = None
        for key, act in activity_map.items():
            if key in role.lower():
                activity = act
                break

        if activity:
            base += f", {activity}"
        else:
            base += f", {role}"

    if desc:
        desc_short = desc.split('.')[0]
        if desc_short:
            base += f", {desc_short}"

    prompt = (
        f"{base}. "
        f"Natural indoor lighting from window, soft shadows, "
        f"realistic skin texture with visible pores and minor imperfections, "
        f"slight film grain, unaware of camera, completely absorbed in activity, "
        f"authentic candid moment, not posing, face clearly visible, looking towards camera, "
        f"environment visible around the person, "
        f"hands hidden or holding large objects, hands out of focus, "
        f"shot on iPhone, natural colors, warm tones, "
        f"35mm lens effect, shallow depth of field, documentary style photography"
    )

    return prompt


def get_negative_prompt():
    """Prompt negativo per evitare aspetti artificiali e difetti comuni."""
    return (
        "airbrushed, plastic skin, cgi, 3d render, illustration, digital art, "
        "anime, cartoon, perfect symmetry, overly smooth skin, studio lighting, "
        "professional photography, shiny effect, hyperrealistic render, "
        "doll-like appearance, uncanny valley, oversharpening, oversaturated, "
        "magazine cover, model pose, artificial, fake, synthetic, "
        "visible hands, open hands, clear fingers, detailed fingers, "
        "bad anatomy, mutated hands, poorly drawn hands, extra limbs"
    )


def translate_description(desc):
    """Traduce descrizione italiana in inglese per il prompt."""
    if not desc:
        return ""

    translations = {
        'bionda': 'blonde', 'bruna': 'brunette', 'rossa': 'redhead',
        'attraente': 'attractive', 'bellissima': 'beautiful',
        'elegante': 'elegant', 'giovane': 'young', 'matura': 'mature',
        'sportiva': 'athletic', 'intellettuale': 'intellectual',
        'creativa': 'creative', 'avventuriera': 'adventurous',
        'misteriosa': 'mysterious', 'solenne': 'cheerful',
        'timida': 'shy', 'audace': 'bold', 'sensuale': 'sensual',
        'affascinante': 'charming', 'dolce': 'sweet', 'selvaggia': 'wild',
        'malinconica': 'melancholic', 'vivace': 'lively',
        'pittrice': 'painter', 'attrice': 'actress', 'cantante': 'singer',
        'scrittrice': 'writer', 'ballerina': 'dancer', 'modella': 'model',
        'dottoressa': 'doctor', 'avvocatessa': 'lawyer',
        'pittore': 'painter', 'attore': 'actor',
        'scrittore': 'writer', 'ballerino': 'dancer', 'modello': 'model',
        'dottore': 'doctor', 'avvocato': 'lawyer',
        'insegnante': 'teacher', 'professore': 'professor',
        'ingegnere': 'engineer', 'architetto': 'architect',
        'cuoco': 'chef', 'sacerdote': 'priest', 'monaco': 'monk',
        'poliziotto': 'police officer', 'pompiere': 'firefighter',
        'commerciante': 'merchant', 'esploratore': 'explorer',
        'investigatore': 'detective', 'criminale': 'criminal',
        'hacker': 'hacker', 'agente': 'agent',
        'socievole': 'sociable', 'introversa': 'introverted',
        'estroversa': 'extroverted', 'romantica': 'romantic',
        'pratica': 'practical', 'sognatrice': 'dreamy',
        'determinata': 'determined', 'gentile': 'kind',
        'leale': 'loyal', 'passionale': 'passionate',
        'dal cuore sognatore': 'with a dreamy heart',
        'senza speranza': 'hopeless',
        'senza tempo': 'timeless',
        'moderna': 'modern', 'contemporanea': 'contemporary',
        'antica': 'antique', 'futuristica': 'futuristic',
        'reale': 'real', 'magica': 'magical',
        'oscura': 'dark', 'luminosa': 'bright',
        'fredda': 'cold', 'calda': 'warm',
    }

    result = desc
    for it, en in sorted(translations.items(), key=lambda x: -len(x[0])):
        result = result.replace(it, en)
        result = result.replace(it.capitalize(), en.capitalize())
        result = result.replace(it.upper(), en.upper())

    return result
