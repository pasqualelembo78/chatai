#!/usr/bin/env python3
"""Pruning automatico: elimina i dati utente più vecchi di N giorni.

Replica la logica di storage.pruning.prune_old_data ma senza importare
l'intero backend (più leggero per il cron). Legge DATABASE_URL da env
o da .env nella directory dello script.
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prune_cron")

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
DEFAULT_RETENTION_DAYS = 90


def load_database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    raise RuntimeError("DATABASE_URL non trovato")


def main():
    import psycopg2

    retention = int(os.environ.get("PRUNE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
    url = load_database_url()

    conn = psycopg2.connect(url, connect_timeout=15)
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM messages WHERE timestamp < NOW() - INTERVAL '%s days'",
            (retention,),
        )
        deleted_messages = cur.rowcount
        cur.execute(
            "DELETE FROM conversation_memory WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention,),
        )
        deleted_memories = cur.rowcount
        cur.execute(
            "DELETE FROM personality_shifts WHERE created_at < NOW() - INTERVAL '%s days'",
            (retention,),
        )
        deleted_shifts = cur.rowcount
        cur.execute("DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '365 days'")
        deleted_audit = cur.rowcount
        conn.commit()
        logger.info(
            "Prune completato (retention=%sgg): messages=%s memories=%s shifts=%s audit=%s",
            retention, deleted_messages, deleted_memories, deleted_shifts, deleted_audit,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Prune fallito: %s", e)
        sys.exit(1)
