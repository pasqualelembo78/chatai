-- RIASSUNTI DELLE CONVERSAZIONI — database PostgreSQL del backend ARIA.
-- Da eseguire con: psql "$DATABASE_URL" -f sql_chat_summaries.sql
-- (NON è il database di WordPress: quello è MySQL e serve per chat_response_stats)

CREATE TABLE IF NOT EXISTS chat_summaries (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    character_id VARCHAR(255) NOT NULL,
    summary_text TEXT NOT NULL,
    message_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- serve all'ON CONFLICT di chat_summary.save_summary()
CREATE UNIQUE INDEX IF NOT EXISTS chat_summaries_user_char
    ON chat_summaries (user_id, character_id);

CREATE INDEX IF NOT EXISTS chat_summaries_updated ON chat_summaries (updated_at);
