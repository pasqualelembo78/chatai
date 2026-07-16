from datetime import datetime
from db import get_conn, put_conn


def get_character_demographics(character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE character_id=%s", (character_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        put_conn(conn)


# Columns that may be written via update_character_demographics. Any other key
# is rejected to prevent SQL injection through interpolated identifiers.
_ALLOWED_DEMO_COLUMNS = {
    "gender", "gender_display", "sexual_orientation", "sexual_orientation_display",
    "birth_date", "birth_place", "species", "age_static",
}


def update_character_demographics(character_id, **kwargs):
    # Only allow known columns; reject anything else before it reaches SQL.
    for k in kwargs:
        if k not in _ALLOWED_DEMO_COLUMNS:
            raise ValueError(f"colonna non consentita: {k}")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE character_id=%s", (character_id,))
        existing = cur.fetchone()
        if existing:
            sets = ", ".join(f"{k}=%s" for k in kwargs)
            cur.execute(f"UPDATE character_demographics SET {sets} WHERE character_id=%s",
                        list(kwargs.values()) + [character_id])
        else:
            kwargs["character_id"] = character_id
            cols = ", ".join(kwargs.keys())
            phs = ", ".join(["%s"] * len(kwargs))
            cur.execute(f"INSERT INTO character_demographics ({cols}) VALUES ({phs})", list(kwargs.values()))
        conn.commit()
    finally:
        put_conn(conn)


def get_characters_by_species(species):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE species=%s", (species,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_characters_by_gender(gender):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE gender=%s", (gender,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_characters_by_orientation(orientation):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE sexual_orientation=%s", (orientation,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_upcoming_birthdays(days=7):
    from datetime import date, timedelta
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE birth_date != ''")
        rows = cur.fetchall()
        result = []
        today = date.today()
        for r in rows:
            bd = r["birth_date"]
            if not bd or bd.startswith("Y") or "|" in bd:
                continue
            try:
                parts = bd.split("-")
                bday = date(int(parts[0]), int(parts[1]), int(parts[2]))
                this_year = bday.replace(year=today.year)
                if this_year < today:
                    this_year = bday.replace(year=today.year + 1)
                diff = (this_year - today).days
                if 0 <= diff <= days:
                    result.append({"character_id": r["character_id"], "birthday": bd, "days_until": diff})
            except (ValueError, IndexError, TypeError):
                pass
        return sorted(result, key=lambda x: x["days_until"])
    finally:
        put_conn(conn)


def register_character_birthday(character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO character_birthdays (character_id) VALUES (%s) ON CONFLICT DO NOTHING", (character_id,))
        conn.commit()
    finally:
        put_conn(conn)


def mark_birthday_notified(character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE character_birthdays SET last_notified=%s WHERE character_id=%s",
                     (datetime.now().isoformat(), character_id))
        conn.commit()
    finally:
        put_conn(conn)
