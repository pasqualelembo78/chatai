import json
import os
import base64
import hashlib
import logging
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import psycopg2.errors

from db import get_conn, put_conn

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def _get_master_key():
    key = os.environ.get("MASTER_KEY", "")
    if not key:
        logger.warning("MASTER_KEY not set, using derived key (INSECURE)")
        key = hashlib.sha256(b"chatai-insecure-fallback-key").hexdigest()
    return key[:64]

def encrypt_value(plaintext):
    if not plaintext:
        return ""
    try:
        from cryptography.fernet import Fernet
        master = _get_master_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
        cipher = Fernet(fernet_key)
        return cipher.encrypt(plaintext.encode()).decode()
    except ImportError:
        logger.warning("cryptography not installed, storing in plaintext")
        return plaintext
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return ""

def decrypt_value(ciphertext):
    if not ciphertext:
        return ""
    try:
        from cryptography.fernet import Fernet, InvalidToken
        master = _get_master_key()
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
        cipher = Fernet(fernet_key)
        return cipher.decrypt(ciphertext.encode()).decode()
    except ImportError:
        return ciphertext
    except (InvalidToken, Exception) as e:
        logger.error(f"Decryption failed: {e}")
        return ""


def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                trust REAL DEFAULT 0,
                affinity REAL DEFAULT 0,
                respect REAL DEFAULT 0,
                conflict REAL DEFAULT 0,
                intimacy REAL DEFAULT 0,
                pressure_level REAL DEFAULT 0,
                PRIMARY KEY (user_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personality (
                character_id TEXT PRIMARY KEY,
                warmth REAL DEFAULT 5,
                strictness REAL DEFAULT 5,
                patience REAL DEFAULT 5,
                sarcasm REAL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                scene TEXT DEFAULT 'default',
                events TEXT DEFAULT '[]',
                flags TEXT DEFAULT '{}'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                topics TEXT DEFAULT '[]',
                message_count INTEGER DEFAULT 0,
                relationship_snapshot TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personality_shifts (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                pressure_type TEXT,
                pressure_level REAL,
                deltas TEXT DEFAULT '{}',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id TEXT PRIMARY KEY,
                memory_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_characters (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER DEFAULT 0,
                role TEXT DEFAULT '',
                category TEXT DEFAULT '',
                avatar TEXT DEFAULT '💬',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                is_adult INTEGER DEFAULT 0,
                essence TEXT DEFAULT '',
                personality TEXT DEFAULT '',
                speaking_style TEXT DEFAULT '',
                backstory TEXT DEFAULT '',
                hobbies TEXT DEFAULT '[]',
                system_prompt TEXT DEFAULT '',
                core_traits TEXT DEFAULT '{}',
                intimacy_config TEXT DEFAULT '{}',
                refusal_style TEXT DEFAULT 'dolce',
                evolution TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            INSERT INTO world_state (id, scene, events, flags)
            VALUES (1, 'default', '[]', '{}')
            ON CONFLICT (id) DO NOTHING
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id TEXT PRIMARY KEY,
                is_premium INTEGER DEFAULT 0,
                sku TEXT DEFAULT '',
                purchase_token TEXT DEFAULT '',
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_evolution (
                user_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                current_stage TEXT DEFAULT 'base',
                unlocked_stages TEXT DEFAULT '["base"]',
                flags TEXT DEFAULT '{}',
                trait_modifiers TEXT DEFAULT '{}',
                intimacy_peak REAL DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                action TEXT NOT NULL,
                detail TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS moderation_flags (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                flagged_by TEXT NOT NULL DEFAULT 'system',
                reason TEXT NOT NULL,
                content_type TEXT DEFAULT '',
                content_snippet TEXT DEFAULT '',
                severity TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                gender_interest TEXT DEFAULT '',
                age_range TEXT DEFAULT '',
                interest_tags TEXT DEFAULT '[]',
                show_adult INTEGER DEFAULT 0,
                user_gender TEXT DEFAULT '',
                user_age INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mevacoins (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mevacoins_transactions (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_checkins (
                user_id TEXT NOT NULL,
                checkin_date TEXT NOT NULL,
                redeemed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, checkin_date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS new_user_bonus (
                user_id TEXT NOT NULL,
                day_number INTEGER NOT NULL,
                claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS content_unlocks (
                user_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                spent_amount INTEGER NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, content_type, content_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                user_id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_earnings (
                referrer_id TEXT NOT NULL,
                referred_id TEXT NOT NULL,
                bonus_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_id, bonus_type)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_shares (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                share_date TEXT NOT NULL,
                platform TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streak_milestones (
                user_id TEXT NOT NULL,
                milestone INTEGER NOT NULL,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, milestone)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_char ON messages(user_id, character_id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_demographics (
                character_id TEXT PRIMARY KEY,
                gender TEXT DEFAULT '',
                gender_display TEXT DEFAULT '',
                sexual_orientation TEXT DEFAULT 'etero',
                sexual_orientation_display TEXT DEFAULT 'eterosessuale',
                birth_date TEXT DEFAULT '',
                birth_place TEXT DEFAULT '',
                species TEXT DEFAULT 'umano',
                age_static INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_gender ON character_demographics(gender)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_species ON character_demographics(species)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demo_orientation ON character_demographics(sexual_orientation)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS character_birthdays (
                character_id TEXT PRIMARY KEY,
                last_notified TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                character_id TEXT,
                user_id TEXT,
                data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        put_conn(conn)


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
            "UPDATE relationships SET intimacy=%s WHERE user_id=%s AND character_id=%s",
            (intimacy, user_id, character_id)
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
            "UPDATE relationships SET pressure_level=%s WHERE user_id=%s AND character_id=%s",
            (pressure_level, user_id, character_id)
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


def add_message(user_id, character_id, role, content):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (user_id, character_id, role, content) VALUES (%s, %s, %s, %s)",
            (user_id, character_id, role, content)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_recent_messages(user_id, character_id, limit=30):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM messages WHERE user_id=%s AND character_id=%s ORDER BY timestamp DESC LIMIT %s",
            (user_id, character_id, limit)
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        put_conn(conn)


def count_messages(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM messages WHERE user_id=%s AND character_id=%s",
            (user_id, character_id)
        )
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)


def count_all_user_messages(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM messages WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)


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


def get_evolution(user_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT current_stage, unlocked_stages, flags, trait_modifiers,
                      intimacy_peak, total_messages
               FROM character_evolution
               WHERE user_id=%s AND character_id=%s""",
            (user_id, character_id)
        )
        row = cur.fetchone()
        if row:
            return {
                "current_stage": row["current_stage"],
                "unlocked_stages": json.loads(row["unlocked_stages"]),
                "flags": json.loads(row["flags"]),
                "trait_modifiers": json.loads(row["trait_modifiers"]),
                "intimacy_peak": row["intimacy_peak"],
                "total_messages": row["total_messages"],
            }
        return {
            "current_stage": "base",
            "unlocked_stages": ["base"],
            "flags": {},
            "trait_modifiers": {},
            "intimacy_peak": 0,
            "total_messages": 0,
        }
    finally:
        put_conn(conn)


def update_evolution(user_id, character_id, evo):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO character_evolution
            (user_id, character_id, current_stage, unlocked_stages,
             flags, trait_modifiers, intimacy_peak, total_messages, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, character_id) DO UPDATE SET
            current_stage=EXCLUDED.current_stage, unlocked_stages=EXCLUDED.unlocked_stages,
            flags=EXCLUDED.flags, trait_modifiers=EXCLUDED.trait_modifiers,
            intimacy_peak=EXCLUDED.intimacy_peak, total_messages=EXCLUDED.total_messages,
            updated_at=EXCLUDED.updated_at
        """, (
            user_id, character_id,
            evo["current_stage"],
            json.dumps(evo["unlocked_stages"]),
            json.dumps(evo["flags"]),
            json.dumps(evo.get("trait_modifiers", {})),
            evo.get("intimacy_peak", 0),
            evo["total_messages"],
        ))
        conn.commit()
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
        cur.execute("DELETE FROM personality WHERE character_id=%s", (character_id,))
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


def create_user_character(user_id, data):
    char_id = data.get("id", "").strip().lower().replace(" ", "_")
    if not char_id:
        char_id = f"user_{user_id}_{int(time.time())}"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_characters
               (id, user_id, name, age, role, category, avatar, description, tags,
                is_adult, essence, personality, speaking_style, backstory, hobbies,
                system_prompt, core_traits, intimacy_config, refusal_style, evolution)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (char_id, user_id,
             data.get("name", ""), data.get("age", 0), data.get("role", ""),
             data.get("category", ""), data.get("avatar", "💬"), data.get("description", ""),
             json.dumps(data.get("tags", [])), 1 if data.get("is_adult") else 0,
             data.get("essence", ""), data.get("personality", ""),
             data.get("speaking_style", ""), data.get("backstory", ""),
             json.dumps(data.get("hobbies", [])), data.get("system_prompt", ""),
             json.dumps(data.get("core_traits", {})),
             json.dumps(data.get("intimacy_config", {})),
             data.get("refusal_style", "dolce"),
             json.dumps(data.get("evolution", {})))
        )
        conn.commit()
    finally:
        put_conn(conn)
    return get_user_character(char_id)


def get_user_character(char_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_characters WHERE id=%s", (char_id,))
        row = cur.fetchone()
        return _row_to_character(row) if row else None
    finally:
        put_conn(conn)


def get_user_characters(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM user_characters WHERE user_id=%s ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cur.fetchall()
        return [_row_to_character(r) for r in rows]
    finally:
        put_conn(conn)


def get_all_user_characters():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_characters ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [_row_to_character(r) for r in rows]
    finally:
        put_conn(conn)


def delete_user_character(char_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_characters WHERE id=%s", (char_id,))
        conn.commit()
    finally:
        put_conn(conn)


def _row_to_character(row):
    CATEGORY_NAMES = {
        "romantici": "Romantici", "amicizia": "Amicizia", "fantasy": "Fantasy",
        "horror": "Horror", "anime": "Anime", "scuola": "Scuola",
        "gamer": "Gamer", "detective": "Detective", "medicina": "Medicina",
        "business": "Business", "viaggi": "Viaggi", "motivazione": "Motivazione",
        "cucina": "Cucina", "tecnologia": "Tecnologia", "storia": "Storia",
        "supereroi": "Supereroi", "sopravvivenza": "Sopravvivenza", "sci-fi": "Sci-Fi",
        "sport": "Sport", "flirt": "Flirt", "relazioni": "Relazioni",
        "confessioni": "Confessioni", "seduzione": "Seduzione",
    }
    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "role": row["role"],
        "category": row["category"],
        "category_name": CATEGORY_NAMES.get(row["category"], row["category"]),
        "avatar": row["avatar"],
        "description": row["description"],
        "tags": json.loads(row["tags"] or "[]"),
        "is_adult": bool(row["is_adult"]),
        "essence": row["essence"] or "",
        "personality": row["personality"] or "",
        "speaking_style": row["speaking_style"] or "",
        "backstory": row["backstory"] or "",
        "hobbies": json.loads(row["hobbies"] or "[]"),
        "system_prompt": row["system_prompt"] or "",
        "core_traits": json.loads(row["core_traits"] or "{}"),
        "intimacy_config": json.loads(row["intimacy_config"] or "{}"),
        "refusal_style": row["refusal_style"] or "dolce",
        "evolution": json.loads(row["evolution"] or "{}"),
        "conversations": 0,
        "user_created": True,
        "user_id": row["user_id"],
    }


def is_user_premium(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT is_premium FROM premium_users WHERE user_id=%s", (user_id,)
        )
        row = cur.fetchone()
        return bool(row and row["is_premium"])
    finally:
        put_conn(conn)


def set_user_premium(user_id, premium=True, sku="", purchase_token=""):
    encrypted_token = encrypt_value(purchase_token)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO premium_users
               (user_id, is_premium, sku, purchase_token, activated_at)
               VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (user_id) DO UPDATE SET
               is_premium=EXCLUDED.is_premium, sku=EXCLUDED.sku,
               purchase_token=EXCLUDED.purchase_token, activated_at=EXCLUDED.activated_at""",
            (user_id, 1 if premium else 0, sku, encrypted_token)
        )
        conn.commit()
    finally:
        put_conn(conn)


def audit_log(user_id, action, detail="", ip="", user_agent=""):
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO audit_log (user_id, action, detail, ip, user_agent) VALUES (%s, %s, %s, %s, %s)",
                (user_id, action, detail[:500], ip[:50], user_agent[:200])
            )
            conn.commit()
        finally:
            put_conn(conn)
    except Exception as e:
        logger.warning(f"audit_log failed: {e}")


def prune_old_data(retention_days=DEFAULT_RETENTION_DAYS):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE timestamp < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_messages = cur.rowcount
        cur.execute(
            "DELETE FROM conversation_memory WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_memories = cur.rowcount
        cur.execute(
            "DELETE FROM personality_shifts WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention_days,)
        )
        deleted_shifts = cur.rowcount
        cur.execute(
            "DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '365 days'"
        )
        deleted_audit = cur.rowcount
        conn.commit()
        return {
            "messages": deleted_messages,
            "memories": deleted_memories,
            "shifts": deleted_shifts,
            "audit_logs": deleted_audit,
        }
    finally:
        put_conn(conn)


def get_all_users():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role, email, google_id, banned_until, created_at, last_login FROM users ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def ban_user(user_id, duration_hours=0):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if duration_hours > 0:
            from datetime import timedelta
            ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
            cur.execute("UPDATE users SET banned_until = %s WHERE id = %s", (ban_until, user_id))
        else:
            cur.execute("UPDATE users SET banned_until = NULL WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def export_user_data(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        data = {}

        cur.execute("SELECT id, username, role, email, google_id, created_at, last_login FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        data["profile"] = dict(user) if user else None

        cur.execute("SELECT character_id, trust, affinity, respect, conflict, intimacy, pressure_level FROM relationships WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["relationships"] = [dict(r) for r in rows]

        cur.execute("SELECT character_id, role, content, timestamp FROM messages WHERE user_id=%s ORDER BY timestamp", (user_id,))
        rows = cur.fetchall()
        data["messages"] = [dict(r) for r in rows]

        cur.execute("SELECT character_id, summary, topics, message_count, created_at FROM conversation_memory WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["memories"] = [dict(r) for r in rows]

        cur.execute("SELECT memory_data, updated_at FROM user_memory WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["user_memory"] = {"memory": json.loads(row["memory_data"]) if row else {}, "updated_at": row["updated_at"] if row else None}

        cur.execute("SELECT id, name, age, role, description, created_at FROM user_characters WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["characters"] = [dict(r) for r in rows]

        cur.execute("SELECT is_premium, sku, activated_at, expires_at FROM premium_users WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["premium"] = dict(row) if row else None

        cur.execute("SELECT character_id, current_stage, total_messages, updated_at FROM character_evolution WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["evolution"] = [dict(r) for r in rows]

        cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["preferences"] = dict(row) if row else None

        cur.execute("SELECT balance, total_earned, updated_at FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        data["mevacoins"] = dict(row) if row else {"balance": 0, "total_earned": 0, "updated_at": None}

        cur.execute("SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=%s ORDER BY created_at", (user_id,))
        rows = cur.fetchall()
        data["mevacoins_transactions"] = [dict(r) for r in rows]

        cur.execute("SELECT checkin_date, redeemed FROM daily_checkins WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["daily_checkins"] = [dict(r) for r in rows]

        cur.execute("SELECT day_number, claimed FROM new_user_bonus WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
        data["new_user_bonus"] = [dict(r) for r in rows]

        data["exported_at"] = datetime.now(timezone.utc).isoformat()
        return data
    finally:
        put_conn(conn)


def delete_user(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM relationships WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM conversation_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM personality_shifts WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_memory WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_characters WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM premium_users WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM character_evolution WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM user_preferences WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM mevacoins WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM mevacoins_transactions WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM daily_checkins WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM new_user_bonus WHERE user_id=%s", (user_id,))
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        cur.execute("DELETE FROM audit_log WHERE user_id=%s", (user_id,))
        conn.commit()
    finally:
        put_conn(conn)


def flag_user(user_id, reason, content_type="", content_snippet="", severity="medium", flagged_by="system"):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO moderation_flags (user_id, flagged_by, reason, content_type, content_snippet, severity) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, flagged_by, reason, content_type, content_snippet[:200], severity)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_moderation_flags(resolved=False, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if resolved:
            cur.execute(
                "SELECT * FROM moderation_flags ORDER BY created_at DESC LIMIT %s", (limit,)
            )
        else:
            cur.execute(
                "SELECT * FROM moderation_flags WHERE resolved_at IS NULL ORDER BY created_at DESC LIMIT %s", (limit,)
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def resolve_moderation_flag(flag_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE moderation_flags SET resolved_at = CURRENT_TIMESTAMP WHERE id = %s", (flag_id,)
        )
        conn.commit()
    finally:
        put_conn(conn)


def get_flag_count(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM moderation_flags WHERE user_id = %s AND resolved_at IS NULL",
            (user_id,)
        )
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)


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
            return {
                "gender_interest": gender_interest,
                "age_range": row["age_range"],
                "interest_tags": json.loads(row["interest_tags"] or "[]"),
                "show_adult": bool(row["show_adult"]),
                "user_gender": user_gender,
                "user_age": user_age,
                "sexual_orientation": orientation,
            }
        return {"gender_interest": "", "age_range": "", "interest_tags": [], "show_adult": False, "user_gender": "", "user_age": 0, "sexual_orientation": ""}
    finally:
        put_conn(conn)


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


def get_mevacoins_balance(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["balance"] if row else 0
    finally:
        put_conn(conn)


def add_mevacoins(user_id, amount, reason):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mevacoins (user_id, balance, total_earned, updated_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "balance = mevacoins.balance + EXCLUDED.balance, "
            "total_earned = mevacoins.total_earned + EXCLUDED.total_earned, "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id, amount, amount)
        )
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, amount, reason)
        )
        cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        conn.commit()
        return row["balance"] if row else amount
    finally:
        put_conn(conn)


def spend_mevacoins(user_id, amount, reason):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE mevacoins SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s AND balance >= %s", (amount, user_id, amount))
        if cur.rowcount == 0:
            return False
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, -amount, reason)
        )
        conn.commit()
        return True
    finally:
        put_conn(conn)


def get_mevacoins_transactions(user_id, limit=20):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def daily_checkin(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM daily_checkins WHERE user_id=%s AND checkin_date=%s",
            (user_id, today)
        )
        row = cur.fetchone()
        if row:
            return {"already_checked": True, "redeemed": bool(row["redeemed"])}
        cur.execute(
            "INSERT INTO daily_checkins (user_id, checkin_date) VALUES (%s, %s)",
            (user_id, today)
        )
        conn.commit()
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


def get_new_user_bonus(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT day_number, claimed FROM new_user_bonus WHERE user_id=%s ORDER BY day_number",
            (user_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []
    finally:
        put_conn(conn)


def claim_new_user_bonus(user_id, day_number):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT claimed FROM new_user_bonus WHERE user_id=%s AND day_number=%s",
            (user_id, day_number)
        )
        row = cur.fetchone()
        if not row or row["claimed"]:
            return False
        cur.execute(
            "UPDATE new_user_bonus SET claimed=1 WHERE user_id=%s AND day_number=%s",
            (user_id, day_number)
        )
        conn.commit()
    finally:
        put_conn(conn)
    add_mevacoins(user_id, 30, f"bonus_nuovo_utente_giorno_{day_number}")
    return True


def init_new_user_bonus(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM new_user_bonus WHERE user_id=%s", (user_id,)
        )
        existing = cur.fetchone()[0]
        if existing == 0:
            for day in range(1, 5):
                cur.execute(
                    "INSERT INTO new_user_bonus (user_id, day_number, claimed) VALUES (%s, %s, 0)",
                    (user_id, day)
                )
        conn.commit()
    finally:
        put_conn(conn)


def unlock_content(user_id, content_type, content_id, amount):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE mevacoins SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s AND balance >= %s", (amount, user_id, amount))
        if cur.rowcount == 0:
            return False, "saldo_insufficiente"
        cur.execute(
            "INSERT INTO content_unlocks (user_id, content_type, content_id, spent_amount) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (user_id, content_type, content_id, amount)
        )
        cur.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (%s, %s, %s)",
            (user_id, -amount, f"unlock:{content_type}:{content_id}")
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        put_conn(conn)


def is_content_unlocked(user_id, content_type, content_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM content_unlocks WHERE user_id=%s AND content_type=%s AND content_id=%s",
            (user_id, content_type, content_id)
        )
        row = cur.fetchone()
        return row is not None
    finally:
        put_conn(conn)


def get_user_unlocks(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT content_type, content_id, spent_amount FROM content_unlocks WHERE user_id=%s",
            (user_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


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
        cur.execute(
            "SELECT 1 FROM referral_earnings WHERE referred_id=%s AND bonus_type='signup'",
            (user_id,)
        )
        already = cur.fetchone()
        if already:
            return False, "gia_utilizzato"
        cur.execute("BEGIN")
        add_mevacoins(referrer_id, 100, f"referral_signup:{user_id}")
        add_mevacoins(user_id, 50, "referral_bonus")
        cur.execute(
            "INSERT INTO referral_earnings (referrer_id, referred_id, bonus_type, amount) VALUES (%s, %s, 'signup', 100)",
            (referrer_id, user_id)
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
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
            cur.execute("BEGIN")
            add_mevacoins(referrer_id, 100, f"referral_first_message:{user_id}")
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
            "SELECT COUNT(*) FROM social_shares WHERE user_id=%s AND share_date=%s", (user_id, today)
        )
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        put_conn(conn)


def add_social_share(user_id, platform=""):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = get_daily_share_count(user_id)
    if count >= 3:
        return False, "limite_giornaliero"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO social_shares (user_id, share_date, platform) VALUES (%s, %s, %s)",
            (user_id, today, platform)
        )
        conn.commit()
    finally:
        put_conn(conn)
    add_mevacoins(user_id, 30, f"social_share:{today}")
    return True, "ok"


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


# ── Character Demographics ──────────────────────────────────────────────

def get_character_demographics(character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM character_demographics WHERE character_id=%s", (character_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        put_conn(conn)


def update_character_demographics(character_id, **kwargs):
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
            except:
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


# ── Time Events ──────────────────────────────────────────────────────

def add_time_event(event_type, character_id=None, user_id=None, data=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO time_events (event_type, character_id, user_id, data) VALUES (%s, %s, %s, %s)",
                     (event_type, character_id, user_id, json.dumps(data or {})))
        conn.commit()
    finally:
        put_conn(conn)


def get_time_events(event_type=None, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if event_type:
            cur.execute("SELECT * FROM time_events WHERE event_type=%s ORDER BY created_at DESC LIMIT %s",
                                (event_type, limit))
        else:
            cur.execute("SELECT * FROM time_events ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d.get("data", "{}"))
            result.append(d)
        return result
    finally:
        put_conn(conn)
