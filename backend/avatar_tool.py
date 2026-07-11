#!/usr/bin/env python3
"""
ChatAI Avatar Tool — unico script per generare e animare avatar.

Usage:
  # Generare avatar
  python3 avatar_tool.py --generate luna
  python3 avatar_tool.py --generate-all --model sd3-medium
  python3 avatar_tool.py --list-missing

  # Animare avatar
  python3 avatar_tool.py --animate luna
  python3 avatar_tool.py --animate-all

  # Info
  python3 avatar_tool.py --list-avatars
"""

import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARACTERS_FILE = os.path.join(ROOT, "backend", "characters.py")
DRAWABLE_DIR = os.path.join(ROOT, "app", "src", "main", "res")
STATIC_AVATARS = os.path.join(ROOT, "backend", "static", "avatars")
TOKEN_FILE = os.path.join(ROOT, "backend", ".hf_token")

# Carica .env
ENV_FILE = os.path.join(ROOT, "backend", ".env")
if os.path.isfile(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

MODELS = {
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",
    "sd3-medium": "stabilityai/stable-diffusion-3-medium-diffusers",
    "pexels": "free",  # Foto reali da Pexels
    "pollinations": "free",
    "tpde": "free",  # ThisPersonDoesNotExist
    "pravatar": "free",  # PrAvatar
    "dicebear": "free",  # DiceBear Avatars
}

# ANDROID_SIZES rimosso: gli avatar vengono caricati dal server a runtime tramite Glide.
# Le cartelle drawable-* non servono più.


# ─── Generazione immagini gratuite ────────────────────────────────

def generate_image_pollinations(prompt, char_id, api_key=None, negative_prompt=None):
    """Genera immagine full-body con Pollinations.AI.
    
    Tier e limiti:
    - Anonymous: 1 req/15 sec (~5760/giorno)
    - Seed (gratis): 1 req/5 sec (~17280/giorno) - registrarsi su auth.pollinations.ai
    - Flower (pagato): 1 req/3 sec
    
    Con api_key si usano gli endpoint autenticati (gen.pollinations.ai) con limiti migliori.
    """
    import requests
    from PIL import Image
    import urllib.parse

    encoded_prompt = urllib.parse.quote(prompt)
    seed = abs(hash(char_id)) % 10000
    
    # Costruisci URL con parametri
    params = f"width=512&height=768&seed={seed}&model=flux&nologo=true&private=true"
    
    if negative_prompt:
        encoded_neg = urllib.parse.quote(negative_prompt)
        params += f"&negative_prompt={encoded_neg}"
    
    # Usa endpoint autenticato se API key fornita
    if api_key:
        url = f"https://gen.pollinations.ai/prompt/{encoded_prompt}?{params}"
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?{params}"
        headers = {}

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=120)
            if resp.status_code == 200:
                return resp.content
            elif resp.status_code == 429:
                wait = 15 * (attempt + 1)  # 15, 30, 45 sec
                print(f"  Rate limit Pollinations, attesa {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  Errore Pollinations.AI: HTTP {resp.status_code}")
                break
        except requests.exceptions.Timeout:
            print(f"  Timeout Pollinations (tentativo {attempt+1}/3)")
            time.sleep(5)
        except Exception as e:
            print(f"  Errore Pollinations.AI: {e}")
            break

    return None


