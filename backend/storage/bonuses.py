from db import get_conn, put_conn
from storage.mevacoins import add_mevacoins


def get_new_user_bonus(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT day_number, claimed FROM new_user_bonus WHERE user_id=%s ORDER BY day_number",
            (user_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []
    finally:
        put_conn(conn)


def claim_new_user_bonus(user_id, day_number):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT claimed FROM new_user_bonus WHERE user_id=%s AND day_number=%s",
            (user_id, day_number)
        )
        row = cur.fetchone()
        if not row or row["claimed"]:
            return False
        cur.execute(
            "UPDATE new_user_bonus SET claimed=1 WHERE user_id=%s AND day_number=%s",
            (user_id, day_number)
        )
        conn.commit()
    finally:
        put_conn(conn)
    add_mevacoins(user_id, 30, f"bonus_nuovo_utente_giorno_{day_number}")
    return True


def init_new_user_bonus(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM new_user_bonus WHERE user_id=%s", (user_id,)
        )
        existing = cur.fetchone()['count']
        if existing == 0:
            for day in range(1, 5):
                cur.execute(
                    "INSERT INTO new_user_bonus (user_id, day_number, claimed) VALUES (%s, %s, 0)",
                    (user_id, day)
                )
        conn.commit()
    finally:
        put_conn(conn)


def unlock_content(user_id, content_type, content_id, amount):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE mevacoins SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s AND balance >= %s", (amount, user_id, amount))
        if cur.rowcount == 0:
            return False, "saldo_insufficiente"
        cur.execute(
            "INSERT INTO content_unlocks (user_id, content_type, content_id, spent_amount) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (user_id, content_type, content_id, amount)
        )
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, -amount, f"unlock:{content_type}:{content_id}")
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        put_conn(conn)


def is_content_unlocked(user_id, content_type, content_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user_row = cur.fetchone()
        if user_row and user_row["role"] == "admin":
            return True
        cur.execute(
            "SELECT 1 FROM content_unlocks WHERE user_id=%s AND content_type=%s AND content_id=%s",
            (user_id, content_type, content_id)
        )
        row = cur.fetchone()
        return row is not None
    finally:
        put_conn(conn)


def get_user_unlocks(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT content_type, content_id, spent_amount FROM content_unlocks WHERE user_id=%s",
            (user_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)
