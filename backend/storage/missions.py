"""Sistema missioni MVC.

Le missioni sono derivate dai messaggi esistenti (tabella `messages`),
quindi non serve duplicare i dati utente. Ogni giorno della settimana ha
un set fisso di 2 missioni (schedule a rotazione), più una missione
"streak settimanale" di 7 giorni sempre attiva. Tutto si resetta
settimanalmente ("ricomincia daccapo").

Le ricompense vengono assegnate in modo idempotente (tabella
`user_mission_rewards` con vincolo UNIQUE su user_id+mission_id+period),
quindi richiamare `award_missions` più volte per lo stesso giorno/settimana
non paga due volte.
"""
from datetime import date, datetime, timedelta

from db import get_conn, put_conn

# ── Template delle missioni ────────────────────────────────────────
# kind:
#   msg_count   -> numero di messaggi utente inviati oggi
#   any_char    -> ha chattato (>=1 messaggio) con almeno 1 personaggio oggi
#   chars_count -> numero di personaggi DIVERSI chattati oggi
#   new_char    -> personaggi mai incontrati prima, chattati oggi
#   week_streak -> giorni distinti della settimana con >=1 messaggio
MISSION_TEMPLATES = {
    "MSG10":   {"kind": "msg_count",   "target": 10, "reward": 50,
                "title": "Messaggiatore", "desc": "Invia 10 messaggi oggi"},
    "MSG20":   {"kind": "msg_count",   "target": 20, "reward": 80,
                "title": "Chatterbox", "desc": "Invia 20 messaggi oggi"},
    "NEWCHAR": {"kind": "new_char",    "target": 1,  "reward": 80,
                "title": "Nuova conoscenza", "desc": "Chatta con 1 personaggio mai incontrato"},
    "ANYCHAR": {"kind": "any_char",    "target": 1,  "reward": 30,
                "title": "Una chiacchierata", "desc": "Chatta con almeno 1 personaggio oggi"},
    "CHARS3":  {"kind": "chars_count", "target": 3,  "reward": 80,
                "title": "Socializziamo", "desc": "Chatta con 3 personaggi diversi oggi"},
}

# Schedule settimanale (0=Lunedì ... 6=Domenica). Set diversi per ogni giorno.
WEEKLY_SCHEDULE = [
    ["ANYCHAR", "MSG10"],   # Lun
    ["MSG10", "NEWCHAR"],   # Mar
    ["ANYCHAR", "CHARS3"],  # Mer
    ["MSG20", "NEWCHAR"],   # Gio
    ["MSG10", "CHARS3"],    # Ven
    ["ANYCHAR", "NEWCHAR"], # Sab
    ["MSG20", "CHARS3"],    # Dom
]

WEEKLY_STREAK = {
    "id": "WEEK_STREAK", "kind": "week_streak", "target": 7, "reward": 200,
    "title": "Streak 7 giorni", "desc": "Chatta almeno 1 messaggio per 7 giorni della settimana",
}


def _today():
    return date.today()


def _week_period(today):
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"


def _week_bounds(today):
    # Lunedì 00:00 di questa settimana ISO -> lunedì della settimana successiva
    monday = today - timedelta(days=today.weekday())
    start = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    end = start + timedelta(days=7)
    return start, end


def _count(user_id, sql, params):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row["count"] if row and "count" in row else (row[0] if row else 0)
    finally:
        put_conn(conn)


def _compute_progress(user_id, spec, today):
    kind = spec["kind"]
    today_str = today.isoformat()
    if kind == "msg_count":
        return _count(user_id,
            "SELECT COUNT(*) AS count FROM messages "
            "WHERE user_id=%s AND role='user' AND timestamp::date = %s",
            (user_id, today_str))
    if kind in ("any_char", "chars_count"):
        return _count(user_id,
            "SELECT COUNT(DISTINCT character_id) AS count FROM messages "
            "WHERE user_id=%s AND role='user' AND timestamp::date = %s",
            (user_id, today_str))
    if kind == "new_char":
        return _count(user_id,
            "SELECT COUNT(DISTINCT m.character_id) AS count FROM messages m "
            "WHERE m.user_id=%s AND m.role='user' AND m.timestamp::date = %s "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM messages m2 WHERE m2.user_id=%s AND m2.role='user' "
            "  AND m2.character_id = m.character_id AND m2.timestamp::date < %s"
            ")",
            (user_id, today_str, user_id, today_str))
    if kind == "week_streak":
        start, end = _week_bounds(today)
        return _count(user_id,
            "SELECT COUNT(DISTINCT DATE(timestamp)) AS count FROM messages "
            "WHERE user_id=%s AND role='user' AND timestamp >= %s AND timestamp < %s",
            (user_id, start, end))
    return 0


def _is_awarded(user_id, mission_id, period):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM user_mission_rewards WHERE user_id=%s AND mission_id=%s AND period=%s",
            (user_id, mission_id, period))
        return cur.fetchone() is not None
    finally:
        put_conn(conn)


def _build_mission(user_id, spec, mission_id, period, today):
    progress = _compute_progress(user_id, spec, today)
    completed = progress >= spec["target"]
    awarded = completed and _is_awarded(user_id, mission_id, period)
    return {
        "code": mission_id,
        "title": spec["title"],
        "description": spec["desc"],
        "target": spec["target"],
        "reward": spec["reward"],
        "progress": progress,
        "completed": completed,
        "awarded": awarded,
        "period": period,
    }


def get_active_missions(user_id):
    """Restituisce le missioni attive per l'utente (oggi + streak settimanale)."""
    today = _today()
    week_period = _week_period(today)
    weekday = today.weekday()
    missions = []
    for tid in WEEKLY_SCHEDULE[weekday]:
        spec = MISSION_TEMPLATES[tid]
        missions.append(_build_mission(user_id, spec, tid, today.isoformat(), today))
    missions.append(_build_mission(user_id, WEEKLY_STREAK, WEEKLY_STREAK["id"], week_period, today))
    return missions


def award_missions(user_id):
    """Assegna le ricompense delle missioni completate non ancora riscosse.
    Idempotente grazie al vincolo UNIQUE su (user_id, mission_id, period).
    Restituisce la lista delle missioni appena pagate (per notifiche)."""
    from storage.mevacoins import add_mevacoins

    today = _today()
    week_period = _week_period(today)
    missions = get_active_missions(user_id)
    paid = []
    for m in missions:
        if not m["completed"] or m["awarded"]:
            continue
        try:
            add_mevacoins(user_id, m["reward"], f"mission:{m['id']}:{m['period']}")
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO user_mission_rewards (user_id, mission_id, period, reward) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (user_id, m["id"], m["period"], m["reward"]))
                conn.commit()
            finally:
                put_conn(conn)
            paid.append(m)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"award_missions FAILED user={user_id} mission={m['id']}: {e}")
    return paid
