import logging
from db import get_conn, put_conn

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def audit_log(user_id, action, detail="", ip="", user_agent=""):
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO audit_log (user_id, action, detail, ip, user_agent) VALUES (%s, %s, %s, %s, %s)",
                (user_id, action, detail[:500], ip[:50], user_agent[:200])
            )
            conn.commit()
        finally:
            put_conn(conn)
    except Exception as e:
        logger.warning(f"audit_log failed: {e}")


def prune_old_data(retention_days=DEFAULT_RETENTION_DAYS):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE timestamp < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_messages = cur.rowcount
        cur.execute(
            "DELETE FROM conversation_memory WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_memories = cur.rowcount
        cur.execute(
            "DELETE FROM personality_shifts WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_shifts = cur.rowcount
        cur.execute(
            "DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '365 days'"
        )
        deleted_audit = cur.rowcount
        conn.commit()
        return {
            "messages": deleted_messages,
            "memories": deleted_memories,
            "shifts": deleted_shifts,
            "audit_logs": deleted_audit,
        }
    finally:
        put_conn(conn)
