import json
from datetime import datetime, timezone
from db import get_conn, put_conn


def get_all_users():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role, email, google_id, banned_until, created_at, last_login FROM users ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def ban_user(user_id, duration_hours=0):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if duration_hours > 0:
            from datetime import timedelta
            ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
            cur.execute("UPDATE users SET banned_until = %s WHERE id = %s", (ban_until, user_id))
        else:
            cur.execute("UPDATE users SET banned_until = NULL WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def export_user_data(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        data = {}

        cur.execute("SELECT id, username, role, email, google_id, created_at, last_login FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        data["profile"] = dict(user) if user else None

        cur.execute("SELECT character_id, trust, affinity, respect, conflict, intimacy, pressure_level FROM relationships WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["relationships"] = [dict(r) for r in rows]

        cur.execute("SELECT character_id, role, content, timestamp FROM messages WHERE user_id=%s ORDER BY timestamp", (user_id,))
        rows = cur.fetchall()
        data["messages"] = [dict(r) for r in rows]

        cur.execute("SELECT character_id, summary, topics, message_count, created_at FROM conversation_memory WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["memories"] = [dict(r) for r in rows]

        cur.execute("SELECT memory_data, updated_at FROM user_memory WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["user_memory"] = {"memory": json.loads(row["memory_data"]) if row else {}, "updated_at": row["updated_at"] if row else None}

        cur.execute("SELECT id, name, age, role, description, created_at FROM user_characters WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["characters"] = [dict(r) for r in rows]

        cur.execute("SELECT is_premium, sku, activated_at, expires_at FROM premium_users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["premium"] = dict(row) if row else None

        cur.execute("SELECT character_id, current_stage, total_messages, updated_at FROM character_evolution WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["evolution"] = [dict(r) for r in rows]

        cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["preferences"] = dict(row) if row else None

        cur.execute("SELECT balance, total_earned, updated_at FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["mevacoins"] = dict(row) if row else {"balance": 0, "total_earned": 0, "updated_at": None}

        cur.execute("SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=%s ORDER BY created_at", (user_id,))
        rows = cur.fetchall()
        data["mevacoins_transactions"] = [dict(r) for r in rows]

        cur.execute("SELECT checkin_date, redeemed FROM daily_checkins WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["daily_checkins"] = [dict(r) for r in rows]

        cur.execute("SELECT day_number, claimed FROM new_user_bonus WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["new_user_bonus"] = [dict(r) for r in rows]

        data["exported_at"] = datetime.now(timezone.utc).isoformat()
        return data
    finally:
        put_conn(conn)


def delete_user(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM relationships WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM conversation_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM personality_shifts WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_characters WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM premium_users WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM character_evolution WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_preferences WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM mevacoins WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM mevacoins_transactions WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM daily_checkins WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM new_user_bonus WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        cur.execute("DELETE FROM audit_log WHERE user_id=%s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def get_admin_stats():
    conn = get_conn()
    try:
        cur = conn.cursor()
        stats = {}
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        stats["total_users"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE last_login >= NOW() - INTERVAL '7 days'")
        stats["active_7d"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE last_login >= NOW() - INTERVAL '30 days'")
        stats["active_30d"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE created_at >= NOW() - INTERVAL '1 day'")
        stats["registrations_today"] = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE created_at >= NOW() - INTERVAL '7 days'")
        stats["registrations_7d"] = cur.fetchone()["cnt"]
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM messages")
            stats["total_messages"] = cur.fetchone()["cnt"]
        except Exception:
            stats["total_messages"] = 0
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM user_characters")
            stats["total_user_characters"] = cur.fetchone()["cnt"]
        except Exception:
            stats["total_user_characters"] = 0
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_flags WHERE resolved_at IS NULL")
            stats["pending_flags"] = cur.fetchone()["cnt"]
        except Exception:
            stats["pending_flags"] = 0
        return stats
    finally:
        put_conn(conn)


def search_users(query, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        escaped = query.replace('%', '\\%').replace('_', '\\_')
        like_q = f"%{escaped}%"
        cur.execute(
            "SELECT id, username, role, email, google_id, banned_until, created_at, last_login "
            "FROM users WHERE username ILIKE %s OR email ILIKE %s ORDER BY created_at DESC LIMIT %s",
            (like_q, like_q, min(limit, 200))
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_user_detail(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role, email, google_id, banned_until, created_at, last_login "
            "FROM users WHERE id=%s",
            (user_id,)
        )
        user = cur.fetchone()
        if not user:
            return None
        result = dict(user)
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE user_id=%s", (user_id,))
            result["message_count"] = cur.fetchone()["cnt"]
        except Exception:
            result["message_count"] = 0
        try:
            cur.execute("SELECT COUNT(DISTINCT character_id) AS cnt FROM messages WHERE user_id=%s", (user_id,))
            result["conversation_count"] = cur.fetchone()["cnt"]
        except Exception:
            result["conversation_count"] = 0
        try:
            cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
            mc = cur.fetchone()
            result["mevacoins"] = mc["balance"] if mc else 0
        except Exception:
            result["mevacoins"] = 0
        return result
    finally:
        put_conn(conn)


def list_user_conversations(user_id, limit=100):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT character_id, COUNT(*) as msg_count, MIN(timestamp) as first_msg, "
            "MAX(timestamp) as last_msg FROM messages WHERE user_id=%s "
            "GROUP BY character_id ORDER BY last_msg DESC LIMIT %s",
            (user_id, limit)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        put_conn(conn)


def get_user_conversation_messages(user_id, character_id, limit=500):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content, timestamp FROM messages "
            "WHERE user_id=%s AND character_id=%s ORDER BY timestamp ASC LIMIT %s",
            (user_id, character_id, limit)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        put_conn(conn)
