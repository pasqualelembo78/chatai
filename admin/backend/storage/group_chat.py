from db import get_conn, put_conn

# ═══════════════════════════════════════════════════════════════════
# GROUP CHATS
# ═══════════════════════════════════════════════════════════════════

def init_group_chat_tables():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chats (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_characters (
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                character_id TEXT NOT NULL,
                PRIMARY KEY (group_chat_id, character_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_messages (
                id SERIAL PRIMARY KEY,
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                sender_type TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_participants (
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_chat_id, user_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_chat_invitations (
                id SERIAL PRIMARY KEY,
                group_chat_id INTEGER NOT NULL REFERENCES group_chats(id) ON DELETE CASCADE,
                inviter_id TEXT NOT NULL,
                invitee_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                UNIQUE(group_chat_id, invitee_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcm_chat ON group_chat_messages(group_chat_id, timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcc_chat ON group_chat_characters(group_chat_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gc_user ON group_chats(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcp_chat ON group_chat_participants(group_chat_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gcp_user ON group_chat_participants(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gci_invitee ON group_chat_invitations(invitee_id, status)")
        conn.commit()
    finally:
        put_conn(conn)


def create_group_chat(user_id, name, character_ids):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO group_chats (user_id, name) VALUES (%s, %s) RETURNING id, created_at",
                    (user_id, name))
        row = cur.fetchone()
        chat_id = row["id"]
        created_at = row["created_at"]
        for cid in character_ids:
            cur.execute("INSERT INTO group_chat_characters (group_chat_id, character_id) VALUES (%s, %s)",
                        (chat_id, cid))
        conn.commit()
        return {"id": chat_id, "user_id": user_id, "name": name, "created_at": str(created_at),
                "character_ids": character_ids}
    finally:
        put_conn(conn)


def list_group_chats(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, created_at FROM group_chats WHERE user_id=%s ORDER BY created_at DESC",
                    (user_id,))
        chats = []
        for r in cur.fetchall():
            cur2 = conn.cursor()
            cur2.execute("SELECT character_id FROM group_chat_characters WHERE group_chat_id=%s", (r["id"],))
            chars = [row["character_id"] for row in cur2.fetchall()]
            cur2.execute("SELECT COUNT(*) as cnt FROM group_chat_messages WHERE group_chat_id=%s", (r["id"],))
            msg_count = cur2.fetchone()["cnt"]
            chats.append({"id": r["id"], "name": r["name"], "created_at": str(r["created_at"]),
                          "character_ids": chars, "message_count": msg_count})
        return chats
    finally:
        put_conn(conn)


def get_group_chat(chat_id, user_id=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if user_id:
            cur.execute("SELECT id, user_id, name, created_at FROM group_chats WHERE id=%s AND user_id=%s",
                        (chat_id, user_id))
        else:
            cur.execute("SELECT id, user_id, name, created_at FROM group_chats WHERE id=%s", (chat_id,))
        r = cur.fetchone()
        if not r:
            return None
        cur.execute("SELECT character_id FROM group_chat_characters WHERE group_chat_id=%s", (chat_id,))
        chars = [row["character_id"] for row in cur.fetchall()]
        return {"id": r["id"], "user_id": r["user_id"], "name": r["name"],
                "created_at": str(r["created_at"]), "character_ids": chars}
    finally:
        put_conn(conn)


def delete_group_chat(chat_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM group_chats WHERE id=%s", (chat_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def add_group_character(chat_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO group_chat_characters (group_chat_id, character_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chat_id, character_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def remove_group_character(chat_id, character_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM group_chat_characters WHERE group_chat_id=%s AND character_id=%s",
            (chat_id, character_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def add_group_participant(chat_id, user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO group_chat_participants (group_chat_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (chat_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def remove_group_participant(chat_id, user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM group_chat_participants WHERE group_chat_id=%s AND user_id=%s",
            (chat_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        put_conn(conn)


def get_group_participants(chat_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, joined_at FROM group_chat_participants WHERE group_chat_id=%s ORDER BY joined_at",
            (chat_id,))
        return [{"user_id": row["user_id"], "joined_at": str(row["joined_at"])} for row in cur.fetchall()]
    finally:
        put_conn(conn)


def is_group_participant(chat_id, user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM group_chat_participants WHERE group_chat_id=%s AND user_id=%s",
            (chat_id, user_id))
        return cur.fetchone() is not None
    finally:
        put_conn(conn)


def create_group_invitation(chat_id, inviter_id, invitee_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO group_chat_invitations (group_chat_id, inviter_id, invitee_id, status) "
            "VALUES (%s, %s, %s, 'pending') ON CONFLICT (group_chat_id, invitee_id) "
            "DO UPDATE SET status='pending', responded_at=NULL, created_at=CURRENT_TIMESTAMP "
            "RETURNING id",
            (chat_id, inviter_id, invitee_id))
        row = cur.fetchone()
        conn.commit()
        return row["id"] if row else None
    finally:
        put_conn(conn)


def get_user_pending_invitations(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT gci.id, gci.group_chat_id, gci.inviter_id, gci.created_at, gc.name as chat_name
            FROM group_chat_invitations gci
            JOIN group_chats gc ON gci.group_chat_id = gc.id
            WHERE gci.invitee_id = %s AND gci.status = 'pending'
            ORDER BY gci.created_at DESC
        """, (user_id,))
        return [{"id": row["id"], "group_chat_id": row["group_chat_id"],
                 "inviter_id": row["inviter_id"], "chat_name": row["chat_name"],
                 "created_at": str(row["created_at"])} for row in cur.fetchall()]
    finally:
        put_conn(conn)


def respond_to_invitation(invitation_id, user_id, accept):
    conn = get_conn()
    try:
        cur = conn.cursor()
        status = "accepted" if accept else "declined"
        cur.execute(
            "UPDATE group_chat_invitations SET status=%s, responded_at=CURRENT_TIMESTAMP "
            "WHERE id=%s AND invitee_id=%s AND status='pending' "
            "RETURNING group_chat_id",
            (status, invitation_id, user_id))
        row = cur.fetchone()
        if not row:
            return None
        chat_id = row["group_chat_id"]
        if accept:
            cur.execute(
                "INSERT INTO group_chat_participants (group_chat_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (chat_id, user_id))
        conn.commit()
        return chat_id
    finally:
        put_conn(conn)


def get_invitation_status(chat_id, user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM group_chat_invitations WHERE group_chat_id=%s AND invitee_id=%s",
            (chat_id, user_id))
        row = cur.fetchone()
        return row["status"] if row else None
    finally:
        put_conn(conn)


def get_user_group_chats(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT gc.id, gc.name, gc.created_at 
            FROM group_chats gc
            JOIN group_chat_participants gcp ON gc.id = gcp.group_chat_id
            WHERE gcp.user_id = %s
            ORDER BY gc.created_at DESC
        """, (user_id,))
        chats = []
        for r in cur.fetchall():
            cur2 = conn.cursor()
            cur2.execute("SELECT character_id FROM group_chat_characters WHERE group_chat_id=%s", (r["id"],))
            chars = [row["character_id"] for row in cur2.fetchall()]
            cur2.execute("SELECT user_id FROM group_chat_participants WHERE group_chat_id=%s", (r["id"],))
            participants = [row["user_id"] for row in cur2.fetchall()]
            cur2.execute("SELECT COUNT(*) as cnt FROM group_chat_messages WHERE group_chat_id=%s", (r["id"],))
            msg_count = cur2.fetchone()["cnt"]
            chats.append({"id": r["id"], "name": r["name"], "created_at": str(r["created_at"]),
                          "character_ids": chars, "participants": participants, "message_count": msg_count})
        return chats
    finally:
        put_conn(conn)


def add_group_message(chat_id, sender_type, sender_id, role, content):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO group_chat_messages (group_chat_id, sender_type, sender_id, role, content) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id, timestamp",
            (chat_id, sender_type, sender_id, role, content))
        row = cur.fetchone()
        conn.commit()
        return {"id": row["id"], "group_chat_id": chat_id, "sender_type": sender_type,
                "sender_id": sender_id, "role": role, "content": content, "timestamp": str(row["timestamp"])}
    finally:
        put_conn(conn)


def get_group_messages(chat_id, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, sender_type, sender_id, role, content, timestamp "
            "FROM group_chat_messages WHERE group_chat_id=%s "
            "ORDER BY timestamp DESC LIMIT %s", (chat_id, limit))
        msgs = [{"id": r["id"], "sender_type": r["sender_type"], "sender_id": r["sender_id"],
                 "role": r["role"], "content": r["content"],
                 "timestamp": str(r["timestamp"])} for r in cur.fetchall()]
        msgs.reverse()
        return msgs
    finally:
        put_conn(conn)
