from db import get_conn, put_conn


def send_admin_dm(from_user_id, to_user_id, content):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admin_dms (from_user_id, to_user_id, content) VALUES (%s, %s, %s) RETURNING id, created_at",
            (from_user_id, to_user_id, content)
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        put_conn(conn)


def list_admin_dms(user_id, limit=200, unread_only=False):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if unread_only:
            cur.execute(
                "SELECT id, from_user_id, to_user_id, content, read_at, created_at "
                "FROM admin_dms WHERE to_user_id=%s AND read_at IS NULL ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
        else:
            cur.execute(
                "SELECT id, from_user_id, to_user_id, content, read_at, created_at "
                "FROM admin_dms WHERE from_user_id=%s OR to_user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, user_id, limit)
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        put_conn(conn)


def mark_admin_dms_read(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE admin_dms SET read_at = CURRENT_TIMESTAMP "
            "WHERE to_user_id=%s AND read_at IS NULL",
            (user_id,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        put_conn(conn)
