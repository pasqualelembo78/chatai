import json
from datetime import datetime
from db import get_conn, put_conn


def get_evolution(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT current_stage, unlocked_stages, flags, trait_modifiers,
                      intimacy_peak, total_messages
               FROM character_evolution
               WHERE user_id=%s AND character_id=%s""",
            (user_id, character_id)
        )
        row = cur.fetchone()
        if row:
            return {
                "current_stage": row["current_stage"],
                "unlocked_stages": json.loads(row["unlocked_stages"] or '["base"]'),
                "flags": json.loads(row["flags"] or '{}'),
                "trait_modifiers": json.loads(row["trait_modifiers"] or '{}'),
                "intimacy_peak": row["intimacy_peak"],
                "total_messages": row["total_messages"],
            }
        return {
            "current_stage": "base",
            "unlocked_stages": ["base"],
            "flags": {},
            "trait_modifiers": {},
            "intimacy_peak": 0,
            "total_messages": 0,
        }
    finally:
        put_conn(conn)


def update_evolution(user_id, character_id, evo):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO character_evolution
            (user_id, character_id, current_stage, unlocked_stages,
             flags, trait_modifiers, intimacy_peak, total_messages, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, character_id) DO UPDATE SET
            current_stage=EXCLUDED.current_stage, unlocked_stages=EXCLUDED.unlocked_stages,
            flags=EXCLUDED.flags, trait_modifiers=EXCLUDED.trait_modifiers,
            intimacy_peak=EXCLUDED.intimacy_peak, total_messages=EXCLUDED.total_messages,
            updated_at=EXCLUDED.updated_at
        """, (
            user_id, character_id,
            evo["current_stage"],
            json.dumps(evo["unlocked_stages"]),
            json.dumps(evo["flags"]),
            json.dumps(evo.get("trait_modifiers", {})),
            evo.get("intimacy_peak", 0),
            evo["total_messages"],
        ))
        conn.commit()
    finally:
        put_conn(conn)


def start_conversation_session(user_id, character_id):
    """Create or update a conversation session."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Check if there's a recent session (within 2 hours)
        cur.execute("""
            SELECT id FROM conversation_sessions
            WHERE user_id=%s AND character_id=%s
            AND last_message_at > CURRENT_TIMESTAMP - INTERVAL '2 hours'
            ORDER BY last_message_at DESC LIMIT 1
        """, (user_id, character_id))
        row = cur.fetchone()
        if row:
            # Update existing session
            cur.execute("""
                UPDATE conversation_sessions SET last_message_at=CURRENT_TIMESTAMP,
                message_count=message_count+1 WHERE id=%s
            """, (row["id"],))
            conn.commit()
            return row["id"]
        else:
            # Create new session
            cur.execute("""
                INSERT INTO conversation_sessions (user_id, character_id, message_count)
                VALUES (%s, %s, 1) RETURNING id
            """, (user_id, character_id))
            session_id = cur.fetchone()["id"]
            conn.commit()
            return session_id
    finally:
        put_conn(conn)


def get_last_conversation_time(user_id, character_id):
    """Get the timestamp of the last conversation with a character."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT last_message_at FROM conversation_sessions
            WHERE user_id=%s AND character_id=%s
            ORDER BY last_message_at DESC LIMIT 1
        """, (user_id, character_id))
        row = cur.fetchone()
        return row["last_message_at"] if row else None
    finally:
        put_conn(conn)


def get_temporal_context(user_id, character_id):
    """Build temporal context for the prompt."""
    last_time = get_last_conversation_time(user_id, character_id)
    context = {}
    if last_time:
        try:
            now = datetime.now()
            if isinstance(last_time, str):
                last_dt = datetime.fromisoformat(last_time)
            else:
                last_dt = last_time
            diff = now - last_dt
            hours = diff.total_seconds() / 3600
            if hours < 1:
                context["time_gap"] = "pochi minuti fa"
            elif hours < 24:
                context["time_gap"] = f"{int(hours)} ore fa"
            else:
                days = diff.days
                context["time_gap"] = f"{days} {'giorno' if days == 1 else 'giorni'} fa"
            context["last_conversation"] = last_dt.isoformat()
        except Exception:
            pass

    # Total sessions count
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as cnt, SUM(message_count) as total_msgs
            FROM conversation_sessions WHERE user_id=%s AND character_id=%s
        """, (user_id, character_id))
        row = cur.fetchone()
        if row:
            context["total_sessions"] = row["cnt"]
            context["total_messages"] = row["total_msgs"]
    finally:
        put_conn(conn)

    return context
