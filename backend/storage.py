import sqlite3
import json
import os
import base64
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "roleplay_data.db")

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


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
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
        );

        CREATE TABLE IF NOT EXISTS personality (
            character_id TEXT PRIMARY KEY,
            warmth REAL DEFAULT 5,
            strictness REAL DEFAULT 5,
            patience REAL DEFAULT 5,
            sarcasm REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS world_state (
            id INTEGER PRIMARY KEY DEFAULT 1,
            scene TEXT DEFAULT 'default',
            events TEXT DEFAULT '[]',
            flags TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            topics TEXT DEFAULT '[]',
            message_count INTEGER DEFAULT 0,
            relationship_snapshot TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS personality_shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            pressure_type TEXT,
            pressure_level REAL,
            deltas TEXT DEFAULT '{}',
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT PRIMARY KEY,
            memory_data TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        INSERT OR IGNORE INTO world_state (id, scene, events, flags)
        VALUES (1, 'default', '[]', '{}');

        CREATE TABLE IF NOT EXISTS premium_users (
            user_id TEXT PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            sku TEXT DEFAULT '',
            purchase_token TEXT DEFAULT '',
            activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS character_evolution (
            user_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            current_stage TEXT DEFAULT 'base',
            unlocked_stages TEXT DEFAULT '["base"]',
            flags TEXT DEFAULT '{}',
            trait_modifiers TEXT DEFAULT '{}',
            intimacy_peak REAL DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, character_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            ip TEXT DEFAULT '',
            user_agent TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS moderation_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            flagged_by TEXT NOT NULL DEFAULT 'system',
            reason TEXT NOT NULL,
            content_type TEXT DEFAULT '',
            content_snippet TEXT DEFAULT '',
            severity TEXT DEFAULT 'medium',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            gender_interest TEXT DEFAULT '',
            age_range TEXT DEFAULT '',
            interest_tags TEXT DEFAULT '[]',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mevacoins (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mevacoins_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_checkins (
            user_id TEXT NOT NULL,
            checkin_date TEXT NOT NULL,
            redeemed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, checkin_date)
        );

        CREATE TABLE IF NOT EXISTS new_user_bonus (
            user_id TEXT NOT NULL,
            day_number INTEGER NOT NULL,
            claimed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, day_number)
        );

        CREATE TABLE IF NOT EXISTS content_unlocks (
            user_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_id TEXT NOT NULL,
            spent_amount INTEGER NOT NULL,
            unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, content_type, content_id)
        );

        CREATE TABLE IF NOT EXISTS referral_codes (
            user_id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS referral_earnings (
            referrer_id TEXT NOT NULL,
            referred_id TEXT NOT NULL,
            bonus_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (referrer_id, referred_id, bonus_type)
        );

        CREATE TABLE IF NOT EXISTS social_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            share_date TEXT NOT NULL,
            platform TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS streak_milestones (
            user_id TEXT NOT NULL,
            milestone INTEGER NOT NULL,
            claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, milestone)
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    """)
    # Migrazione: aggiungi colonna show_adult a user_preferences
    try:
        conn.execute("ALTER TABLE user_preferences ADD COLUMN show_adult INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Colonna già esistente
    try:
        conn.execute("ALTER TABLE relationships ADD COLUMN intimacy REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE relationships ADD COLUMN pressure_level REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE user_preferences ADD COLUMN user_gender TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE user_preferences ADD COLUMN user_age INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_relationship(user_id, character_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT trust, affinity, respect, conflict, intimacy, pressure_level FROM relationships WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"trust": 0, "affinity": 0, "respect": 0, "conflict": 0, "intimacy": 0, "pressure_level": 0}


def update_relationship(user_id, character_id, deltas):
    conn = get_conn()
    current = get_relationship(user_id, character_id)
    for k, v in deltas.items():
        current[k] = max(0, min(100, current.get(k, 0) + v))
    conn.execute(
        """INSERT OR REPLACE INTO relationships
           (user_id, character_id, trust, affinity, respect, conflict, intimacy, pressure_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, character_id, current["trust"], current["affinity"],
         current["respect"], current["conflict"],
         current.get("intimacy", 0), current.get("pressure_level", 0))
    )
    conn.commit()
    conn.close()
    return current


def update_intimacy(user_id, character_id, delta, intimacy_config):
    conn = get_conn()
    current = get_relationship(user_id, character_id)
    intimacy = current.get("intimacy", 0)
    intimacy = max(0, min(100, intimacy + delta))
    current["intimacy"] = intimacy
    conn.execute(
        "UPDATE relationships SET intimacy=? WHERE user_id=? AND character_id=?",
        (intimacy, user_id, character_id)
    )
    conn.commit()
    conn.close()
    return current


def update_pressure_level(user_id, character_id, pressure_level):
    conn = get_conn()
    conn.execute(
        "UPDATE relationships SET pressure_level=? WHERE user_id=? AND character_id=?",
        (pressure_level, user_id, character_id)
    )
    conn.commit()
    conn.close()


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
    row = conn.execute(
        "SELECT warmth, strictness, patience, sarcasm FROM personality WHERE character_id=?",
        (character_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return defaults or {"warmth": 5, "strictness": 5, "patience": 5, "sarcasm": 0}


def update_personality(character_id, deltas, defaults=None):
    conn = get_conn()
    current = get_personality(character_id, defaults)
    for k, v in deltas.items():
        current[k] = max(0, min(10, current.get(k, 0) + v))
    conn.execute(
        """INSERT OR REPLACE INTO personality (character_id, warmth, strictness, patience, sarcasm)
           VALUES (?, ?, ?, ?, ?)""",
        (character_id, current["warmth"], current["strictness"], current["patience"], current["sarcasm"])
    )
    conn.commit()
    conn.close()
    return current


def record_personality_shift(user_id, character_id, pressure_type, pressure_level, deltas, description):
    conn = get_conn()
    conn.execute(
        """INSERT INTO personality_shifts
           (user_id, character_id, pressure_type, pressure_level, deltas, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, character_id, pressure_type, pressure_level, json.dumps(deltas), description)
    )
    conn.commit()
    conn.close()


def get_recent_shifts(user_id, character_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        """SELECT pressure_type, pressure_level, deltas, description, created_at
           FROM personality_shifts
           WHERE user_id=? AND character_id=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, character_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


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
    row = conn.execute("SELECT scene, events, flags FROM world_state WHERE id=1").fetchone()
    conn.close()
    if row:
        return {
            "scene": row["scene"],
            "events": json.loads(row["events"]),
            "flags": json.loads(row["flags"])
        }
    return {"scene": "default", "events": [], "flags": {}}


def save_world_state(state):
    conn = get_conn()
    conn.execute(
        "UPDATE world_state SET scene=?, events=?, flags=? WHERE id=1",
        (state["scene"], json.dumps(state["events"]), json.dumps(state["flags"]))
    )
    conn.commit()
    conn.close()


def add_message(user_id, character_id, role, content):
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (user_id, character_id, role, content) VALUES (?, ?, ?, ?)",
        (user_id, character_id, role, content)
    )
    conn.commit()
    conn.close()


def get_recent_messages(user_id, character_id, limit=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE user_id=? AND character_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, character_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def count_messages(user_id, character_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def count_all_user_messages(user_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM messages WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def add_memory(user_id, character_id, summary, topics, message_count, relationship_snapshot):
    conn = get_conn()
    conn.execute(
        """INSERT INTO conversation_memory
           (user_id, character_id, summary, topics, message_count, relationship_snapshot)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, character_id, summary, json.dumps(topics),
         message_count, json.dumps(relationship_snapshot))
    )
    conn.commit()
    conn.close()


def get_memories(user_id, character_id, limit=3):
    conn = get_conn()
    rows = conn.execute(
        """SELECT summary, topics, relationship_snapshot, created_at
           FROM conversation_memory
           WHERE user_id=? AND character_id=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, character_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_last_summary_checkpoint(user_id, character_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(message_count), 0) FROM conversation_memory WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_evolution(user_id, character_id):
    conn = get_conn()
    row = conn.execute(
        """SELECT current_stage, unlocked_stages, flags, trait_modifiers,
                  intimacy_peak, total_messages
           FROM character_evolution
           WHERE user_id=? AND character_id=?""",
        (user_id, character_id)
    ).fetchone()
    conn.close()
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


def update_evolution(user_id, character_id, evo):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO character_evolution
        (user_id, character_id, current_stage, unlocked_stages,
         flags, trait_modifiers, intimacy_peak, total_messages, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
    conn.close()


def get_user_memory(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT memory_data, updated_at FROM user_memory WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return {"memory": json.loads(row["memory_data"]), "updated_at": row["updated_at"]}
    return {"memory": {}, "updated_at": None}


def update_user_memory(user_id, new_facts):
    conn = get_conn()
    existing = get_user_memory(user_id)
    memory = existing["memory"]
    memory.update(new_facts)
    conn.execute(
        """INSERT OR REPLACE INTO user_memory (user_id, memory_data, created_at, updated_at)
           VALUES (?, ?, COALESCE((SELECT created_at FROM user_memory WHERE user_id=?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)""",
        (user_id, json.dumps(memory), user_id)
    )
    conn.commit()
    conn.close()
    return memory


def reset_user_memory(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM user_memory WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def reset_conversation(user_id, character_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM messages WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    )
    conn.execute(
        "DELETE FROM conversation_memory WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    )
    conn.execute(
        "DELETE FROM personality_shifts WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    )
    conn.execute(
        "DELETE FROM relationships WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    )
    conn.execute(
        "DELETE FROM personality WHERE character_id=?",
        (character_id,)
    )
    conn.execute(
        "DELETE FROM character_evolution WHERE user_id=? AND character_id=?",
        (user_id, character_id)
    )
    conn.commit()
    conn.close()


def reset_all_user_data(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM conversation_memory WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM personality_shifts WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM relationships WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_memory WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM character_evolution WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def create_user_character(user_id, data):
    char_id = data.get("id", "").strip().lower().replace(" ", "_")
    if not char_id:
        char_id = f"user_{user_id}_{int(time.time())}"
    conn = get_conn()
    conn.execute(
        """INSERT INTO user_characters
           (id, user_id, name, age, role, category, avatar, description, tags,
            is_adult, essence, personality, speaking_style, backstory, hobbies,
            system_prompt, core_traits, intimacy_config, refusal_style, evolution)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
    conn.close()
    return get_user_character(char_id)


def get_user_character(char_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user_characters WHERE id=?", (char_id,)).fetchone()
    conn.close()
    return _row_to_character(row) if row else None


def get_user_characters(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM user_characters WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [_row_to_character(r) for r in rows]


def get_all_user_characters():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM user_characters ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_character(r) for r in rows]


def delete_user_character(char_id):
    conn = get_conn()
    conn.execute("DELETE FROM user_characters WHERE id=?", (char_id,))
    conn.commit()
    conn.close()


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
    row = conn.execute(
        "SELECT is_premium FROM premium_users WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    return bool(row and row["is_premium"])


def set_user_premium(user_id, premium=True, sku="", purchase_token=""):
    conn = get_conn()
    encrypted_token = encrypt_value(purchase_token)
    conn.execute(
        """INSERT OR REPLACE INTO premium_users
           (user_id, is_premium, sku, purchase_token, activated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (user_id, 1 if premium else 0, sku, encrypted_token)
    )
    conn.commit()
    conn.close()


def audit_log(user_id, action, detail="", ip="", user_agent=""):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO audit_log (user_id, action, detail, ip, user_agent) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, detail[:500], ip[:50], user_agent[:200])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"audit_log failed: {e}")


def prune_old_data(retention_days=DEFAULT_RETENTION_DAYS):
    conn = get_conn()
    cutoff = datetime.now(timezone.utc).isoformat()
    deleted_messages = conn.execute(
        "DELETE FROM messages WHERE timestamp < datetime('now', ?)",
        (f"-{retention_days} days",)
    ).rowcount
    deleted_memories = conn.execute(
        "DELETE FROM conversation_memory WHERE created_at < datetime('now', ?)",
        (f"-{retention_days} days",)
    ).rowcount
    deleted_shifts = conn.execute(
        "DELETE FROM personality_shifts WHERE created_at < datetime('now', ?)",
        (f"-{retention_days} days",)
    ).rowcount
    deleted_audit = conn.execute(
        "DELETE FROM audit_log WHERE timestamp < datetime('now', ?)",
        ("-365 days",)
    ).rowcount
    conn.commit()
    conn.close()
    return {
        "messages": deleted_messages,
        "memories": deleted_memories,
        "shifts": deleted_shifts,
        "audit_logs": deleted_audit,
    }


def get_all_users():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, email, google_id, banned_until, created_at, last_login FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ban_user(user_id, duration_hours=0):
    conn = get_conn()
    if duration_hours > 0:
        from datetime import timedelta
        ban_until = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
        conn.execute("UPDATE users SET banned_until = ? WHERE id = ?", (ban_until, user_id))
    else:
        conn.execute("UPDATE users SET banned_until = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def export_user_data(user_id):
    conn = get_conn()
    data = {}

    user = conn.execute("SELECT id, username, role, email, google_id, created_at, last_login FROM users WHERE id=?", (user_id,)).fetchone()
    data["profile"] = dict(user) if user else None

    rows = conn.execute("SELECT character_id, trust, affinity, respect, conflict, intimacy, pressure_level FROM relationships WHERE user_id=?", (user_id,)).fetchall()
    data["relationships"] = [dict(r) for r in rows]

    rows = conn.execute("SELECT character_id, role, content, timestamp FROM messages WHERE user_id=? ORDER BY timestamp", (user_id,)).fetchall()
    data["messages"] = [dict(r) for r in rows]

    rows = conn.execute("SELECT character_id, summary, topics, message_count, created_at FROM conversation_memory WHERE user_id=?", (user_id,)).fetchall()
    data["memories"] = [dict(r) for r in rows]

    row = conn.execute("SELECT memory_data, updated_at FROM user_memory WHERE user_id=?", (user_id,)).fetchone()
    data["user_memory"] = {"memory": json.loads(row["memory_data"]) if row else {}, "updated_at": row["updated_at"] if row else None}

    rows = conn.execute("SELECT id, name, age, role, description, created_at FROM user_characters WHERE user_id=?", (user_id,)).fetchall()
    data["characters"] = [dict(r) for r in rows]

    row = conn.execute("SELECT is_premium, sku, activated_at, expires_at FROM premium_users WHERE user_id=?", (user_id,)).fetchone()
    data["premium"] = dict(row) if row else None

    rows = conn.execute("SELECT character_id, current_stage, total_messages, updated_at FROM character_evolution WHERE user_id=?", (user_id,)).fetchall()
    data["evolution"] = [dict(r) for r in rows]

    row = conn.execute("SELECT * FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    data["preferences"] = dict(row) if row else None

    row = conn.execute("SELECT balance, total_earned, updated_at FROM mevacoins WHERE user_id=?", (user_id,)).fetchone()
    data["mevacoins"] = dict(row) if row else {"balance": 0, "total_earned": 0, "updated_at": None}

    rows = conn.execute("SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=? ORDER BY created_at", (user_id,)).fetchall()
    data["mevacoins_transactions"] = [dict(r) for r in rows]

    rows = conn.execute("SELECT checkin_date, redeemed FROM daily_checkins WHERE user_id=?", (user_id,)).fetchall()
    data["daily_checkins"] = [dict(r) for r in rows]

    rows = conn.execute("SELECT day_number, claimed FROM new_user_bonus WHERE user_id=?", (user_id,)).fetchall()
    data["new_user_bonus"] = [dict(r) for r in rows]

    data["exported_at"] = datetime.now(timezone.utc).isoformat()
    conn.close()
    return data


def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM relationships WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM conversation_memory WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM personality_shifts WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_memory WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_characters WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM premium_users WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM character_evolution WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM user_preferences WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM mevacoins WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM mevacoins_transactions WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM daily_checkins WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM new_user_bonus WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.execute("DELETE FROM audit_log WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def flag_user(user_id, reason, content_type="", content_snippet="", severity="medium", flagged_by="system"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO moderation_flags (user_id, flagged_by, reason, content_type, content_snippet, severity) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, flagged_by, reason, content_type, content_snippet[:200], severity)
    )
    conn.commit()
    conn.close()


def get_moderation_flags(resolved=False, limit=50):
    conn = get_conn()
    if resolved:
        rows = conn.execute(
            "SELECT * FROM moderation_flags ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM moderation_flags WHERE resolved_at IS NULL ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_moderation_flag(flag_id):
    conn = get_conn()
    conn.execute(
        "UPDATE moderation_flags SET resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (flag_id,)
    )
    conn.commit()
    conn.close()


def get_flag_count(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM moderation_flags WHERE user_id = ? AND resolved_at IS NULL",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_user_preferences(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        user_gender = row["user_gender"] if "user_gender" in row.keys() else ""
        user_age = row["user_age"] if "user_age" in row.keys() else 0
        gender_interest = row["gender_interest"]
        orientation = derive_sexual_orientation(user_gender, gender_interest)
        return {
            "gender_interest": gender_interest,
            "age_range": row["age_range"],
            "interest_tags": json.loads(row["interest_tags"] or "[]"),
            "show_adult": bool(row["show_adult"]) if "show_adult" in row.keys() else False,
            "user_gender": user_gender,
            "user_age": user_age,
            "sexual_orientation": orientation,
        }
    return {"gender_interest": "", "age_range": "", "interest_tags": [], "show_adult": False, "user_gender": "", "user_age": 0, "sexual_orientation": ""}


def save_user_preferences(user_id, data):
    conn = get_conn()
    interests = data.get("interest_tags") or data.get("interests", [])
    conn.execute(
        """INSERT OR REPLACE INTO user_preferences
           (user_id, gender_interest, age_range, interest_tags, show_adult, user_gender, user_age, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (user_id,
         data.get("gender_interest", ""),
         data.get("age_range", ""),
         json.dumps(interests),
         1 if data.get("show_adult") else 0,
         data.get("user_gender", ""),
         data.get("user_age", 0))
    )
    conn.commit()
    conn.close()


def derive_sexual_orientation(user_gender, gender_interest):
    """
    Deriva l'orientamento sessuale dal genere dell'utente e dal genere cercato.
    Restituisce una stringa descrittiva.

    Esempi:
    - female + femminile = lesbica
    - male + maschile = gay
    - female + maschile = etero
    - male + femminile = etero
    - non-binary + * = bisessuale/pansessuale
    """
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
    row = conn.execute("SELECT balance FROM mevacoins WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["balance"] if row else 0


def add_mevacoins(user_id, amount, reason):
    conn = get_conn()
    conn.execute(
        "INSERT INTO mevacoins (user_id, balance, total_earned, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "balance = balance + ?, total_earned = total_earned + ?, updated_at = CURRENT_TIMESTAMP",
        (user_id, amount, amount, amount, amount)
    )
    conn.execute(
        "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
        (user_id, amount, reason)
    )
    row = conn.execute("SELECT balance FROM mevacoins WHERE user_id=?", (user_id,)).fetchone()
    conn.commit()
    conn.close()
    return row["balance"] if row else amount


def spend_mevacoins(user_id, amount, reason):
    conn = get_conn()
    conn.execute("UPDATE mevacoins SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND balance >= ?", (amount, user_id, amount))
    if conn.total_changes == 0:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
        (user_id, -amount, reason)
    )
    conn.commit()
    conn.close()
    return True


def get_mevacoins_transactions(user_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT amount, reason, created_at FROM mevacoins_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def daily_checkin(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? AND checkin_date=?",
        (user_id, today)
    ).fetchone()
    if row:
        conn.close()
        return {"already_checked": True, "redeemed": bool(row["redeemed"])}
    conn.execute(
        "INSERT INTO daily_checkins (user_id, checkin_date) VALUES (?, ?)",
        (user_id, today)
    )
    conn.commit()
    conn.close()
    add_mevacoins(user_id, 15, "checkin_giornaliero")
    return {"already_checked": False, "earned": 15}


def redeem_daily_checkin(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? AND checkin_date=? AND redeemed=0",
        (user_id, today)
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute(
        "UPDATE daily_checkins SET redeemed=1 WHERE user_id=? AND checkin_date=?",
        (user_id, today)
    )
    conn.commit()
    conn.close()
    return True


def get_new_user_bonus(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT day_number, claimed FROM new_user_bonus WHERE user_id=? ORDER BY day_number",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows] if rows else []


def claim_new_user_bonus(user_id, day_number):
    conn = get_conn()
    row = conn.execute(
        "SELECT claimed FROM new_user_bonus WHERE user_id=? AND day_number=?",
        (user_id, day_number)
    ).fetchone()
    if not row or row["claimed"]:
        conn.close()
        return False
    conn.execute(
        "UPDATE new_user_bonus SET claimed=1 WHERE user_id=? AND day_number=?",
        (user_id, day_number)
    )
    conn.commit()
    conn.close()
    add_mevacoins(user_id, 30, f"bonus_nuovo_utente_giorno_{day_number}")
    return True


def init_new_user_bonus(user_id):
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) FROM new_user_bonus WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    if existing == 0:
        for day in range(1, 5):
            conn.execute(
                "INSERT INTO new_user_bonus (user_id, day_number, claimed) VALUES (?, ?, 0)",
                (user_id, day)
            )
    conn.commit()
    conn.close()


def unlock_content(user_id, content_type, content_id, amount):
    conn = get_conn()
    try:
        conn.execute("UPDATE mevacoins SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND balance >= ?", (amount, user_id, amount))
        if conn.total_changes == 0:
            conn.close()
            return False, "saldo_insufficiente"
        conn.execute(
            "INSERT OR IGNORE INTO content_unlocks (user_id, content_type, content_id, spent_amount) VALUES (?, ?, ?, ?)",
            (user_id, content_type, content_id, amount)
        )
        conn.execute(
            "INSERT INTO mevacoins_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, -amount, f"unlock:{content_type}:{content_id}")
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def is_content_unlocked(user_id, content_type, content_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM content_unlocks WHERE user_id=? AND content_type=? AND content_id=?",
        (user_id, content_type, content_id)
    ).fetchone()
    conn.close()
    return row is not None


def get_user_unlocks(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT content_type, content_id, spent_amount FROM content_unlocks WHERE user_id=?",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_or_create_referral_code(user_id):
    conn = get_conn()
    row = conn.execute("SELECT code FROM referral_codes WHERE user_id=?", (user_id,)).fetchone()
    if row:
        conn.close()
        return row["code"]
    import random, string
    for _ in range(10):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        try:
            conn.execute("INSERT INTO referral_codes (user_id, code) VALUES (?, ?)", (user_id, code))
            conn.commit()
            conn.close()
            return code
        except sqlite3.IntegrityError:
            continue
    conn.close()
    return None


def get_referrer_by_code(code):
    conn = get_conn()
    row = conn.execute("SELECT user_id FROM referral_codes WHERE code=?", (code,)).fetchone()
    conn.close()
    return row["user_id"] if row else None


def claim_referral_bonus(user_id, code):
    referrer_id = get_referrer_by_code(code)
    if not referrer_id or referrer_id == user_id:
        return False, "codice_non_valido"
    conn = get_conn()
    already = conn.execute(
        "SELECT 1 FROM referral_earnings WHERE referred_id=? AND bonus_type='signup'",
        (user_id,)
    ).fetchone()
    if already:
        conn.close()
        return False, "gia_utilizzato"
    try:
        conn.execute("BEGIN IMMEDIATE")
        add_mevacoins(referrer_id, 100, f"referral_signup:{user_id}")
        add_mevacoins(user_id, 50, "referral_bonus")
        conn.execute(
            "INSERT INTO referral_earnings (referrer_id, referred_id, bonus_type, amount) VALUES (?, ?, 'signup', 100)",
            (referrer_id, user_id)
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)


def credit_referral_first_message(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT referrer_id FROM referral_earnings WHERE referred_id=? AND bonus_type='signup'",
        (user_id,)
    ).fetchone()
    if not row:
        conn.close()
        return
    referrer_id = row["referrer_id"]
    already = conn.execute(
        "SELECT 1 FROM referral_earnings WHERE referrer_id=? AND referred_id=? AND bonus_type='first_message'",
        (referrer_id, user_id)
    ).fetchone()
    if already:
        conn.close()
        return
    try:
        conn.execute("BEGIN IMMEDIATE")
        add_mevacoins(referrer_id, 100, f"referral_first_message:{user_id}")
        conn.execute(
            "INSERT INTO referral_earnings (referrer_id, referred_id, bonus_type, amount) VALUES (?, ?, 'first_message', 100)",
            (referrer_id, user_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def get_daily_share_count(user_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM social_shares WHERE user_id=? AND share_date=?", (user_id, today)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def add_social_share(user_id, platform=""):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = get_daily_share_count(user_id)
    if count >= 3:
        return False, "limite_giornaliero"
    conn = get_conn()
    conn.execute(
        "INSERT INTO social_shares (user_id, share_date, platform) VALUES (?, ?, ?)",
        (user_id, today, platform)
    )
    conn.commit()
    conn.close()
    add_mevacoins(user_id, 30, f"social_share:{today}")
    return True, "ok"


def get_checkin_streak(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT checkin_date FROM daily_checkins WHERE user_id=? ORDER BY checkin_date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
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


def claim_streak_milestone(user_id, milestone):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO streak_milestones (user_id, milestone) VALUES (?, ?)",
            (user_id, milestone)
        )
        conn.commit()
        return conn.total_changes > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


import time
