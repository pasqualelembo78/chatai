import psycopg2.errors
from db import get_conn, put_conn
from datetime import datetime, timezone
from storage.mevacoins import add_mevacoins


def get_or_create_referral_code(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT code FROM referral_codes WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if row:
            return row["code"]
        import random, string
        for _ in range(10):
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            try:
                cur.execute("INSERT INTO referral_codes (user_id, code) VALUES (%s, %s)", (user_id, code))
                conn.commit()
                return code
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                continue
        return None
    finally:
        put_conn(conn)


def get_referrer_by_code(code):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM referral_codes WHERE code=%s", (code,))
        row = cur.fetchone()
        return row["user_id"] if row else None
    finally:
        put_conn(conn)


def claim_referral_bonus(user_id, code):
    referrer_id = get_referrer_by_code(code)
    if not referrer_id or referrer_id == user_id:
        return False, "codice_non_valido"
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Gate on the unique (referred_id, bonus_type) row first. This makes the
        # signup bonus usable at most once per user even if two different codes
        # are submitted concurrently (the constraint rejects the second INSERT).
        try:
            cur.execute(
                "INSERT INTO referral_earnings (referrer_id, referred_id, bonus_type, amount) "
                "VALUES (%s, %s, 'signup', 100)",
                (referrer_id, user_id)
            )
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return False, "gia_utilizzato"
        add_mevacoins(referrer_id, 100, f"referral_signup:{user_id}", conn=conn, cur=cur)
        add_mevacoins(user_id, 50, "referral_bonus", conn=conn, cur=cur)
        conn.commit()
        return True, "ok"
    except Exception as e:
        logger.error(f"Claim referral bonus failed: {e}")
        conn.rollback()
        return False, "Bonus referral non riuscito"
    finally:
        put_conn(conn)


def credit_referral_first_message(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT referrer_id FROM referral_earnings WHERE referred_id=%s AND bonus_type='signup'",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return
        referrer_id = row["referrer_id"]
        cur.execute(
            "SELECT 1 FROM referral_earnings WHERE referrer_id=%s AND referred_id=%s AND bonus_type='first_message'",
            (referrer_id, user_id)
        )
        already = cur.fetchone()
        if already:
            return
        try:
            add_mevacoins(referrer_id, 100, f"referral_first_message:{user_id}", conn=conn, cur=cur)
            cur.execute(
                "INSERT INTO referral_earnings (referrer_id, referred_id, bonus_type, amount) VALUES (%s, %s, 'first_message', 100)",
                (referrer_id, user_id)
            )
            conn.commit()
        except Exception:
            conn.rollback()
    finally:
        put_conn(conn)


def get_daily_share_count(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS count FROM social_shares WHERE user_id=%s AND share_date=%s", (user_id, today)
        )
        row = cur.fetchone()
        return row["count"] if row else 0
    finally:
        put_conn(conn)


def add_social_share(user_id, platform=""):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS count FROM social_shares WHERE user_id=%s AND share_date=%s", (user_id, today)
        )
        row = cur.fetchone()
        if (row["count"] if row else 0) >= 3:
            return False, "limite_giornaliero"
        cur.execute(
            "INSERT INTO social_shares (user_id, share_date, platform) VALUES (%s, %s, %s)",
            (user_id, today, platform)
        )
        # Re-check the cap inside the same transaction so the payout stays
        # consistent with the recorded shares (no orphan payout / over-limit).
        cur.execute(
            "SELECT COUNT(*) AS count FROM social_shares WHERE user_id=%s AND share_date=%s", (user_id, today)
        )
        row = cur.fetchone()
        if (row["count"] if row else 0) > 3:
            conn.rollback()
            return False, "limite_giornaliero"
        add_mevacoins(user_id, 30, f"social_share:{today}", conn=conn, cur=cur)
        conn.commit()
        return True, "ok"
    except Exception as e:
        logger.error(f"Social share bonus failed: {e}")
        conn.rollback()
        return False, "Bonus condivisione non riuscito"
    finally:
        put_conn(conn)
