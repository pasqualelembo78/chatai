import json
from db import get_conn, put_conn


def get_world_state():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT scene, events, flags FROM world_state WHERE id=1")
        row = cur.fetchone()
        if row:
            return {
                "scene": row["scene"],
                "events": json.loads(row["events"]),
                "flags": json.loads(row["flags"])
            }
        return {"scene": "default", "events": [], "flags": {}}
    finally:
        put_conn(conn)


def save_world_state(state):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE world_state SET scene=%s, events=%s, flags=%s WHERE id=1",
            (state["scene"], json.dumps(state["events"]), json.dumps(state["flags"]))
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_user_world_state(user_id):
    """Get world state for a specific user."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT scene, events, flags FROM user_world_state WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if row:
            return {"scene": row["scene"], "events": json.loads(row["events"]), "flags": json.loads(row["flags"])}
        # Initialize from global world state as fallback
        ws = get_world_state()
        save_user_world_state(user_id, ws)
        return ws
    finally:
        put_conn(conn)


def save_user_world_state(user_id, world_state):
    """Save world state for a specific user."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_world_state (user_id, scene, events, flags, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
            scene=EXCLUDED.scene, events=EXCLUDED.events, flags=EXCLUDED.flags, updated_at=EXCLUDED.updated_at
        """, (user_id, world_state.get("scene", "default"),
              json.dumps(world_state.get("events", [])),
              json.dumps(world_state.get("flags", {}))))
        conn.commit()
    finally:
        put_conn(conn)
