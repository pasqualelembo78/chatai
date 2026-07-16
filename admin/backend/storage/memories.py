import json
from datetime import datetime
from db import get_conn, put_conn


def add_memory(user_id, character_id, summary, topics, message_count, relationship_snapshot):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO conversation_memory
               (user_id, character_id, summary, topics, message_count, relationship_snapshot)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, character_id, summary, json.dumps(topics),
             message_count, json.dumps(relationship_snapshot))
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_memories(user_id, character_id, limit=3):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT summary, topics, relationship_snapshot, created_at
               FROM conversation_memory
               WHERE user_id=%s AND character_id=%s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, character_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        put_conn(conn)


def get_last_summary_checkpoint(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(message_count), 0) FROM conversation_memory WHERE user_id=%s AND character_id=%s",
            (user_id, character_id)
        )
        row = cur.fetchone()
        return row["coalesce"] if row else 0
    finally:
        put_conn(conn)


def get_user_memory(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT memory_data, updated_at FROM user_memory WHERE user_id=%s",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            return {"memory": json.loads(row["memory_data"]), "updated_at": row["updated_at"]}
        return {"memory": {}, "updated_at": None}
    finally:
        put_conn(conn)


def update_user_memory(user_id, new_facts):
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    memory.update(new_facts)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_memory (user_id, memory_data, created_at, updated_at)
               VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET
               memory_data=EXCLUDED.memory_data, updated_at=EXCLUDED.updated_at""",
            (user_id, json.dumps(memory))
        )
        conn.commit()
    finally:
        put_conn(conn)
    return memory


def reset_user_memory(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_memory WHERE user_id=%s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def reset_conversation(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        cur.execute("DELETE FROM conversation_memory WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        cur.execute("DELETE FROM personality_shifts WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        cur.execute("DELETE FROM relationships WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        cur.execute("DELETE FROM user_personality WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        cur.execute("DELETE FROM character_evolution WHERE user_id=%s AND character_id=%s", (user_id, character_id))
        conn.commit()
    finally:
        put_conn(conn)


def reset_all_user_data(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM conversation_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM personality_shifts WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM relationships WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM character_evolution WHERE user_id=%s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def update_user_memory_enhanced(user_id, new_facts, source_character=None, source_name=None):
    """Enhanced memory update with importance scoring and deduplication."""
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    now = datetime.now().isoformat()

    for key, value in new_facts.items():
        val_str = value["value"] if isinstance(value, dict) and "value" in value else str(value)
        src = source_name or (value.get("source_name", "") if isinstance(value, dict) else "")

        if key in memory:
            existing_fact = memory[key]
            if isinstance(existing_fact, dict):
                # Deduplication: if same value, just bump mentions
                if existing_fact.get("value", "").lower().strip() == val_str.lower().strip():
                    existing_fact["mentions"] = existing_fact.get("mentions", 1) + 1
                    existing_fact["last_mentioned"] = now
                    # Boost importance with each mention (capped at 1.0)
                    existing_fact["importance"] = min(1.0, existing_fact.get("importance", 0.5) + 0.05)
                else:
                    # Conflict: user said something different. Keep newer, mark old as superseded.
                    existing_fact["previous"] = existing_fact.get("value", "")
                    existing_fact["value"] = val_str
                    existing_fact["mentions"] = 1
                    existing_fact["last_mentioned"] = now
                    existing_fact["importance"] = 0.7  # New info gets moderate importance
                    existing_fact["source_name"] = src
            else:
                memory[key] = {
                    "value": val_str,
                    "source_name": src,
                    "mentions": 1,
                    "last_mentioned": now,
                    "importance": 0.5,
                }
        else:
            memory[key] = {
                "value": val_str,
                "source_name": src,
                "mentions": 1,
                "last_mentioned": now,
                "importance": 0.5,
            }

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_memory (user_id, memory_data, created_at, updated_at)
               VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET
               memory_data=EXCLUDED.memory_data, updated_at=EXCLUDED.updated_at""",
            (user_id, json.dumps(memory))
        )
        conn.commit()
    finally:
        put_conn(conn)
    return memory


def decay_user_memory(user_id, decay_days=30, min_importance=0.1):
    """Apply temporal decay to user memory facts. Call periodically."""
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    now = datetime.now()
    changed = False

    for key in list(memory.keys()):
        fact = memory[key]
        if not isinstance(fact, dict):
            continue
        last = fact.get("last_mentioned", "")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                days_since = (now - last_dt).days
                if days_since > decay_days:
                    # Decay importance over time
                    decay_factor = max(0, 1.0 - (days_since - decay_days) / 90)
                    fact["importance"] = max(min_importance, fact.get("importance", 0.5) * decay_factor)
                    changed = True
                    # Remove facts below threshold and not mentioned much
                    if fact["importance"] <= min_importance and fact.get("mentions", 1) <= 1:
                        del memory[key]
                        changed = True
            except Exception:
                pass

    if changed:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """UPDATE user_memory SET memory_data=%s, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s""",
                (json.dumps(memory), user_id)
            )
            conn.commit()
        finally:
            put_conn(conn)


def get_relevant_memories(user_id, context_hint=None, limit=10):
    """Get user memories sorted by importance + recency. Optionally filtered by context."""
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    facts = []
    for key, value in memory.items():
        if not isinstance(value, dict):
            facts.append({"key": key, "value": str(value), "importance": 0.5, "mentions": 1})
            continue
        score = value.get("importance", 0.5) * 0.6 + min(1.0, value.get("mentions", 1) / 5) * 0.4
        # Recency bonus
        last = value.get("last_mentioned", "")
        if last:
            try:
                days = (datetime.now() - datetime.fromisoformat(last)).days
                recency_bonus = max(0, 1.0 - days / 90) * 0.3
                score += recency_bonus
            except Exception:
                pass
        facts.append({
            "key": key,
            "value": value.get("value", ""),
            "source_name": value.get("source_name", ""),
            "importance": value.get("importance", 0.5),
            "mentions": value.get("mentions", 1),
            "score": score,
        })

    # Sort by score descending
    facts.sort(key=lambda x: x.get("score", 0), reverse=True)
    return facts[:limit]


def consolidate_user_memory(user_id, target_count=15):
    """Compress user memory to keep only the most important facts."""
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    if len(memory) <= target_count:
        return  # Nothing to consolidate

    # Score and sort
    scored = []
    for key, value in memory.items():
        if not isinstance(value, dict):
            scored.append({"key": key, "score": 0.5, "data": value})
            continue
        score = value.get("importance", 0.5) * 0.5 + min(1.0, value.get("mentions", 1) / 5) * 0.3
        # Recency bonus
        last = value.get("last_mentioned", "")
        if last:
            try:
                days = (datetime.now() - datetime.fromisoformat(last)).days
                score += max(0, 1.0 - days / 90) * 0.2
            except Exception:
                pass
        scored.append({"key": key, "score": score, "data": value})

    scored.sort(key=lambda x: x["score"], reverse=True)
    consolidated = {item["key"]: item["data"] for item in scored[:target_count]}

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE user_memory SET memory_data=%s, updated_at=CURRENT_TIMESTAMP,
               memory_version=COALESCE(memory_version, 1) + 1 WHERE user_id=%s""",
            (json.dumps(consolidated), user_id)
        )
        conn.commit()
    finally:
        put_conn(conn)
