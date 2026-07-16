import json

from db import get_conn, put_conn


def add_message(user_id, character_id, role, content):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (user_id, character_id, role, content) VALUES (%s, %s, %s, %s)",
            (user_id, character_id, role, content)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_recent_messages(user_id, character_id, limit=30):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM messages WHERE user_id=%s AND character_id=%s ORDER BY timestamp DESC LIMIT %s",
            (user_id, character_id, limit)
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        put_conn(conn)


def count_messages(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM messages WHERE user_id=%s AND character_id=%s",
            (user_id, character_id)
        )
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)


def has_scenario_message(user_id, character_id):
    """True se esiste già almeno un messaggio di sistema (scenario) per
    questa coppia utente/character, indipendentemente da quanti messaggi
    sono stati scambiati. Evita che lo scenario venga reinserito a ogni
    rientro nella chat."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM messages WHERE user_id=%s AND character_id=%s AND role='system' LIMIT 1",
            (user_id, character_id)
        )
        return cur.fetchone() is not None
    finally:
        put_conn(conn)


def count_all_user_messages(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)


def add_time_event(event_type, character_id=None, user_id=None, data=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO time_events (event_type, character_id, user_id, data) VALUES (%s, %s, %s, %s)",
                     (event_type, character_id, user_id, json.dumps(data or {})))
        conn.commit()
    finally:
        put_conn(conn)


def get_time_events(event_type=None, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if event_type:
            cur.execute("SELECT * FROM time_events WHERE event_type=%s ORDER BY created_at DESC LIMIT %s",
                                (event_type, limit))
        else:
            cur.execute("SELECT * FROM time_events ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d.get("data", "{}"))
            result.append(d)
        return result
    finally:
        put_conn(conn)
