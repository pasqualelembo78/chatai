import json

from db import get_conn, put_conn


def get_personality(character_id, defaults=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT warmth, strictness, patience, sarcasm FROM personality WHERE character_id=%s",
            (character_id,)
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return defaults or {"warmth": 5, "strictness": 5, "patience": 5, "sarcasm": 0}
    finally:
        put_conn(conn)


def update_personality(character_id, deltas, defaults=None):
    current = get_personality(character_id, defaults)
    for k, v in deltas.items():
        current[k] = max(0, min(10, current.get(k, 0) + v))
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO personality (character_id, warmth, strictness, patience, sarcasm)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (character_id) DO UPDATE SET
               warmth=EXCLUDED.warmth, strictness=EXCLUDED.strictness,
               patience=EXCLUDED.patience, sarcasm=EXCLUDED.sarcasm""",
            (character_id, current["warmth"], current["strictness"], current["patience"], current["sarcasm"])
        )
        conn.commit()
    finally:
        put_conn(conn)
    return current


def record_personality_shift(user_id, character_id, pressure_type, pressure_level, deltas, description):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO personality_shifts
               (user_id, character_id, pressure_type, pressure_level, deltas, description)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, character_id, pressure_type, pressure_level, json.dumps(deltas), description)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_recent_shifts(user_id, character_id, limit=5):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT pressure_type, pressure_level, deltas, description, created_at
               FROM personality_shifts
               WHERE user_id=%s AND character_id=%s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, character_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        put_conn(conn)


def describe_personality(personality, core_traits):
    diff_descriptions = []
    for trait in ["warmth", "strictness", "patience", "sarcasm"]:
        current = personality.get(trait, 5)
        core = core_traits.get(trait, 5)
        diff = current - core
        if diff >= 2:
            if trait == "warmth":
                diff_descriptions.append("più caloroso del solito")
            elif trait == "strictness":
                diff_descriptions.append("più severo del solito")
            elif trait == "patience":
                diff_descriptions.append("più paziente del solito")
            elif trait == "sarcasm":
                diff_descriptions.append("più sarcastico del solito")
        elif diff <= -2:
            if trait == "warmth":
                diff_descriptions.append("più freddo del solito")
            elif trait == "strictness":
                diff_descriptions.append("meno severo del solito")
            elif trait == "patience":
                diff_descriptions.append("meno paziente del solito")
            elif trait == "sarcasm":
                diff_descriptions.append("meno sarcastico del solito")

    if not diff_descriptions:
        return ""

    return "EVOLUZIONE PERSONALITÀ: Il personaggio è " + ", ".join(diff_descriptions) + " rispetto al normale."


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Per-User Personality
# ═══════════════════════════════════════════════════════════════════

def get_user_personality(user_id, character_id, core_traits=None):
    """Get personality for a specific user+character pair. Falls back to shared personality."""
    core_traits = core_traits or {}
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT warmth, strictness, patience, sarcasm FROM user_personality WHERE user_id=%s AND character_id=%s",
            (user_id, character_id)
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        # Fallback: copy shared personality as starting point
        shared = get_personality(character_id, core_traits)
        conn2 = get_conn()
        try:
            cur2 = conn2.cursor()
            cur2.execute(
                """INSERT INTO user_personality (user_id, character_id, warmth, strictness, patience, sarcasm)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, character_id) DO NOTHING""",
                (user_id, character_id, shared.get("warmth", 5), shared.get("strictness", 5),
                 shared.get("patience", 5), shared.get("sarcasm", 0))
            )
            conn2.commit()
        finally:
            put_conn(conn2)
        return shared
    finally:
        put_conn(conn)


def update_user_personality(user_id, character_id, deltas):
    """Update per-user personality with deltas (dict of trait->delta)."""
    current = get_user_personality(user_id, character_id)
    for trait, delta in deltas.items():
        if trait in current:
            current[trait] = max(0, min(10, current.get(trait, 5) + delta))
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_personality (user_id, character_id, warmth, strictness, patience, sarcasm, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, character_id) DO UPDATE SET
            warmth=EXCLUDED.warmth, strictness=EXCLUDED.strictness,
            patience=EXCLUDED.patience, sarcasm=EXCLUDED.sarcasm, updated_at=EXCLUDED.updated_at
        """, (user_id, character_id, current["warmth"], current["strictness"],
              current["patience"], current["sarcasm"]))
        conn.commit()
    finally:
        put_conn(conn)
    return current


def set_user_personality(user_id, character_id, personality):
    """Set full personality for a user+character pair."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_personality (user_id, character_id, warmth, strictness, patience, sarcasm, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, character_id) DO UPDATE SET
            warmth=EXCLUDED.warmth, strictness=EXCLUDED.strictness,
            patience=EXCLUDED.patience, sarcasm=EXCLUDED.sarcasm, updated_at=EXCLUDED.updated_at
        """, (user_id, character_id, personality.get("warmth", 5), personality.get("strictness", 5),
              personality.get("patience", 5), personality.get("sarcasm", 0)))
        conn.commit()
    finally:
        put_conn(conn)
