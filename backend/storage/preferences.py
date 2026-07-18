import json

from db import get_conn, put_conn


def get_user_preferences(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if row:
            user_gender = row["user_gender"] if row["user_gender"] else ""
            user_age = row["user_age"] if row["user_age"] else 0
            gender_interest = row["gender_interest"]
            orientation = derive_sexual_orientation(user_gender, gender_interest)
            verified_birth_year = row["verified_birth_year"] if row.get("verified_birth_year") else 0
            return {
                "gender_interest": gender_interest,
                "age_range": row["age_range"],
                "interest_tags": json.loads(row["interest_tags"] or "[]"),
                "show_adult": bool(row["show_adult"]),
                "user_gender": user_gender,
                "user_age": user_age,
                "verified_birth_year": verified_birth_year,
                "age_verified": _is_adult_from_birth_year(verified_birth_year),
                "sexual_orientation": orientation,
            }
        return {"gender_interest": "", "age_range": "", "interest_tags": [], "show_adult": False, "user_gender": "", "user_age": 0,
                "verified_birth_year": 0, "age_verified": False, "sexual_orientation": ""}
    finally:
        put_conn(conn)


def _is_adult_from_birth_year(birth_year):
    if not birth_year:
        return False
    try:
        return (2026 - int(birth_year)) >= 18
    except (ValueError, TypeError):
        return False


def set_verified_birth_year(user_id, birth_year):
    """Memorizza l'anno di nascita verificato (inserito dall'utente nel dialog 18+).

    Restituisce True se l'utente risulta maggiorenne (>=18 anni), False altrimenti.
    Il valore e' la base del gate età lato server per i contenuti per adulti.
    """
    try:
        birth_year = int(birth_year)
    except (ValueError, TypeError):
        return False
    import datetime
    current_year = datetime.datetime.utcnow().year
    if birth_year < 1900 or birth_year > current_year:
        return False
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_preferences (user_id, verified_birth_year, updated_at)
               VALUES (%s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET
               verified_birth_year=EXCLUDED.verified_birth_year,
               updated_at=EXCLUDED.updated_at""",
            (user_id, birth_year),
        )
        conn.commit()
    finally:
        put_conn(conn)
    return _is_adult_from_birth_year(birth_year)


def is_age_verified(user_id):
    prefs = get_user_preferences(user_id)
    return bool(prefs.get("age_verified"))


def save_user_preferences(user_id, data):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
        existing = cur.fetchone()
        old = dict(existing) if existing else {}

        interests = data.get("interest_tags") or data.get("interests") or old.get("interest_tags", [])
        if isinstance(interests, str):
            interests = json.loads(interests) if interests else []

        cur.execute(
            """INSERT INTO user_preferences
               (user_id, gender_interest, age_range, interest_tags, show_adult, user_gender, user_age, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET
               gender_interest=EXCLUDED.gender_interest, age_range=EXCLUDED.age_range,
               interest_tags=EXCLUDED.interest_tags, show_adult=EXCLUDED.show_adult,
               user_gender=EXCLUDED.user_gender, user_age=EXCLUDED.user_age,
               updated_at=EXCLUDED.updated_at""",
            (user_id,
             data.get("gender_interest") or old.get("gender_interest", ""),
             data.get("age_range") or old.get("age_range", ""),
             json.dumps(interests),
             data["show_adult"] if "show_adult" in data else old.get("show_adult", 0),
             data.get("user_gender") or old.get("user_gender", ""),
             data.get("user_age") or old.get("user_age", 0))
        )
        conn.commit()
    finally:
        put_conn(conn)


def derive_sexual_orientation(user_gender, gender_interest):
    if not user_gender or not gender_interest:
        return ""
    g = user_gender.lower()
    gi = gender_interest.lower()

    if g == "non-binary":
        return "bisessuale"

    if g == "female" and gi == "femminile":
        return "lesbica"
    if g == "male" and gi == "maschile":
        return "gay"
    if g == "female" and gi == "maschile":
        return "etero"
    if g == "male" and gi == "femminile":
        return "etero"
    if "non binario" in gi or "non-binary" in gi:
        return "bisessuale"

    return ""
