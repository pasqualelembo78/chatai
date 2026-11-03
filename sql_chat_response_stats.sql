-- Tempi di risposta per chat (utente + personaggio) — tabella della barra di caricamento.
-- Va eseguita su un DB nuovo PRIMA di usare il plugin: senza tabella la media
-- ricade sul default (5000 ms) e le misurazioni non vengono registrate.
CREATE TABLE IF NOT EXISTS chat_response_stats (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
    character_id VARCHAR(64) NOT NULL DEFAULT '',
    response_time_ms INT UNSIGNED NOT NULL DEFAULT 0,
    message_text TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY user_char_created (user_id, character_id, created_at),
    KEY char_created (character_id, created_at),
    KEY created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
