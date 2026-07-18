import json
from db import get_conn, put_conn


def get_relationship(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT trust, affinity, respect, conflict, intimacy, pressure_level FROM relationships WHERE user_id=%s AND character_id=%s",
            (user_id, character_id)
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return {"trust": 0, "affinity": 0, "respect": 0, "conflict": 0, "intimacy": 0, "pressure_level": 0}
    finally:
        put_conn(conn)


def get_user_intimacies(user_id):
    """Mappa {character_id: intimacy} per tutti i personaggi di un utente (1 query)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT character_id, intimacy FROM relationships WHERE user_id=%s",
            (user_id,)
        )
        return {row["character_id"]: int(row["intimacy"]) for row in cur.fetchall()}
    finally:
        put_conn(conn)


def update_relationship(user_id, character_id, deltas):
    current = get_relationship(user_id, character_id)
    for k, v in deltas.items():
        current[k] = max(0, min(100, current.get(k, 0) + v))
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO relationships
               (user_id, character_id, trust, affinity, respect, conflict, intimacy, pressure_level)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id, character_id) DO UPDATE SET
               trust=EXCLUDED.trust, affinity=EXCLUDED.affinity,
               respect=EXCLUDED.respect, conflict=EXCLUDED.conflict,
               intimacy=EXCLUDED.intimacy, pressure_level=EXCLUDED.pressure_level""",
            (user_id, character_id, current["trust"], current["affinity"],
             current["respect"], current["conflict"],
             current.get("intimacy", 0), current.get("pressure_level", 0))
        )
        conn.commit()
    finally:
        put_conn(conn)
    return current


def update_intimacy(user_id, character_id, delta, intimacy_config):
    current = get_relationship(user_id, character_id)
    intimacy = current.get("intimacy", 0)
    intimacy = max(0, min(100, intimacy + delta))
    current["intimacy"] = intimacy
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO relationships (user_id, character_id, intimacy)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, character_id) DO UPDATE SET intimacy=EXCLUDED.intimacy""",
            (user_id, character_id, intimacy)
        )
        conn.commit()
    finally:
        put_conn(conn)
    return current


def update_pressure_level(user_id, character_id, pressure_level):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO relationships (user_id, character_id, pressure_level)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, character_id) DO UPDATE SET pressure_level=EXCLUDED.pressure_level""",
            (user_id, character_id, pressure_level)
        )
        conn.commit()
    finally:
        put_conn(conn)


def describe_intimacy_level(intimacy, config):
    if intimacy <= 0:
        return "Sconosciuti"
    elif intimacy < config["threshold_refuse"]:
        return "Conoscenza superficiale"
    elif intimacy < config["threshold_accept"]:
        return "Confidenza crescente"
    elif intimacy < 80:
        return "Relazione intima"
    else:
        return "Relazione profonda"
