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
        # Atomic claim: only the caller that flips claimed 0->1 wins the payout.
        cur.execute(
            "UPDATE new_user_bonus SET claimed=1 WHERE user_id=%s AND day_number=%s AND claimed=0",
            (user_id, day_number)
        )
        if cur.rowcount == 0:
            return False
        add_mevacoins(user_id, 30, f"bonus_nuovo_utente_giorno_{day_number}", conn=conn, cur=cur)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        put_conn(conn)


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
        # Atomic gate: only the first unlock of this content wins. If it was
        # already unlocked (or a concurrent caller won), we don't charge.
        cur.execute(
            "INSERT INTO content_unlocks (user_id, content_type, content_id, spent_amount) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (user_id, content_type, content_id, amount)
        )
        if cur.rowcount == 0:
            conn.commit()
            return True, "ok"
        # Deduct only now; if the user can't pay, roll back the unlock too.
        cur.execute(
            "UPDATE mevacoins SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND balance >= %s",
            (amount, user_id, amount)
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False, "saldo_insufficiente"
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, -amount, f"unlock:{content_type}:{content_id}")
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        logger.error(f"Unlock content failed: {e}")
        conn.rollback()
        return False, "Sblocco non riuscito"
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
