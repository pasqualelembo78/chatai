-- MEMORIA GRANULARE PER PERSONAGGIO — database PostgreSQL del backend ARIA.
-- Da eseguire con: psql "$DATABASE_URL" -f sql_user_memory_items.sql
-- user_id è TEXT perché gli id utente di ARIA sono UUID, non numeri.

CREATE TABLE IF NOT EXISTS user_memory_items (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    character_id VARCHAR(255),
    memory_key VARCHAR(255) NOT NULL,
    memory_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, character_id, memory_key)
);

CREATE INDEX IF NOT EXISTS idx_user_mem_u_c ON user_memory_items (user_id, character_id);
