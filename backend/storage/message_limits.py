"""Daily per-user free-message limit.

Normal users get a fixed number of AI chat messages per day (env
``DAILY_FREE_MESSAGE_LIMIT``, default 50). Admins (and moderators) are
unlimited. Any user can permanently lift the limit by spending MevaCoins
(env ``DAILY_UNLOCK_MVC_COST``, default 100) via ``unlock_unlimited_messages``.

The counter is keyed by UTC calendar day (``YYYY-MM-DD``) so it resets daily.
"""

import os
import logging
from datetime import date

from db import get_conn, put_conn
from storage.mevacoins import spend_mevacoins

logger = logging.getLogger(__name__)

DAILY_FREE_MESSAGE_LIMIT = int(os.environ.get("DAILY_FREE_MESSAGE_LIMIT", "50"))
DAILY_UNLOCK_MVC_COST = int(os.environ.get("DAILY_UNLOCK_MVC_COST", "100"))

# Roles that bypass the daily limit entirely.
UNLIMITED_ROLES = ("admin", "moderator")


def get_user_role(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        return row["role"] if row else "user"
    finally:
        put_conn(conn)


def _is_unlimited(user_id, role):
    if role in UNLIMITED_ROLES:
        return True
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT unlocked FROM user_message_unlock WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return bool(row and row["unlocked"])
    except Exception as e:
        logger.warning(f"_is_unlimited check failed for {user_id}: {e}")
        return False
    finally:
        put_conn(conn)


def get_daily_message_status(user_id):
    """Return a dict describing the user's daily message quota usage."""
    role = get_user_role(user_id)
    today = date.today().isoformat()
    used = 0
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count FROM user_daily_messages WHERE user_id=%s AND day=%s",
            (user_id, today)
        )
        row = cur.fetchone()
        if row:
            used = row["count"]
    finally:
        put_conn(conn)

    unlimited = _is_unlimited(user_id, role)
    if unlimited:
        return {
            "role": role,
            "unlimited": True,
            "limit": 0,
            "used": used,
            "remaining": None,
            "unlock_cost": DAILY_UNLOCK_MVC_COST,
        }
    remaining = max(0, DAILY_FREE_MESSAGE_LIMIT - used)
    return {
        "role": role,
        "unlimited": False,
        "limit": DAILY_FREE_MESSAGE_LIMIT,
        "used": used,
        "remaining": remaining,
        "unlock_cost": DAILY_UNLOCK_MVC_COST,
    }


def check_and_count_message(user_id):
    """Atomically check the daily limit and, if allowed, increment the counter.

    Returns ``(allowed: bool, status: dict)``. Admins/unlocked users are always
    allowed and are NOT counted.
    """
    role = get_user_role(user_id)
    if _is_unlimited(user_id, role):
        return True, get_daily_message_status(user_id)

    today = date.today().isoformat()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_daily_messages (user_id, day, count)
               VALUES (%s, %s, 1)
               ON CONFLICT (user_id, day) DO UPDATE SET count = user_daily_messages.count + 1
               WHERE user_daily_messages.count < %s""",
            (user_id, today, DAILY_FREE_MESSAGE_LIMIT)
        )
        updated = cur.rowcount
        conn.commit()
    except Exception as e:
        logger.error(f"check_and_count_message FAILED user={user_id} error={e}")
        conn.rollback()
        # On DB error, fail open (allow the message) rather than break chat.
        return True, get_daily_message_status(user_id)
    finally:
        put_conn(conn)

    if updated == 0:
        # Conflict existed and the WHERE clause rejected the update -> limit hit.
        return False, get_daily_message_status(user_id)
    return True, get_daily_message_status(user_id)


def unlock_unlimited_messages(user_id, cost=None):
    """Spend ``cost`` MevaCoins to permanently lift the daily message limit.

    Returns ``(ok: bool, msg: str)``.
    """
    if cost is None:
        cost = DAILY_UNLOCK_MVC_COST
    if not spend_mevacoins(user_id, cost, "unlock:daily_messages_unlimited"):
        return False, "saldo_insufficiente"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_message_unlock (user_id, unlocked, unlocked_at)
               VALUES (%s, 1, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET unlocked=1, unlocked_at=CURRENT_TIMESTAMP""",
            (user_id,)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"unlock_unlimited_messages FAILED user={user_id} error={e}")
        conn.rollback()
        return False, "db_error"
    finally:
        put_conn(conn)
    return True, "unlocked"