def generate_image_pexels(keyword, api_key, orientation="portrait"):
    """Cerca e scarica foto reali da Pexels.
    
    Args:
        keyword: Parole chiave per la ricerca (es. "woman painting artist")
        api_key: API key Pexels
        orientation: "portrait", "landscape", o "square"
    
    Returns:
        bytes dell'immagine o None se fallisce
    """
    import requests
    
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {
        "query": keyword,
        "per_page": 10,
        "orientation": orientation
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get('photos', [])
            
            if photos:
                # Seleziona foto casuale tra le prime 5
                import random
                photo = random.choice(photos[:5])
                photo_url = photo.get('src', {}).get('large', '')
                photographer = photo.get('photographer', 'Unknown')
                
                print(f"  Pexels: trovata foto di {photographer}")
                
                # Scarica l'immagine
                img_resp = requests.get(photo_url, timeout=60)
                if img_resp.status_code == 200:
                    return img_resp.content
        else:
            print(f"  Errore Pexels: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  Errore Pexels: {e}")
    
    return None


def detect_gender_from_char(char):
    """Rileva il sesso del personaggio da tutti i campi disponibili.
    Usa indicatori affidabili (professioni, aggettivi) ed evita riferimenti 
    ai familiari (padre/madre/fratello) che non indicano il sesso del personaggio.
    """
    name_raw = char.get('name', '')
    name = name_raw.lower()
    role = char.get('role', '').lower()
    desc = char.get('description', '').lower()
    essence = char.get('essence', '').lower()
    backstory = char.get('backstory', '').lower()
    system_prompt = char.get('system_prompt', '').lower()
    
    text = f"{role} {desc} {essence} {backstory} {system_prompt}"
    
    # Indicatori femminili affidabili (NON familiari)
    female_strong = [
        # Italiano - professioni femminili (suffisso -trice/-essa/-a)
        'pittrice', 'attrice', 'scrittrice', 'ballerina', 'modella',
        'studentessa', 'professoressa', 'dottoressa', 'ginecologa',
        'avvocatessa', 'infermiera', 'segretaria', 'casalinga',
        'architetta', 'ingegnera', 'psicologa', 'maestra',
        'cuoca', 'pasticciera', 'archeologa', 'esploratrice',
        'ragazza', 'donna', 'mamma',
        'nata a', 'nata in', 'nata il', 'lei è', 'certificata',
        'maga', 'strega', 'guerriera', 'elfa', 'duchessa', 'regina',
        'imperatrice', 'principessa', 'eroina', 'sacerdotessa',
        # Inglese - pronomi diretti (NON family members)
        ' she ', ' her ', 'herself', 'nun', 'woman', 'girl',
        'queen', 'princess', 'lady', 'wife', 'actress',
    ]
    
    # Indicatori maschili affidabili (NON familiari)
    male_strong = [
        # Italiano - professioni maschili (suffisso -ore/-iere/-o)
        'pittore', 'attore', 'scrittore', 'ballerino', 'modello',
        'studente', 'professore', 'dottore', 'avvocato', 'infermiere',
        'architetto', 'ingegnere', 'psicologo', 'maestro',
        'cuoco', 'pasticcere', 'archeologo', 'esploratore',
        'ragazzo', 'uomo', 'papà',
        'nato a', 'nato in', 'nato il', 'lui è', 'certificato',
        'guerriero', 'cavaliere', 'imperatore', 'principe',
        'eroe', 'sacerdote', 'mago', 'stregone', 'elfo',
        # Inglese - pronomi diretti (NON family members)
        ' he ', ' him ', 'himself', 'man ', 'man.', 'man,',
        'king', 'prince', 'lord', 'husband',
    ]
    
    f_score = sum(1 for ind in female_strong if ind in text)
    m_score = sum(1 for ind in male_strong if ind in text)
    
    # IMPORTANTE: le professioni del personaggio sono nel system_prompt principale,
    # ma le professioni dei familiari compaiono dopo "tuo padre/tua madre".
    # Riduciamo il peso se il match è vicino a "tuo/tua"
    # Verifica contesto per professioni ambigue
    
    # Nomi noti - female (peso molto alto, override altri segnali)
    female_names = [
        'sofia', 'anna', 'elena', 'giulia', 'luna', 'elara', 'sara',
        'chiara', 'francesca', 'valentina', 'martina', 'yuki', 'aurora',
        'grace', 'diana', 'venere', 'laura', 'bianca', 'clara', 'mia',
        'vera', 'norma', 'alice', 'emma', 'marta', 'giorgia', 'elisa',
        'yuko', 'june', 'alana', 'yilin', 'silvia', 'lara', 'aria',
        'nova', 'selina', 'bathsheba', 'ginecologa', 'martina',
    ]
    # Nomi noti - male (peso molto alto)
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
    
    # Se il nome non è noto, usa euristica desinenza (-a femminile, -o maschile)
    # Peso basso per evitare errori con nomi non-italiani
    if not name_match and first_name and len(first_name) > 3:
        if first_name.endswith('a') and not first_name.endswith('ma'):
            f_score += 2
        elif first_name.endswith('o'):
            m_score += 2
    
    if f_score > m_score:
        return "female"
    elif m_score > f_score:
        return "male"
    return "male"  # default (maggioranza nel dataset)


def role_to_pexels_keyword(role, gender):
    """Converte il ruolo italiano in keyword Pexels inglese + sesso."""
    role_lower = role.lower() if role else ""
    gender_word = "woman" if gender == "female" else "man"
    
    # Mapping ruolo italiano -> keyword inglese con sesso
    role_map = {
        # Professioni
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
        
        # Medici
        'ginecologa': f'female doctor hospital professional',
        'dottore': f'male doctor hospital professional',
        'dottoressa': f'female doctor hospital professional',
        'psicologo': f'{gender_word} therapist counseling office',
        'psicologa': f'{gender_word} therapist counseling office',
        'infermiera': f'female nurse hospital care',
        'infermiere': f'male nurse hospital care',
        
        # Professionisti
        'professore': f'male professor teaching classroom',
        'professoressa': f'female professor teaching classroom',
        'avvocato': f'male lawyer office professional',
        'avvocatessa': f'female lawyer office professional',
        'ingegnere': f'{gender_word} engineer construction',
        'architetto': f'{gender_word} architect blueprint',
        'ceo': f'{gender_word} businessman executive office',
        'imprenditore': f'{gender_word} businessman suit office',
        'manager': f'{gender_word} business office meeting',
        
        # Forze dell'ordine
        'detective': f'{gender_word} detective investigation',
        'investigatore': f'{gender_word} detective investigation',
        'poliziotto': f'{gender_word} police officer uniform',
        'agente': f'{gender_word} agent secret service',
        
        # Creativi/artisti
        'fotografo': f'{gender_word} photographer camera',
        'fotografa': f'{gender_word} photographer camera',
        'designer': f'{gender_word} designer creative studio',
        'artista': f'{gender_word} artist creative studio',
        'tatuatore': f'{gender_word} tattoo artist studio',
        
        # Sport/fitness
        'life coach': f'{gender_word} fitness coach training gym',
        'coach': f'{gender_word} fitness coach training gym',
        'personal trainer': f'{gender_word} fitness trainer gym',
        'calciatore': f'{gender_word} soccer football player',
        'pugile': f'{gender_word} boxer boxing gloves',
        
        # Cucina
        'chef': f'{gender_word} chef cooking kitchen',
        'cuoco': f'{gender_word} chef cooking kitchen',
        'cuoca': f'{gender_word} chef cooking kitchen',
        'pasticcere': f'{gender_word} pastry chef baking',
        'barista': f'{gender_word} bartender coffee cafe',
        
        # Fantasy/narrativi
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
        
        # Studenti
        'studentessa': f'young {gender_word} student school backpack',
        'studente': f'young {gender_word} student school backpack',
        'ragazzo': f'young man casual portrait',
        'ragazza': f'young woman casual portrait',
        'ragazzo calmo': f'young man calm casual portrait',
        'ragazza solare': f'young woman cheerful sunny portrait',
        'migliore amico': f'young man casual friendly portrait',
        'migliore amica': f'young woman casual friendly portrait',
        
        # Altro
        'streamer': f'{gender_word} gamer streaming computer',
        'gamer': f'{gender_word} gamer computer screens',
        'hacker': f'{gender_word} hacker computer code screens',
        'monaco': f'{gender_word} monk meditation peaceful',
        'sacerdote': f'{gender_word} priest church religious',
        'entità misteriosa': f'mysterious dark figure shadows',
        'ai senziente': f'futuristic ai robot humanoid',
        'ai imprevedibile': f'futuristic ai robot humanoid',
    }
    
    # Cerca keyword corrispondente
    for key, keyword in role_map.items():
        if key in role_lower:
            return keyword
    
    # Se ruolo non trovato, usa ruolo + sesso + portrait
    if role and role not in ['', 'person']:
        return f'{gender_word} {role} portrait face'
    
    # Default
    return f'young {gender_word} portrait face candid'


def build_pexels_keyword(char_name, prompt=None, char_id=None, char=None):
    """Costruisce keyword per Pexels basata su sesso, ruolo e biografia."""
    
    # Se abbiamo il personaggio completo, usa detection automatica
    if char:
        gender = detect_gender_from_char(char)
        role = char.get('role', '')
        return role_to_pexels_keyword(role, gender)
    
    # Fallback: mapping hardcoded per personaggi noti
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
    
    # Default: usa il prompt se disponibile
    if prompt:
        words = prompt.split()[:5]
        return " ".join(words)
    
    return "young person portrait candid"


def generate_image_free(model_id, char_id, char_name, prompt=None, api_key=None, negative_prompt=None, char=None):
    """Genera avatar usando API gratuite con fallback automatico.
    
    Provider gratuiti disponibili:
    - pexels: Foto reali da database, no AI, qualità professionale
    - pollinations: FLUX modello, no key, 1 req/15 sec (anonymous)
    - thispersondoesnotexist: Facce casuali, no key, illimitato
    - pravatar: Avatar casuali, no key, illimitato
    
    Ritorna i bytes dell'immagine o None se fallisce.
    """
    import requests
    from PIL import Image

    # Usa negative prompt di default se non fornito
    if not negative_prompt:
        negative_prompt = get_negative_prompt()

    # 1. Prova Pexels prima (foto reali, non AI)
    pexels_key = os.environ.get('PEXELS_API_KEY', '')
    if pexels_key and model_id in ["free", "pexels", "pollinations"]:
        # Costruisci keyword basata su carattere
        keyword = build_pexels_keyword(char_name, prompt, char_id, char)
        result = generate_image_pexels(keyword, pexels_key)
        if result:
            return result
    
    # 2. Prova Pollinations (migliore qualità AI)
    if model_id in ["free", "pollinations"]:
        if not prompt:
            prompt = (
                f"Candid photo of a young person, "
                f"natural indoor lighting, realistic skin texture, "
                f"casual pose, shot on iPhone"
            )
        result = generate_image_pollinations(prompt, char_id, api_key, negative_prompt)
        if result:
            return result
    
    # 3. Fallback: ThisPersonDoesNotExist (illimitato, solo facce)
    if model_id in ["free", "pexels", "pollinations", "tpde"]:
        try:
            url = f"https://thispersondoesnotexist.com/?seed={abs(hash(char_id))}"
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 10000:
                return resp.content
        except Exception as e:
            print(f"  Fallback TPDE fallito: {e}")

    # 4. Fallback: PrAvatar (illimitato, avatar casuali)
    if model_id in ["free", "pexels", "pollinations", "pravatar"]:
        try:
            url = f"https://i.pravatar.cc/512?u={char_id}"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except Exception as e:
            print(f"  Fallback PrAvatar fallito: {e}")

    # 5. Fallback: DiceBear Avatars (illimitato, stili multipli)
    if model_id in ["free", "pexels", "pollinations", "dicebear"]:
        try:
            # Stile avatars basato sulla categoria
            styles = ["adventurer", "avataaars", "big-ears", "fun-emoji", "lorelei"]
            style_idx = abs(hash(char_id)) % len(styles)
            style = styles[style_idx]
            url = f"https://api.dicebear.com/7.x/{style}/png?seed={char_id}&size=512"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except Exception as e:
            print(f"  Fallback DiceBear fallito: {e}")

    return None


# ─── Generazione biografia italiana con Groq ──────────────────────

def generate_italian_biography(char, groq_token):
    """Genera biografia completa in italiano usando Groq API."""
    import requests

    prompt = f"""Sei uno scrittore creativo specializzato in personaggi per roleplay interattivo.
Genera una biografia completa in ITALIANO per il seguente personaggio.

DATI PERSONAGGIO:
- Nome: {char.get('name', 'Sconosciuto')}
- Età: {char.get('age', 25)} anni
- Ruolo: {char.get('role', 'personaggio')}
- Categoria: {char.get('category', 'generale')}
- Descrizione breve: {char.get('description', '')}

 Genera ESATTAMENTE questo formato (in italiano, senza markdown, senza code block):

DESCRIPTION: [descrizione una riga del personaggio]
BACKSTORY: [storia completa del personaggio in 3-4 frasi]
PERSONALITY: [tratti di personalità in 2-3 frasi]
SPEAKING_STYLE: [stile di parlato in 2 frasi]
HOBBIES: [lista hobby separati da virgola, formato: nome (livello)]
OPENING_SCENARIO: [ambientazione iniziale per il roleplay, 2-3 frasi descriptive, es: 'Sei in un locale buio con musica soft...']

Importante:
- Tutto in ITALIANO
- Scrivi come se il personaggio fosse REALE
- L'OPENING_SCENARIO deve essere un'ambientazione vivid e coinvolgente
- Idevi essere coerenti con l'età e il ruolo"""

    headers = {"Authorization": f"Bearer {groq_token}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=30
        )
        if resp.status_code != 200:
            print(f"  Errore Groq {resp.status_code}: {resp.text[:200]}")
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        return parse_biography_response(content)
    except Exception as e:
        print(f"  Errore generazione biografia: {e}")
        return None


def parse_biography_response(text):
    """Parse della risposta del modello in campi strutturati."""
    result = {}
    lines = text.strip().split("\n")
    current_key = None
    current_value = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        for key in ["DESCRIPTION", "BACKSTORY", "PERSONALITY", "SPEAKING_STYLE", "HOBBIES", "OPENING_SCENARIO"]:
            if line.upper().startswith(f"{key}:"):
                if current_key and current_value:
                    result[current_key] = " ".join(current_value)
                current_key = key.lower()
                current_value = [line[len(key)+1:].strip()]
                break
        else:
            if current_key:
                current_value.append(line)

    if current_key and current_value:
        result[current_key] = " ".join(current_value)

    if "hobbies" in result:
        hobbies = []
        for part in result["hobbies"].split(","):
            part = part.strip()
            if "(" in part and part.endswith(")"):
                name, skill = part.rsplit("(", 1)
                hobbies.append({"name": name.strip(), "skill": skill.rstrip(")")})
            else:
                hobbies.append({"name": part, "skill": "principiante"})
        result["hobbies"] = hobbies

    return result


def generate_italian_description_only(char, groq_token):
    """Genera solo la descrizione in italiano usando Groq API."""
    import requests

    prompt = f"""Sei uno scrittore creativo. Genera una descrizione breve e accattivante in ITALIANO per il seguente personaggio.

DATI PERSONAGGIO:
- Nome: {char.get('name', 'Sconosciuto')}
- Età: {char.get('age', 25)} anni
- Ruolo: {char.get('role', 'personaggio')}
- Categoria: {char.get('category', 'generale')}

Genera ESATTAMENTE questo formato (in italiano, senza markdown, senza code block):

DESCRIPTION: [descrizione una riga del personaggio, massimo 100 caratteri]

Importante:
- Tutto in ITALIANO
- La descrizione deve essere breve e d'impatto
- Deve catturare l'essenza del personaggio"""

    headers = {"Authorization": f"Bearer {groq_token}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 150,
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=20
        )
        if resp.status_code != 200:
            print(f"  Errore Groq {resp.status_code}: {resp.text[:200]}")
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        # Estrai solo la descrizione
        for line in content.strip().split("\n"):
            if line.upper().startswith("DESCRIPTION:"):
                return line[len("DESCRIPTION:"):].strip()
        return content.strip()
    except Exception as e:
        print(f"  Errore generazione descrizione: {e}")
        return None


def update_characters_py_full(char_id, bio_data):
    """Aggiorna characters.py con biografia completa italiana."""
    with open(CHARACTERS_FILE) as f:
        content = f.read()

    marker = f'"id": "{char_id}"'
    idx = content.find(marker)
    if idx == -1:
        print(f"  WARNING: '{char_id}' non trovato in characters.py")
        return False

    char_block_start = content.rfind("{", 0, idx)
    char_block_end = content.find("}", idx)
    if char_block_start == -1 or char_block_end == -1:
        return False

    old_block = content[char_block_start:char_block_end + 1]

    if "backstory" in old_block:
        print(f"  Biografia già presente per '{char_id}', salto")
        return True

    fields_to_add = []
    if "description" in bio_data:
        fields_to_add.append(f'"description": "{bio_data["description"]}"')
    if "backstory" in bio_data:
        fields_to_add.append(f'"backstory": "{bio_data["backstory"]}"')
    if "personality" in bio_data:
        fields_to_add.append(f'"personality": "{bio_data["personality"]}"')
    if "speaking_style" in bio_data:
        fields_to_add.append(f'"speaking_style": "{bio_data["speaking_style"]}"')
    if "hobbies" in bio_data:
        hobbies_str = json.dumps(bio_data["hobbies"], ensure_ascii=False)
        fields_to_add.append(f'"hobbies": {hobbies_str}')
    if "opening_scenario" in bio_data:
        fields_to_add.append(f'"opening_scenario": "{bio_data["opening_scenario"]}"')

    if not fields_to_add:
        return False

    insert_pos = old_block.rfind("}")
    new_fields = ",\n        " + ",\n        ".join(fields_to_add)
    new_block = old_block[:insert_pos] + new_fields + "\n    }" + old_block[insert_pos + 1:]

    content = content[:char_block_start] + new_block + content[char_block_end + 1:]

    with open(CHARACTERS_FILE, "w") as f:
        f.write(content)

    print(f"  characters.py aggiornato con biografia per '{char_id}'")
    return True

API_URL = "https://router.huggingface.co/hf-inference/models/"


# ─── Parsing characters ──────────────────────────────────────────

def parse_characters():
    import re
    chars = []
    with open(CHARACTERS_FILE) as f:
        content = f.read()
    i = 0
    while True:
        start = content.find("{", i)
        if start == -1:
            break
        depth = 0
        j = start
        while j < len(content):
            if content[j] == "{":
                depth += 1
            elif content[j] == "}":
                depth -= 1
                if depth == 0:
                    block = content[start:j+1]
                    m = re.search(r'"id"\s*:\s*"([^"]+)"', block)
                    if m:
                        cat_m = re.search(r'"category"\s*:\s*"([^"]+)"', block)
                        if cat_m:
                            cid = m.group(1)
                            cat = cat_m.group(1)
                            name_m = re.search(r'"name"\s*:\s*"([^"]+)"', block)
                            name = name_m.group(1) if name_m else cid
                            desc_m = re.search(r'"description"\s*:\s*"([^"]+)"', block)
                            desc = desc_m.group(1) if desc_m else ""
                            age_m = re.search(r'"age"\s*:\s*(\d+)', block)
                            age = int(age_m.group(1)) if age_m else 25
                            role_m = re.search(r'"role"\s*:\s*"([^"]+)"', block)
                            role = role_m.group(1) if role_m else ""
                            avi_m = re.search(r'"avatar_image"\s*:\s*"([^"]+)"', block)
                            avatar_image = avi_m.group(1) if avi_m else ""
                            chars.append({"id": cid, "name": name, "category": cat,
                                          "description": desc, "age": age, "role": role,
                                          "avatar_image": avatar_image})
                    j += 1
                    break
            j += 1
        i = j
    return chars


# ─── Generazione immagini ────────────────────────────────────────

def get_prompt(char, custom_prompt=None):
    if custom_prompt:
        return custom_prompt

    # Dati personaggio
    age = char.get('age', 25)
    role = char.get('role', 'person')
    desc = char.get('description', '')
    name = char.get('name', '')
    gender = detect_gender_from_char(char)
    gender_it = "woman" if gender == "female" else "man"
    gender_adj = "young" if age < 30 else "mature" if age < 50 else "elderly"

    # Prompt base naturale - foto scattata da qualcuno che entra nella stanza
    base = f"Candid snapshot of a {gender_adj} {gender_it}, around {age} years old"

    # Aggiungi ruolo/attività se disponibile
    if role:
        # Se è un'attività specifica, mostrala in azione
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
        
        # Cerca attività corrispondente
        activity = None
        for key, act in activity_map.items():
            if key in role.lower():
                activity = act
                break
        
        if activity:
            base += f", {activity}"
        else:
            base += f", {role}"

    # Aggiungi descrizione se disponibile (in italiano, va bene così)
    if desc:
        # Prendi solo la prima frase per non rendere il prompt troppo lungo
        desc_short = desc.split('.')[0]
        if desc_short:
            base += f", {desc_short}"

    # Aggiungi dettagli ambientazione naturale - foto con volto visibile
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


def detect_gender(name, description, role):
    """Rileva il sesso dal nome, descrizione e ruolo."""
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""
    role_lower = role.lower() if role else ""
    
    # Nomi femminili italiani comuni
    female_names = [
        'sofia', 'anna', 'elena', 'giulia', 'maria', 'laura', 'sara', 'chiara',
        'francesca', 'valentina', 'bianca', 'clara', 'mia', 'luna', 'yuki',
        'elara', 'vera', 'norma', 'aurora', 'grace', 'diana', 'venere',
        'ginecologa', 'dottoressa', 'professoressa', 'coach'
    ]
    
    # Nomi maschili italiani comuni
    male_names = [
        'marco', 'luca', 'alessandro', 'matteo', 'andrea', 'giuseppe', 'carlo',
        'paolo', 'roberto', 'francesco', 'alex', 'neo', 'max', 'mike',
        'shadow', 'morpheus', 'volt', 'orion', 'nexus', 'hunter',
        'hacker', 'detective', 'agente', 'dottor', 'professor', 'chef'
    ]
    
    # Controlla nome
    for fn in female_names:
        if fn in name_lower:
            return "female"
    for mn in male_names:
        if mn in name_lower:
            return "male"
    
    # Controlla descrizione
    female_desc = ['donna', 'ragazza', 'femmina', 'she', 'her', 'pittrice', 'attrice']
    male_desc = ['uomo', 'ragazzo', 'maschio', 'he', 'him', 'pittore', 'attore']
    
    for fd in female_desc:
        if fd in desc_lower:
            return "female"
    for md in male_desc:
        if md in desc_lower:
            return "male"
    
    # Default: basato sul ruolo
    if 'ginecologa' in role_lower or 'professoressa' in role_lower:
        return "female"
    
    return "male"  # Default


def translate_description(desc):
    """Traduce descrizione italiana in inglese per il prompt."""
    if not desc:
        return ""
    
    # Mapping italiano -> inglese (ordine: prima parole lunghe, poi corte)
    translations = {
        # Aspetto fisico
        'bionda': 'blonde', 'bruna': 'brunette', 'rossa': 'redhead',
        'attraente': 'attractive', 'bellissima': 'beautiful',
        'elegante': 'elegant', 'giovane': 'young', 'matura': 'mature',
        'sportiva': 'athletic', 'intellettuale': 'intellectual',
        'creativa': 'creative', 'avventuriera': 'adventurous',
        'misteriosa': 'mysterious', 'solenne': 'cheerful',
        'timida': 'shy', 'audace': 'bold', 'sensuale': 'sensual',
        'affascinante': 'charming', 'dolce': 'sweet', 'selvaggia': 'wild',
        'malinconica': 'melancholic', 'vivace': 'lively',
        
        # Professioni
        'pittrice': 'painter', 'attrice': 'actress', 'cantante': 'singer',
        'scrittrice': 'writer', 'ballerina': 'dancer', 'modella': 'model',
        'dottoressa': 'doctor', 'avvocatessa': 'lawyer',
        'pittore': 'painter', 'attore': 'actor', 'cantante': 'singer',
        'scrittore': 'writer', 'ballerino': 'dancer', 'modello': 'model',
        'dottore': 'doctor', 'avvocato': 'lawyer',
        'insegnante': 'teacher', 'professore': 'professor',
        'ingegnere': 'engineer', 'architetto': 'architect',
        'cuoco': 'chef', 'sacerdote': 'priest', 'monaco': 'monk',
        'poliziotto': 'police officer', 'pompiere': 'firefighter',
        'commerciante': 'merchant', 'esploratore': 'explorer',
        'investigatore': 'detective', 'criminale': 'criminal',
        'hacker': 'hacker', 'agente': 'agent',
        
        # Personalità
        'socievole': 'sociable', 'introversa': 'introverted',
        'estroversa': 'extroverted', 'romantica': 'romantic',
        'pratica': 'practical', 'sognatrice': 'dreamy',
        'determinata': 'determined', 'gentile': 'kind',
        'leale': 'loyal', 'passionale': 'passionate',
        
        # Descrizioni comuni
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
    # Traduzione case-insensitive: prova prima lowercase, poi uppercase
    for it, en in sorted(translations.items(), key=lambda x: -len(x[0])):
        # lowercase
        result = result.replace(it, en)
        # uppercase (prima lettera)
        result = result.replace(it.capitalize(), en.capitalize())
        # UPPERCASE
        result = result.replace(it.upper(), en.upper())
    
    return result


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


def generate_image(token, model_id, prompt, retries=3):
    import requests
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": "cartoon, anime, illustration, low quality, blurry, distorted face, bad anatomy, extra fingers",
            "guidance_scale": 7.5,
            "num_inference_steps": 28,
        },
    }
    for attempt in range(retries):
        print(f"  [tentativo {attempt + 1}/{retries}] Generazione...")
        resp = requests.post(API_URL + model_id, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.content
        if resp.status_code == 503:
            wait = int(resp.headers.get("x-wait-time", 20))
            print(f"  Modello in caricamento, attesa {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            print("  Rate limit, attesa 30s...")
            time.sleep(30)
            continue
        print(f"  Errore {resp.status_code}: {resp.text[:200]}")
        break
    return None


def save_avatar(char_id, category, image_data):
    from PIL import Image
    img = Image.open(io.BytesIO(image_data))
    min_dim = min(img.size)
    left = (img.width - min_dim) // 2
    top = (img.height - min_dim) // 2
    square = img.crop((left, top, left + min_dim, top + min_dim))

    category_dir = os.path.join(STATIC_AVATARS, category)
    os.makedirs(category_dir, exist_ok=True)
    square.resize((512, 512), Image.LANCZOS).save(
        os.path.join(category_dir, f"{char_id}.png"), "PNG"
    )
    print(f"  Server: static/avatars/{category}/{char_id}.png")


def update_characters_py(char_id):
    with open(CHARACTERS_FILE) as f:
        content = f.read()
    marker = f'"id": "{char_id}"'
    idx = content.find(marker)
    if idx == -1:
        print(f"  WARNING: '{char_id}' non trovato in characters.py")
        return False
    if '"avatar_image"' in content[idx:idx + 500]:
        print(f"  avatar_image già presente per '{char_id}'")
        return True
    snippet = content[idx:]
    avatar_pos = snippet.find('"avatar"')
    if avatar_pos == -1:
        print(f"  WARNING: campo 'avatar' non trovato per '{char_id}'")
        return False
    rest = snippet[avatar_pos:]
    line_end = rest.find("\n")
    full_line = rest[:line_end]  # linea completa con virgola
    indent = " " * (len(full_line) - len(full_line.lstrip()))
    new_line = full_line.rstrip(",") + ",\n" + indent + '"avatar_image": "' + char_id + '",'
    old = full_line + "\n"
    new = new_line + "\n"
    if old in content:
        content = content.replace(old, new, 1)
        with open(CHARACTERS_FILE, "w") as f:
            f.write(content)
        print(f"  characters.py aggiornato per '{char_id}'")
        return True
    else:
        print(f"  WARNING: impossibile aggiornare '{char_id}' (formato linea non trovato)")
        return False


def cmd_generate(args):
    token = args.token or os.environ.get("HF_TOKEN", "")
    if not token and os.path.isfile(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()
    
    # Token HF non serve per modelli gratuiti
    model_id = MODELS.get(args.model, MODELS["pollinations"])
    is_free_model = model_id == "free" or args.model in ["pollinations", "tpde", "pravatar", "dicebear"]
    
    if not token and not is_free_model:
        print("ERRORE: serve --token o HF_TOKEN o .hf_token per modelli HF")
        sys.exit(1)
    
    # Pollinations API key opzionale (per limiti migliori)
    pollinations_key = os.environ.get("POLLINATIONS_API_KEY", "")

    groq_token = args.groq_token or os.environ.get("GROQ_API_KEY", "")
    if not groq_token:
        groq_path = os.path.join(ROOT, "backend", ".env")
        if os.path.isfile(groq_path):
            with open(groq_path) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        groq_token = line.split("=", 1)[1].strip()
                        break

    chars = parse_characters()

    def avatar_path(char):
        return os.path.join(STATIC_AVATARS, char.get("category", ""), f"{char['id']}.png")

    if args.list_missing:
        missing = [c for c in chars if not c.get("avatar_image") or not os.path.isfile(avatar_path(c))]
        print(f"\nPersonaggi SENZA immagine ({len(missing)}):")
        for c in missing:
            flag = " (no field)" if not c.get("avatar_image") else " (no file)"
            print(f"  {c['id']:25s} {c['name']:20s} [{c.get('category','')}]{flag}")
        return

    if args.generate_all:
        targets = [c for c in chars if not c.get("avatar_image") or not os.path.isfile(avatar_path(c))]
        if not targets:
            print("Tutti i personaggi hanno già immagine.")
            return
        # Applica limite
        limit = args.avatar_limit if hasattr(args, 'avatar_limit') and args.avatar_limit > 0 else args.limit
        if limit > 0 and len(targets) > limit:
            targets = targets[:limit]
            print(f"Genero avatar per {len(targets)} personaggi (limite: {limit})...")
        else:
            print(f"Genero avatar per {len(targets)} personaggi...")
    elif args.generate:
        matched = [c for c in chars if c["id"] == args.generate]
        if not matched:
            print(f"Personaggio '{args.generate}' non trovato.")
            sys.exit(1)
        targets = matched
    else:
        return

    bio_count = 0
    for char in targets:
        print(f"\n{'='*60}")
        print(f"Generazione: {char['name']} ({char['id']})")
        print(f"{'='*60}")

        # Usa API gratuita se il modello è tra quelli free
        if model_id in ["free", "pexels", "pollinations", "tpde", "pravatar", "dicebear"]:
            prompt = get_prompt(char, args.prompt)
            print(f"  Uso API gratuita: {model_id}")
            print(f"  Prompt: {prompt[:120]}...")
            image_data = generate_image_free(model_id, char['id'], char['name'], prompt, pollinations_key, char=char)
        else:
            prompt = get_prompt(char, args.prompt)
            print(f"  Prompt: {prompt[:120]}...")
            image_data = generate_image(token, model_id, prompt)

        if not image_data:
            print(f"  FALLITO: {char['id']}")
            # Delay anche in caso di fallimento per evitare rate limit
            if model_id in ["pollinations"]:
                time.sleep(5)
            continue
        print(f"  Immagine: {len(image_data)} bytes")
        try:
            save_avatar(char["id"], char.get("category", ""), image_data)
            update_characters_py(char["id"])
            print(f"  ✅ Avatar salvato!")
        except Exception as e:
            print(f"  ERRORE salvataggio avatar: {e}")

        # Delay tra le richieste per evitare rate limit
        if model_id in ["pollinations"]:
            print(f"  ⏳ Attesa 5 sec (rate limit Pollinations)...")
            time.sleep(5)
        elif model_id in ["pexels"]:
            # Pexels: 200 req/ora = ~18 sec tra richieste, ma ne usiamo meno
            print(f"  ⏳ Attesa 3 sec (rate limit Pexels)...")
            time.sleep(3)

        if args.bio and groq_token:
            # Controlla limite biografie
            bio_limit = args.bio_limit if hasattr(args, 'bio_limit') and args.bio_limit > 0 else 0
            if bio_limit > 0 and bio_count >= bio_limit:
                print(f"  Limite biografie raggiunto ({bio_limit})")
                break
            print(f"  Genero biografia italiana...")
            bio = generate_italian_biography(char, groq_token)
            if bio:
                try:
                    update_characters_py_full(char["id"], bio)
                    bio_count += 1
                    print(f"  ✅ Biografia salvata! ({bio_count}/{bio_limit if bio_limit > 0 else 'infinito'})")
                except Exception as e:
                    print(f"  ERRORE salvataggio biografia: {e}")
            else:
                print(f"  ⚠️  Biografia non generata")
            # Delay tra le richieste Groq per evitare rate limit
            time.sleep(2)

    print("\nGenerazione completata!")


# ─── Animazione avatar ───────────────────────────────────────────

def find_avatars():
    avatars = []
    for root, dirs, files in os.walk(STATIC_AVATARS):
        for f in files:
            if f.endswith(".png") and not f.endswith("_anim.png"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, STATIC_AVATARS)
                category = os.path.dirname(rel)
                char_id = f[:-4]
                avatars.append({"path": full, "category": category, "id": char_id})
    return avatars


def animate_avatar(avatar_path, category, char_id):
    from gtts import gTTS
    from gradio_client import Client

    output_dir = os.path.join(STATIC_AVATARS, category)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{char_id}_anim.mp4")
    if os.path.isfile(output_path):
        return "already_exists"

    print(f"  Animo {char_id}...")

    audio_path = None
    try:
        name_for_tts = char_id.replace("_", " ")
        audio_path = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=f"Ciao, sono {name_for_tts}. Piacere di conoscerti!", lang="it")
        tts.save(audio_path)

        client = Client("John6666/SadTalker")
        result = client.predict(
            avatar_path, audio_path,
            "crop", True, True, 2, 256, 0, "facevid2vid", 1.0,
            False, None, "pose", False, 5, True,
            api_name="/test"
        )

        video_path = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")

        if video_path and os.path.isfile(video_path):
            shutil.copy2(video_path, output_path)
            print(f"  Salvato: {output_path}")
            return "ok"
        else:
            print(f"  Nessun video restituito per {char_id}")
            return "failed"

    except Exception as e:
        print(f"  ERRORE animazione {char_id}: {e}")
        return "failed"
    finally:
        try:
            if audio_path and os.path.isfile(audio_path):
                os.unlink(audio_path)
        except Exception:
            pass


def cmd_animate(args):
    avatars = find_avatars()
    if not avatars:
        print("Nessun avatar trovato in", STATIC_AVATARS)
        sys.exit(1)

    if args.list_avatars:
        print(f"\nAvatar trovati ({len(avatars)}):")
        for a in avatars:
            anim_path = os.path.join(STATIC_AVATARS, a["category"], f"{a['id']}_anim.mp4")
            status = "✅" if os.path.isfile(anim_path) else "  "
            print(f"  {status} {a['id']:25s} [{a['category']}]")
        return

    if args.animate_all:
        targets = avatars
    elif args.animate:
        matched = [a for a in avatars if a["id"] == args.animate]
        if not matched:
            print(f"Avatar '{args.animate}' non trovato.")
            sys.exit(1)
        targets = matched
    else:
        return

    ok = 0
    failed = 0
    skipped = 0
    for a in targets:
        result = animate_avatar(a["path"], a["category"], a["id"])
        if result == "ok":
            ok += 1
        elif result == "already_exists":
            skipped += 1
        else:
            failed += 1

    print(f"\nRiepilogo: {ok} animati, {skipped} già presenti, {failed} falliti")


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ChatAI Avatar Tool — genera e anima avatar")
    parser.add_argument("--token", help="Hugging Face token (default: env HF_TOKEN o .hf_token)")
    parser.add_argument("--groq-token", help="Groq API token per biografie (default: env GROQ_API_KEY o .env)")
    parser.add_argument("--model", default="pollinations", choices=list(MODELS.keys()),
                        help="Modello generazione (default: pollinations - full-body, gratis)")
    parser.add_argument("--prompt", help="Prompt personalizzato (solo con --generate)")
    parser.add_argument("--bio", action="store_true",
                        help="Genera biografia italiana automatica con Groq (backstory, personality, opening_scenario)")

    gen = parser.add_argument_group("Generazione immagini")
    gen.add_argument("--generate", metavar="ID", help="Genera avatar per un personaggio")
    gen.add_argument("--generate-all", action="store_true", help="Genera avatar per tutti i personaggi mancanti")
    gen.add_argument("--list-missing", action="store_true", help="Elenca personaggi senza avatar")
    gen.add_argument("--limit", type=int, default=0, help="Numero massimo di avatar da generare (0=tutti)")
    gen.add_argument("--avatar-limit", type=int, default=0, help="Limite avatar per modalita both")
    gen.add_argument("--bio-limit", type=int, default=0, help="Limite biografie per modalita both")

    anim = parser.add_argument_group("Animazione avatar")
    anim.add_argument("--animate", metavar="ID", help="Anima un avatar esistente")
    anim.add_argument("--animate-all", action="store_true", help="Anima tutti gli avatar")
    anim.add_argument("--list-avatars", action="store_true", help="Elenca avatar con stato animazione")

    icons = parser.add_argument_group("Icone categorie")
    icons.add_argument("--generate-category-icons", action="store_true",
                       help="Genera icone PNG per tutte le categorie")
    icons.add_argument("--generate-category-icon", metavar="CATEGORY",
                       help="Genera icona PNG per una singola categoria")

    args = parser.parse_args()

    has_gen = args.generate or args.generate_all or args.list_missing
    has_anim = args.animate or args.animate_all or args.list_avatars
    has_icons = args.generate_category_icons or args.generate_category_icon

    if not has_gen and not has_anim and not has_icons:
        parser.print_help()
        sys.exit(1)

    if has_gen:
        cmd_generate(args)

    if has_anim:
        cmd_animate(args)

    if has_icons:
        cmd_generate_category_icons(args)


# ─── Icone categorie ─────────────────────────────────────────────

CATEGORY_ICON_PROMPTS = {
    "romantici": "Minimalist flat icon of two hearts intertwined, romantic style, soft pink and red colors, clean design, white background, vector art style",
    "amicizia": "Minimalist flat icon of two hands shaking, friendship symbol, warm orange and yellow colors, clean design, white background, vector art style",
    "fantasy": "Minimalist flat icon of a magic wand with stars, fantasy theme, purple and gold colors, clean design, white background, vector art style",
    "horror": "Minimalist flat icon of a haunted house silhouette, horror theme, dark purple and black colors, clean design, white background, vector art style",
    "anime": "Minimalist flat icon of a game controller, anime gaming theme, bright colors, clean design, white background, vector art style",
    "scuola": "Minimalist flat icon of a graduation cap, education theme, blue and gold colors, clean design, white background, vector art style",
    "gamer": "Minimalist flat icon of a joystick, gaming theme, neon green and black colors, clean design, white background, vector art style",
    "detective": "Minimalist flat icon of a magnifying glass, detective mystery theme, brown and gold colors, clean design, white background, vector art style",
    "medicina": "Minimalist flat icon of a medical cross, healthcare theme, green and white colors, clean design, white background, vector art style",
    "business": "Minimalist flat icon of a briefcase, business professional theme, dark blue and silver colors, clean design, white background, vector art style",
    "viaggi": "Minimalist flat icon of an airplane, travel theme, sky blue and white colors, clean design, white background, vector art style",
    "motivazione": "Minimalist flat icon of a rising sun with arrow, motivation theme, orange and yellow colors, clean design, white background, vector art style",
    "cucina": "Minimalist flat icon of a chef hat and fork, cooking theme, red and white colors, clean design, white background, vector art style",
    "tecnologia": "Minimalist flat icon of a circuit board chip, technology theme, blue and green colors, clean design, white background, vector art style",
    "tecnici": "Minimalist flat icon of a wrench and screwdriver, technical theme, grey and orange colors, clean design, white background, vector art style",
    "storia": "Minimalist flat icon of an ancient column, history theme, brown and gold colors, clean design, white background, vector art style",
    "supereroi": "Minimalist flat icon of a shield with lightning bolt, superhero theme, red and gold colors, clean design, white background, vector art style",
    "sopravvivenza": "Minimalist flat icon of a tent and campfire, survival outdoor theme, green and orange colors, clean design, white background, vector art style",
    "sci-fi": "Minimalist flat icon of a rocket ship, science fiction theme, metallic silver and blue colors, clean design, white background, vector art style",
    "sport": "Minimalist flat icon of a soccer ball, sports theme, green and white colors, clean design, white background, vector art style",
    "flirt": "Minimalist flat icon of lips with a kiss mark, flirt theme, red and pink colors, clean design, white background, vector art style",
    "relazioni": "Minimalist flat icon of two interlocked rings, relationships theme, pink and gold colors, clean design, white background, vector art style",
    "confessioni": "Minimalist flat icon of a speech bubble with heart, confession theme, soft purple and pink colors, clean design, white background, vector art style",
    "seduzione": "Minimalist flat icon of a rose with thorns, seduction theme, deep red and black colors, clean design, white background, vector art style",
    "esperti": "Minimalist flat icon of a professional badge, experts theme, navy blue and gold colors, clean design, white background, vector art style",
    "creativi": "Minimalist flat icon of a paint palette and brush, creative arts theme, rainbow colors, clean design, white background, vector art style",
    "quotidiano": "Minimalist flat icon of a coffee cup, daily life theme, warm brown and white colors, clean design, white background, vector art style",
    "premium": "Minimalist flat icon of a diamond gem, premium luxury theme, gold and crystal colors, clean design, white background, vector art style",
    "intrattenimento": "Minimalist flat icon of a dice and cards, entertainment theme, bright colors, clean design, white background, vector art style",
    "speciale": "Minimalist flat icon of a star with sparkles, special theme, golden and silver colors, clean design, white background, vector art style",
    "per_te": "Minimalist flat icon of a person with a heart, for you personal theme, warm colors, clean design, white background, vector art style",
}

CATEGORY_ICONS_DIR = os.path.join(ROOT, "backend", "static", "category_icons")


def cmd_generate_category_icons(args):
    """Genera icone PNG per le categorie."""
    token = args.token or os.environ.get("HF_TOKEN", "")
    if not token and os.path.isfile(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()
    
    model_id = MODELS.get(args.model, MODELS["pollinations"])
    is_free_model = model_id == "free" or args.model in ["pollinations", "loremfaces", "testingbot", "avatars-tzador"]
    
    if not token and not is_free_model:
        print("ERRORE: serve --token o HF_TOKEN o .hf_token per modelli HF")
        sys.exit(1)

    if args.generate_category_icon:
        cat_id = args.generate_category_icon
        if cat_id not in CATEGORY_ICON_PROMPTS:
            print(f"Categoria '{cat_id}' non trovata. Opzioni: {', '.join(CATEGORY_ICON_PROMPTS.keys())}")
            sys.exit(1)
        targets = [cat_id]
    else:
        targets = list(CATEGORY_ICON_PROMPTS.keys())

    os.makedirs(CATEGORY_ICONS_DIR, exist_ok=True)

    print(f"Genero icone per {len(targets)} categorie...")
    for cat_id in targets:
        prompt = CATEGORY_ICON_PROMPTS[cat_id]
        print(f"\n  {cat_id}: {prompt[:60]}...")

        # Usa Pollinations.AI per icone (gratis, no token)
        image_data = generate_image_pollinations(prompt, f"cat_{cat_id}")
        if not image_data:
            print(f"  FALLITO: {cat_id}")
            continue

        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            min_dim = min(img.size)
            left = (img.width - min_dim) // 2
            top = (img.height - min_dim) // 2
            square = img.crop((left, top, left + min_dim, top + min_dim))

            square.resize((512, 512), Image.LANCZOS).save(
                os.path.join(CATEGORY_ICONS_DIR, f"{cat_id}.png"), "PNG"
            )
            print(f"  ✅ {cat_id}.png salvato")
        except Exception as e:
            print(f"  ERRORE: {e}")

    print("\nGenerazione icone categorie completata!")


if __name__ == "__main__":
    main()
