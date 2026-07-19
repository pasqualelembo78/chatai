from db import get_conn, put_conn


def get_mevacoins_balance(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["balance"] if row else 0
    finally:
        put_conn(conn)


def add_mevacoins(user_id, amount, reason, conn=None, cur=None):
    if amount <= 0:
        # Earns must be positive; negative adjustments must go through
        # spend_mevacoins. Rejecting here prevents silent balance underflow.
        raise ValueError(f"add_mevacoins amount must be > 0, got {amount}")
    owned_conn = conn is None
    if owned_conn:
        conn = get_conn()
    try:
        if cur is None:
            cur = conn.cursor()
        cur.execute(
            "INSERT INTO mevacoins (user_id, balance, total_earned, updated_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "balance = mevacoins.balance + EXCLUDED.balance, "
            "total_earned = mevacoins.total_earned + EXCLUDED.total_earned, "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id, amount, amount)
        )
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, amount, reason)
        )
        if owned_conn:
            cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            conn.commit()
            return row["balance"] if row else amount
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"add_mevacoins FAILED: user={user_id} amount={amount} reason={reason} error={e}")
        if owned_conn:
            conn.rollback()
        raise
    finally:
        if owned_conn:
            put_conn(conn)


def spend_mevacoins(user_id, amount, reason):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE mevacoins SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s AND balance >= %s", (amount, user_id, amount))
        if cur.rowcount == 0:
            return False
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, -amount, reason)
        )
        conn.commit()
        return True
    finally:
        put_conn(conn)


def get_mevacoins_transactions(user_id, limit=20):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def adjust_balance(user_id, delta, reason):
    """Adjust the balance by `delta` (positive or negative) and log a
    transaction. Does NOT change `total_earned` (used for refunds/rollbacks
    where coins are returned, not newly earned). Returns the new balance, or
    False if a negative delta would drive the balance below zero.
    """
    if delta == 0:
        return get_mevacoins_balance(user_id)
    conn = get_conn()
    try:
        cur = conn.cursor()
        if delta > 0:
            cur.execute(
                "UPDATE mevacoins SET balance = balance + %s, updated_at=CURRENT_TIMESTAMP "
                "WHERE user_id=%s",
                (delta, user_id),
            )
        else:
            cur.execute(
                "UPDATE mevacoins SET balance = balance + %s, updated_at=CURRENT_TIMESTAMP "
                "WHERE user_id=%s AND balance >= %s",
                (delta, user_id, -delta),
            )
            if cur.rowcount == 0:
                return False
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, delta, reason),
        )
        conn.commit()
        cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["balance"] if row else 0
    except Exception as e:
        conn.rollback()
        raise
    finally:
        put_conn(conn)
