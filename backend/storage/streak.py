import logging
from datetime import datetime, timezone
from db import get_conn, put_conn
from storage.mevacoins import add_mevacoins

logger = logging.getLogger(__name__)


def daily_checkin(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO daily_checkins (user_id, checkin_date) VALUES (%s, %s) "
            "ON CONFLICT (user_id, checkin_date) DO NOTHING",
            (user_id, today)
        )
        if cur.rowcount == 0:
            # Already checked in today (or concurrent insert won) -> no payout.
            conn.commit()
            return {"already_checked": True, "redeemed": False}
        conn.commit()
    except Exception:
        conn.rollback()
        return {"already_checked": True, "redeemed": False}
    finally:
        put_conn(conn)
    add_mevacoins(user_id, 15, "checkin_giornaliero")
    return {"already_checked": False, "earned": 15}


def redeem_daily_checkin(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM daily_checkins WHERE user_id=%s AND checkin_date=%s AND redeemed=0",
            (user_id, today)
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            "UPDATE daily_checkins SET redeemed=1 WHERE user_id=%s AND checkin_date=%s",
            (user_id, today)
        )
        conn.commit()
        return True
    finally:
        put_conn(conn)


def get_checkin_streak(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT checkin_date FROM daily_checkins WHERE user_id=%s ORDER BY checkin_date DESC",
            (user_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return 0
        streak = 0
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        for row in rows:
            d = datetime.strptime(row["checkin_date"], "%Y-%m-%d").date()
            if streak == 0:
                if d == today:
                    streak = 1
                elif d == today - timedelta(days=1):
                    streak = 1
                else:
                    return 0
            else:
                expected = today - timedelta(days=streak)
                if d == expected:
                    streak += 1
                else:
                    break
        return streak
    finally:
        put_conn(conn)


def claim_streak_milestone(user_id, milestone):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO streak_milestones (user_id, milestone) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, milestone)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        put_conn(conn)


def calculate_streak_reward(day):
    """Calculate MVC reward for a given day (1-30). Day 30 = super bonus."""
    if day >= 30:
        return 100
    return 10 + (day - 1) * 2


def _parse_claimed_date(ca):
    """Robustly extract a date from a claimed_at value (datetime, date, or string)."""
    from datetime import date as _date, datetime as _dt
    if ca is None:
        return None
    if isinstance(ca, _date) and not isinstance(ca, _dt):
        return ca
    if hasattr(ca, 'date'):
        return ca.date()
    s = str(ca).strip()
    if len(s) >= 10:
        try:
            return _dt.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    return None


def get_streak_30_status(user_id):
    """Get the user's 30-day streak status based on registration date."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        today = datetime.now(timezone.utc).date()

        cur.execute("SELECT created_at FROM users WHERE id=%s", (user_id,))
        user_row = cur.fetchone()
        reg_date = user_row["created_at"].date() if user_row and user_row["created_at"] else today

        days_since_reg = (today - reg_date).days + 1
        expected_day = min(days_since_reg, 30)

        cur.execute(
            "SELECT day_number, claimed, claimed_at FROM streak_30days WHERE user_id=%s ORDER BY day_number",
            (user_id,)
        )
        rows = cur.fetchall()
        claimed_days = {row["day_number"]: row["claimed"] for row in rows}
        claimed_dates = {row["day_number"]: _parse_claimed_date(row.get("claimed_at")) for row in rows}

        current_day = expected_day
        for check_day in range(1, expected_day):
            if check_day not in claimed_days or claimed_days[check_day] == 0:
                current_day = check_day
                break

        already_claimed_today = False
        cd = claimed_dates.get(current_day)
        if cd and cd == today and claimed_days.get(current_day) == 1:
            already_claimed_today = True

        days_list = []
        for d in range(1, 31):
            is_claimed = claimed_days.get(d, 0) == 1
            reward = calculate_streak_reward(d)
            if d < current_day:
                status = "claimed" if is_claimed else "missed"
            elif d == current_day:
                status = "claimed" if already_claimed_today else "available"
            else:
                status = "locked"
            days_list.append({"day": d, "status": status, "reward": reward})

        return {
            "current_day": current_day,
            "already_claimed_today": already_claimed_today,
            "reward": calculate_streak_reward(current_day),
            "total_earned": sum(calculate_streak_reward(d) for d in range(1, 31) if claimed_days.get(d, 0) == 1),
            "days": days_list,
        }
    except Exception as e:
        return {"current_day": 1, "already_claimed_today": False, "reward": 10, "total_earned": 0, "days": []}
    finally:
        put_conn(conn)


def claim_streak_30_day(user_id, day=None):
    """Claim the daily streak reward. Returns (success, earned, message)."""
    import logging
    log = logging.getLogger(__name__)
    conn = get_conn()
    try:
        cur = conn.cursor()

        today = datetime.now(timezone.utc).date()

        cur.execute("SELECT created_at FROM users WHERE id=%s", (user_id,))
        user_row = cur.fetchone()
        if user_row and user_row["created_at"]:
            reg_date = user_row["created_at"].date()
        else:
            log.warning(f"claim_streak_30: user={user_id} has no created_at, using today")
            reg_date = today

        days_since_reg = (today - reg_date).days + 1
        expected_day = min(days_since_reg, 30)

        cur.execute(
            "SELECT day_number, claimed, claimed_at FROM streak_30days WHERE user_id=%s ORDER BY day_number",
            (user_id,)
        )
        rows = cur.fetchall()
        claimed_days = {row["day_number"]: row["claimed"] for row in rows}
        claimed_dates = {row["day_number"]: _parse_claimed_date(row.get("claimed_at")) for row in rows}

        broken = False
        target_day = expected_day
        for check_day in range(1, expected_day):
            if claimed_days.get(check_day, 0) != 1:
                broken = True
                target_day = check_day
                break

        # NOTE: intentionally do NOT reset already-claimed days to 0.
        # `claimed` is a permanent record of what was paid; resetting it would
        # let users re-claim (and re-earn) previously paid days after a break.

        if day is None or day <= 0:
            day = target_day

        if day < 1 or day > 30:
            log.warning(f"claim_streak_30: user={user_id} invalid day={day}")
            return False, 0, "giorno_non_valido"

        earned = calculate_streak_reward(day)
        now = datetime.now(timezone.utc)

        # Atomic claim: only pay out when this call actually flips the day from
        # unclaimed (0) to claimed (1). Concurrent calls collide here and only
        # one wins the payout; a day already claimed (1) yields rowcount 0.
        cur.execute(
            "INSERT INTO streak_30days (user_id, day_number, claimed, claimed_at) "
            "VALUES (%s, %s, 1, %s) "
            "ON CONFLICT (user_id, day_number) DO UPDATE SET claimed=1, claimed_at=EXCLUDED.claimed_at "
            "WHERE streak_30days.claimed = 0",
            (user_id, day, now)
        )
        if cur.rowcount == 0:
            # Already claimed today (or previously) -> no payout.
            conn.commit()
            return False, 0, "gia_riscosso"

        reason = f"streak_giorno_{day}" + ("_super" if day == 30 else "")
        cur.execute(
            "INSERT INTO mevacoins (user_id, balance, total_earned, updated_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "balance = mevacoins.balance + EXCLUDED.balance, "
            "total_earned = mevacoins.total_earned + EXCLUDED.total_earned, "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id, earned, earned)
        )
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, earned, reason)
        )

        conn.commit()
        log.info(f"claim_streak_30: user={user_id} day={day} earned={earned} SUCCESS")

        return True, earned, "ok"
    except Exception as e:
        log.error(f"claim_streak_30: user={user_id} ERROR: {e}")
        conn.rollback()
        return False, 0, "Riscatto streak non riuscito"
    finally:
        put_conn(conn)


def use_streak_shield(user_id):
    """Consuma uno Streak Shield per colmare un giorno perso della streak 30.

    La streak è basata sui giorni dall'iscrizione: se ne salta uno, quel giorno
    resta "da riscuotere" e la progressione si ferma finché non lo reclami.
    Lo shield reclama automaticamente il giorno mancante più vecchio (gap),
    così l'utente non perde il posto. Se non c'è alcun gap (è già in pari),
    lo shield NON viene consumato.
    Ritorna (success, message, earned).
    """
    from storage.store import get_inventory, use_consumable

    today = datetime.now(timezone.utc).date()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        reg = row["created_at"].date() if row and row["created_at"] else today
    finally:
        put_conn(conn)

    expected_day = min((today - reg).days + 1, 30)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT day_number, claimed FROM streak_30days WHERE user_id=%s ORDER BY day_number",
            (user_id,),
        )
        claimed = {r["day_number"]: r["claimed"] for r in cur.fetchall()}
    finally:
        put_conn(conn)

    target_day = expected_day
    for d in range(1, expected_day):
        if claimed.get(d, 0) != 1:
            target_day = d
            break

    if target_day >= expected_day:
        # Nessun giorno perso: niente da proteggere, non consumare lo shield.
        return False, "nothing_to_protect", 0

    if get_inventory(user_id).get("streak_shield", 0) <= 0:
        return False, "no_shield", 0

    success, earned, msg = claim_streak_30_day(user_id, day=target_day)
    if not success:
        return False, msg, 0

    use_consumable(user_id, "streak_shield")
    return True, "ok", earned
