"""Granular user memory: edit, fix errors, delete all."""
import psycopg2, os

def _connect():
    return psycopg2.connect(os.environ.get("DATABASE_URL", "postgresql://chatai:chatai_secret@localhost:5432/chatai"))

def get_user_memory(user_id, character_id=None):
    try:
        conn = _connect()
        cur = conn.cursor()
        if character_id:
            cur.execute("SELECT memory_key, memory_value FROM user_memory_items WHERE user_id=%s AND character_id=%s ORDER BY updated_at DESC", (str(user_id), str(character_id)))
        else:
            cur.execute("SELECT memory_key, memory_value FROM user_memory_items WHERE user_id=%s ORDER BY updated_at DESC", (str(user_id),))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {k: v for k, v in rows}
    except Exception as e:
        return {}

def save_user_memory(user_id, character_id, key, value):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO user_memory_items (user_id, character_id, memory_key, memory_value, updated_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (user_id, character_id, memory_key) DO UPDATE SET memory_value=EXCLUDED.memory_value, updated_at=NOW()", (str(user_id), str(character_id), str(key), str(value)))
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception as e:
        return False

def delete_all_memory(user_id, character_id=None):
    try:
        conn = _connect()
        cur = conn.cursor()
        if character_id:
            cur.execute("DELETE FROM user_memory_items WHERE user_id=%s AND character_id=%s", (str(user_id), str(character_id)))
        else:
            cur.execute("DELETE FROM user_memory_items WHERE user_id=%s", (str(user_id),))
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception:
        return False
