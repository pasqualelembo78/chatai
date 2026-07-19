"""Memorizzazione conversazioni: riassunti, rename personaggio, fact personali."""
import json
import re

from storage import (
    count_messages, get_last_summary_checkpoint, get_recent_messages,
    get_memories, get_relationship, get_user_memory, add_memory,
)
from ai_engine import get_ai_response

SUMMARY_INTERVAL = 30


def _maybe_summarize(user_id, character_id, character):
    total = count_messages(user_id, character_id)
    checkpoint = get_last_summary_checkpoint(user_id, character_id)
    if total - checkpoint < SUMMARY_INTERVAL:
        return
    old = get_recent_messages(user_id, character_id, limit=SUMMARY_INTERVAL)
    if len(old) < 3:
        return
    text = ""
    for m in old[-15:]:
        role = "Utente" if m["role"] == "user" else character["name"]
        text += f"{role}: {m['content']}\n"
    prev_summaries = get_memories(user_id, character_id, limit=3)
    prev_text = ""
    if prev_summaries:
        for s in prev_summaries:
            prev_text += f"- {s.get('summary', '')}\n"
    prompt = (
        f"Sei un assistente che riassume conversazioni tra un utente e {character['name']}.\n"
        f"Estrai informazioni personali sull'utente (nome, soprannome, hobby, lavoro, gusti, preferenze, ecc.) "
        f"e includile nel riassunto.\n\n"
    )
    if prev_text:
        prompt += f"Riassunti precedenti:\n{prev_text}\n\n"
    prompt += (
        f"Conversazione recente:\n{text}\n\n"
        "Scrivi un riassunto dettagliato in 3-4 frasi, includendo eventuali nuovi dettagli sull'utente."
    )
    summary, _, _ = get_ai_response([
        {"role": "system", "content": "Sei un assistente che riassume conversazioni in italiano."},
        {"role": "user", "content": prompt}
    ], user_id=user_id)
    if not summary:
        return
    rel = get_relationship(user_id, character_id)
    topics = []
    user_mem = get_user_memory(user_id).get("memory", {})
    if user_mem:
        topics = list(user_mem.keys())
    add_memory(user_id, character_id, summary, topics, total,
        {"trust": rel.get("trust", 0), "affinity": rel.get("affinity", 0), "intimacy": rel.get("intimacy", 0)})


_MEMORY_KEYWORDS = [
    "mi piace", "mi piacciono", "sono", "ho ", "voglio", "vorrei",
    "preferisco", "odio", "amo", "faccio", "lavoro", "studio",
    "vivo", "abit", "mi chiamo", "il mio", "la mia", "i miei",
    "le mie", "detesto", "adoro", "non mi piace",
    "mi piace tanto", "mi fa impazzire", "il mio preferito", "la mia passione", "mi diverto",
]

_RENAME_PATTERNS = [
    r"ti\s+chiamerai\s+(\w+)", r"ti\s+chiamo\s+(\w+)", r"ti\s+chiami\s+(\w+)",
    r"il\s+tuo\s+nome\s+(?:è|sarà|sara)\s+(\w+)", r"ti\s+chiamerò\s+(\w+)",
    r"il\s+nome\s+(?:è|sarà|sara)\s+(\w+)",
]


def _detect_character_rename(user_text):
    text_lower = user_text.lower()
    for pattern in _RENAME_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            name = m.group(1).strip().capitalize()
            if len(name) >= 2:
                return name
    return None


def _extract_teaching_topic(user_text):
    text_lower = user_text.lower()
    topic_keywords = {
        "musica": ["musica", "canzone", "chitarra", "pianoforte", "batteria", "cantare", "suonare", "nota", "melodia"],
        "cucina": ["cucina", "ricetta", "cibo", "dolce", "pasta", "cuocere", "ingrediente", "piatto"],
        "tecnologia": ["computer", "programmazione", "tecnologia", "codice", "software", "hardware", "internet", "app"],
        "storia": ["storia", "passato", "antico", "guerra", "re", "impero", "medievale", "romano"],
        "scienza": ["scienza", "fisica", "chimica", "biologia", "matematica", "formula", "esperimento"],
        "arte": ["arte", "dipinto", "scultura", "museo", "colore", "pennello", "artistico"],
        "sport": ["sport", "palestra", "allenamento", "correre", "nuoto", "calcio", "basket"],
        "moda": ["moda", "vestito", "stile", "abbigliamento", "trend", "elegante"],
        "viaggi": ["viaggio", "turismo", "meta", "vacanza", "esplorare", "paese", "città"],
        "filosofia": ["filosofia", "pensiero", "esistenza", "senso", "verità", "morale"],
        "medicina": ["medicina", "salute", "dottore", "farmaco", "malattia", "corpo"],
        "natura": ["natura", "pianta", "animale", "foresta", "montagna", "mare"],
        "lingue": ["lingua", "parlare", "inglese", "spagnolo", "francese", "tradurre"],
        "economia": ["economia", "denaro", "investimento", "business", "mercato"],
        "religione": ["religione", "fede", "preghiera", "spirito", "credere"],
    }
    best_topic, best_score = None, 0
    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_topic = topic
    if best_score >= 1:
        return best_topic
    words = text_lower.split()
    for w in words:
        if len(w) > 4 and w not in {"questo", "quello", "essere", "avere", "fare", "dire", "cosa", "come", "perché", "perche", "quando", "dove", "chi"}:
            return w
    return None


def _mentions_personal_info(text):
    """Gatekeeper: returns True only if the message likely contains personal info worth extracting."""
    text_lower = text.lower()
    # Direct personal statements
    direct = any(kw in text_lower for kw in _MEMORY_KEYWORDS)
    if direct:
        return True
    # Broader patterns: "io sono", "a me piace", "il mio lavoro", etc.
    broad_patterns = [
        "io sono", "a me ", "per me ", "il mio ", "la mia ", "i miei ", "le mie ",
        "mi chiamo", "ho bisogno", "vivo a", "abito a", "studio a", "lavoro a",
        "mi piace", "mi piaceva", "adoro ", "detesto ", "odio ",
        "sono di ", "vengo da", "parlo ", "conosco ",
    ]
    return any(p in text_lower for p in broad_patterns)


def _extract_user_facts(user_id, user_text, character_name):
    """Extract personal facts from user message via LLM. Called only when _mentions_personal_info() is True."""
    prompt = (
        f"L'utente ha detto a {character_name}: \"{user_text}\"\n\n"
        "Estrai eventuali informazioni personali sull'utente e restituiscile come JSON con chiavi in italiano. "
        "Ogni valore deve essere una stringa concisa. Se non ci sono informazioni personali, restituisci solo {}.\n"
        "Esempio: {\"hobby\": \"gioca a pallone\", \"lavoro\": \"insegnante\"}\n"
        "Restituisci SOLO il JSON, nient'altro."
    )
    msgs = [
        {"role": "system", "content": "Sei un assistente che estrae informazioni personali in formato JSON."},
        {"role": "user", "content": prompt},
    ]
    result, _, _ = get_ai_response(msgs, user_id=user_id)
    if not result:
        return {}
    json_match = re.search(r'\{.*\}', result, re.DOTALL)
    if not json_match:
        return {}
    try:
        return json.loads(json_match.group(0))
    except Exception:
        return {}


def _extract_memory_updates(user_id, user_text, character, character_id=None):
    """Phase 1: Only call LLM extraction if message likely contains personal info."""
    if not _mentions_personal_info(user_text):
        return {}
    return _extract_user_facts(user_id, user_text, character["name"])
