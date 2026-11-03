"""
Chat summary module - riassunto conversazione per non appesantire AI.
"""
import logging
from storage import init_db
import psycopg2

def _conn():
    from storage import init_db
    # Fallback direct DB via env
    import os
    dsn = os.environ.get("DATABASE_URL", "postgresql://chatai:chatai_secret@localhost:5432/chatai")
    return psycopg2.connect(dsn)

logger = logging.getLogger(__name__)

def get_summary(user_id, character_id):
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT summary_text FROM chat_summaries WHERE user_id=%s AND character_id=%s ORDER BY updated_at DESC LIMIT 1",
            (str(user_id), str(character_id))
        )
        row = cur.fetchone()
        cur.close(); conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.warning("summary read failed: %s", e)
        return None

def save_summary(user_id, character_id, summary_text, message_count=0):
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_summaries (user_id, character_id, summary_text, message_count, updated_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING",
            (str(user_id), str(character_id), str(summary_text), int(message_count))
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logger.warning("summary save failed: %s", e)

def should_summarize(memory_context, threshold=10):
    return isinstance(memory_context, list) and len(memory_context) >= threshold

def build_summary_prompt(memory_context, character_name="personaggio"):
    text = "\n".join(str(m.get("text", m.get("content", str(m)))) for m in memory_context[-6:])
    return (
        f"Sei un assistente di riassunto. Riassumi questa parte di conversazione tra utente e {character_name} "
        f"in 2-3 frasi brevi (max 40 parole), mantenendo il filo narrativo e i punti chiave. "
        f"Non aggiungere presentazioni, non dire che sei AI, rispondi solo con il riassunto.\n\n"
        f"Conversazione:\n{text}\n\nRiassunto:"
    )
