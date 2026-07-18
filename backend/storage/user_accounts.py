import json
import time
from db import get_conn, put_conn
from storage.crypto import encrypt_value


def create_user_character(user_id, data):
    # I personaggi adult/NSFW non sono persistibili: l'app per quel tipo di
    # contenuti è disponibile solo su www.mevacoin.com/aria-adult.apk. Qualsiasi
    # flag is_adult proveniente dal client viene ignorato e forzato a False.
    data = dict(data)
    data["is_adult"] = False
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


def user_exists(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE id=%s", (user_id,))
        return cur.fetchone() is not None
    finally:
        put_conn(conn)


def update_user_role(user_id, role):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET role=%s WHERE id=%s", (role, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def block_user(blocker_id, blocked_id):
    if blocker_id == blocked_id:
        return False
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO blocked_users (blocker_id, blocked_id) VALUES (%s, %s) "
            "ON CONFLICT (blocker_id, blocked_id) DO NOTHING",
            (blocker_id, blocked_id)
        )
        conn.commit()
        return True
    finally:
        put_conn(conn)


def unblock_user(blocker_id, blocked_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM blocked_users WHERE blocker_id=%s AND blocked_id=%s",
            (blocker_id, blocked_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def get_blocked_users(blocker_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT blocked_id FROM blocked_users WHERE blocker_id=%s", (blocker_id,))
        return [r["blocked_id"] for r in cur.fetchall()]
    finally:
        put_conn(conn)


def is_blocked(blocker_id, blocked_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM blocked_users WHERE blocker_id=%s AND blocked_id=%s",
            (blocker_id, blocked_id)
        )
        return cur.fetchone() is not None
    finally:
        put_conn(conn)
