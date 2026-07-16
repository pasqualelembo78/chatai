from db import get_conn, put_conn


def flag_user(user_id, reason, content_type="", content_snippet="", severity="medium", flagged_by="system"):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO moderation_flags (user_id, flagged_by, reason, content_type, content_snippet, severity) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, flagged_by, reason, content_type, content_snippet[:200], severity)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_moderation_flags(resolved=False, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if resolved:
            cur.execute(
                "SELECT * FROM moderation_flags ORDER BY created_at DESC LIMIT %s", (limit,)
            )
        else:
            cur.execute(
                "SELECT * FROM moderation_flags WHERE resolved_at IS NULL ORDER BY created_at DESC LIMIT %s", (limit,)
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def resolve_moderation_flag(flag_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE moderation_flags SET resolved_at = CURRENT_TIMESTAMP WHERE id = %s", (flag_id,)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_flag_count(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM moderation_flags WHERE user_id = %s AND resolved_at IS NULL",
            (user_id,)
        )
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)
