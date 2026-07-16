import json
from db import get_conn, put_conn

TOPIC_KEYWORDS = {
    "musica": ["musica", "canzone", "chitarra", "pianoforte", "batteria", "cantare", "suonare", "nota", "melodia", "concerto"],
    "cucina": ["cucina", "ricetta", "cibo", "dolce", "pasta", "cuocere", "ingrediente", "piatto", "ristorante"],
    "tecnologia": ["computer", "programmazione", "tecnologia", "codice", "software", "hardware", "internet", "app", "smartphone"],
    "storia": ["storia", "passato", "antico", "guerra", "re", "impero", "medievale", "romano", "civiltà"],
    "scienza": ["scienza", "fisica", "chimica", "biologia", "matematica", "formula", "esperimento", "universo"],
    "arte": ["arte", "dipinto", "scultura", "museo", "colore", "pennello", "artistico", "mostra"],
    "sport": ["sport", "palestra", "allenamento", "correre", "nuoto", "calcio", "basket", "fitness"],
    "moda": ["moda", "vestito", "stile", "abbigliamento", "trend", "elegante", "outfit"],
    "viaggi": ["viaggio", "turismo", "meta", "vacanza", "esplorare", "paese", "città", "aeroporto"],
    "filosofia": ["filosofia", "pensiero", "esistenza", "senso", "verità", "morale", "etica"],
    "medicina": ["medicina", "salute", "dottore", "farmaco", "malattia", "corpo", "diagnosi"],
    "natura": ["natura", "pianta", "animale", "foresta", "montagna", "mare", "ecologia"],
    "lavoro": ["lavoro", "ufficio", "collega", "reunione", "progetto", "carriera", "impiego"],
    "relazioni": ["amore", "fidanzato", "relazione", "coppia", "sentimento", "gelosia", "fiducia"],
    "famiglia": ["famiglia", "genitore", "fratello", "sorella", "mamma", "papà", "nonno", "figlio"],
}


def share_memory_across_characters(user_id, fact_key, fact_value, source_character, source_name=""):
    """Share a memory fact across all characters for a user."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shared_memory (user_id, fact_key, fact_value, source_characters, importance, last_mentioned)
            VALUES (%s, %s, %s, %s, 0.7, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, fact_key) DO UPDATE SET
            fact_value=EXCLUDED.fact_value,
            source_characters=(
                SELECT jsonb_agg(DISTINCT elem)
                FROM jsonb_array_elements_text(shared_memory.source_characters || EXCLUDED.source_characters) AS elem
            ),
            importance=GREATEST(shared_memory.importance, 0.7),
            last_mentioned=CURRENT_TIMESTAMP
        """, (user_id, fact_key, fact_value, json.dumps([source_character])))
        conn.commit()
    finally:
        put_conn(conn)


def get_shared_memories(user_id, limit=20):
    """Get all shared memories for a user (cross-character)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT fact_key, fact_value, source_characters, importance, mentions, last_mentioned
            FROM shared_memory WHERE user_id=%s
            ORDER BY importance DESC, last_mentioned DESC LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def detect_message_topics(text):
    """Detect topics in a user message using keyword matching."""
    text_lower = text.lower()
    detected = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score >= 1:
            detected.append({"topic": topic, "relevance": min(1.0, score / 3)})
    return detected


def update_conversation_topics(user_id, character_id, text):
    """Update topic tracking for a conversation."""
    topics = detect_message_topics(text)
    if not topics:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        for t in topics:
            cur.execute("""
                INSERT INTO conversation_topics (user_id, character_id, topic, message_count, last_seen)
                VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, character_id, topic) DO UPDATE SET
                message_count=conversation_topics.message_count + 1,
                last_seen=CURRENT_TIMESTAMP
            """, (user_id, character_id, t["topic"]))
        conn.commit()
    finally:
        put_conn(conn)


def get_recent_topics(user_id, character_id, days=7, limit=10):
    """Get recent topics discussed in a conversation."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT topic, message_count, last_seen
            FROM conversation_topics
            WHERE user_id=%s AND character_id=%s
            AND last_seen > CURRENT_TIMESTAMP - INTERVAL '%s days'
            ORDER BY message_count DESC, last_seen DESC LIMIT %s
        """, (user_id, character_id, days, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_character_recent_topics(character_id, days=7, limit=20):
    """Get most discussed topics for a character across all users."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT topic, SUM(message_count) as total_count
            FROM conversation_topics
            WHERE character_id=%s
            AND last_seen > CURRENT_TIMESTAMP - INTERVAL '%s days'
            GROUP BY topic ORDER BY total_count DESC LIMIT %s
        """, (character_id, days, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)
