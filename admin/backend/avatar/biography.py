"""Biography and description generation using LLM providers."""

from avatar.env import llm_provider_rotator


def generate_italian_biography(char, groq_token=None):
    """Genera biografia completa in italiano usando provider LLM multipli con fallback."""
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
OPENING_SCENARIO: [ambientazione iniziale per il roleplay, 2-3 frasi descrittive]

Importante:
- Tutto in ITALIANO
- Scrivi come se il personaggio fosse REALE
- L'OPENING_SCENARIO deve essere un'ambientazione vivida e coinvolgente
- NON iniziare l'OPENING_SCENARIO con etichette come 'CONTESTO INIZIALE:' o 'Introduzione:'
- NON usare espressioni come 'l'utente entra come...': usa la seconda persona diretta ('tu entri...', 'sei...', 'ti trovi...')
- I valori devono essere coerenti con l'età e il ruolo
- Esempio valido: 'È notte fonda. Luna è seduta da sola al bancone di un bar quasi vuoto, la chitarra acustica sulle ginocchia. tu entri nel locale e incroci il suo sguardo.'"""

    if llm_provider_rotator.providers:
        result = llm_provider_rotator.call(prompt, max_tokens=800, temperature=0.8)
        if result and result.get("text"):
            print(f"  📡 Provider utilizzato: {result.get('provider', 'sconosciuto')}")
            return parse_biography_response(result["text"])
        else:
            print(f"  ❌ Tutti i provider LLM falliti")
            return None

    elif groq_token:
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
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"  Errore Groq {resp.status_code}: {resp.text[:200]}")
                return None

            content = resp.json()["choices"][0]["message"]["content"]
            return parse_biography_response(content)
        except Exception as e:
            print(f"  Errore generazione biografia: {e}")
            return None

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


def generate_italian_description_only(char, groq_token=None):
    """Genera solo la descrizione in italiano usando provider LLM multipli con fallback."""
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

    if llm_provider_rotator.providers:
        result = llm_provider_rotator.call(prompt, max_tokens=150, temperature=0.7)
        if result and result.get("text"):
            print(f"  📡 Provider utilizzato: {result.get('provider', 'sconosciuto')}")
            content = result["text"]
            for line in content.strip().split("\n"):
                if line.upper().startswith("DESCRIPTION:"):
                    return line[len("DESCRIPTION:"):].strip()
            return content.strip()
        else:
            print(f"  ❌ Tutti i provider LLM falliti")
            return None

    elif groq_token:
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
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"  Errore Groq {resp.status_code}: {resp.text[:200]}")
                return None

            content = resp.json()["choices"][0]["message"]["content"]
            for line in content.strip().split("\n"):
                if line.upper().startswith("DESCRIPTION:"):
                    return line[len("DESCRIPTION:"):].strip()
            return content.strip()
        except Exception as e:
            print(f"  Errore generazione descrizione: {e}")
            return None

    return None
