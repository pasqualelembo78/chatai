import logging
from db import get_conn, put_conn

logger = logging.getLogger(__name__)

_pgvector_available = None

def _check_pgvector():
    global _pgvector_available
    if _pgvector_available is not None:
        return _pgvector_available
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_extension WHERE extname='vector'")
            _pgvector_available = cur.fetchone() is not None
        finally:
            put_conn(conn)
    except Exception:
        _pgvector_available = False
    return _pgvector_available


def store_embedding(user_id, character_id, content, content_type="message", embedding=None):
    """Store a text embedding for semantic search."""
    if not _check_pgvector() or embedding is None:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Convert embedding to pgvector format
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        cur.execute("""
            INSERT INTO memory_embeddings (user_id, character_id, content, content_type, embedding)
            VALUES (%s, %s, %s, %s, %s::vector)
        """, (user_id, character_id, content, content_type, vec_str))
        conn.commit()
    finally:
        put_conn(conn)


def search_similar_memories(user_id, query_embedding, character_id=None, limit=5):
    """Search for semantically similar content using cosine similarity."""
    if not _check_pgvector() or query_embedding is None:
        return []
    vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    conn = get_conn()
    try:
        cur = conn.cursor()
        if character_id:
            cur.execute("""
                SELECT content, content_type, created_at,
                       1 - (embedding <=> %s::vector) as similarity
                FROM memory_embeddings
                WHERE user_id=%s AND character_id=%s
                ORDER BY embedding <=> %s::vector LIMIT %s
            """, (vec_str, user_id, character_id, vec_str, limit))
        else:
            cur.execute("""
                SELECT content, content_type, character_id, created_at,
                       1 - (embedding <=> %s::vector) as similarity
                FROM memory_embeddings
                WHERE user_id=%s
                ORDER BY embedding <=> %s::vector LIMIT %s
            """, (vec_str, user_id, vec_str, limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def get_embedding_count(user_id):
    """Count stored embeddings for a user."""
    if not _check_pgvector():
        return 0
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM memory_embeddings WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        put_conn(conn)
