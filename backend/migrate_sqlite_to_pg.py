#!/usr/bin/env python3
"""
Migrazione dati da SQLite a PostgreSQL.

Uso:
  1. Avviare PostgreSQL (docker-compose up -d postgres)
  2. Impostare DATABASE_URL (es. export DATABASE_URL=postgresql://chatai:chatai_secret@localhost:5432/chatai)
  3. Eseguire: python migrate_sqlite_to_pg.py [--dry-run]

Lo script:
  1. Crea le tabelle su PostgreSQL (init_db)
  2. Legge tutti i dati da SQLite
  3. Inserisce i dati in PostgreSQL
  4. Verifica i conteggi
"""

import os
import sys
import sqlite3
import json
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "roleplay_data.db")

# Ordine tabelle: prima quelle senza FK, poi quelle con FK
TABLES_ORDER = [
    "users",
    "world_state",
    "personality",
    "character_demographics",
    "character_birthdays",
    "user_preferences",
    "mevacoins",
    "premium_users",
    "user_memory",
    "user_characters",
    "relationships",
    "messages",
    "conversation_memory",
    "personality_shifts",
    "character_evolution",
    "audit_log",
    "moderation_flags",
    "mevacoins_transactions",
    "daily_checkins",
    "new_user_bonus",
    "content_unlocks",
    "referral_codes",
    "referral_earnings",
    "social_shares",
    "streak_milestones",
    "time_events",
    "refresh_tokens",
]


def get_sqlite_tables(sqlite_conn):
    cur = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
    )
    return [row[0] for row in cur.fetchall()]


def get_table_columns(sqlite_conn, table):
    cur = sqlite_conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def get_row_count(sqlite_conn, table):
    cur = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def migrate_table(sqlite_conn, pg_conn, table, dry_run=False):
    columns = get_table_columns(sqlite_conn, table)
    count = get_row_count(sqlite_conn, table)

    if count == 0:
        logger.info(f"  {table}: 0 righe, skip")
        return 0

    if dry_run:
        logger.info(f"  {table}: {count} righe (dry-run, skip)")
        return count

    sqlite_cur = sqlite_conn.execute(f"SELECT * FROM {table}")
    pg_cur = pg_conn.cursor()

    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    batch = []
    inserted = 0
    for row in sqlite_cur:
        values = []
        for val in row:
            if isinstance(val, str) and val.startswith("[") or isinstance(val, str) and val.startswith("{"):
                try:
                    json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            values.append(val)
        batch.append(tuple(values))

        if len(batch) >= 1000:
            pg_cur.executemany(insert_sql, batch)
            inserted += len(batch)
            batch = []

    if batch:
        pg_cur.executemany(insert_sql, batch)
        inserted += len(batch)

    pg_conn.commit()
    logger.info(f"  {table}: {inserted}/{count} righe migrated")
    return count


def main():
    parser = argparse.ArgumentParser(description="Migrazione SQLite -> PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa farebbe senza scrivere")
    parser.add_argument("--sqlite-path", default=SQLITE_PATH, help="Path al database SQLite")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_path):
        logger.error(f"SQLite non trovato: {args.sqlite_path}")
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url and not args.dry_run:
        logger.error("DATABASE_URL non impostata")
        sys.exit(1)

    logger.info(f"SQLite: {args.sqlite_path}")
    if not args.dry_run:
        logger.info(f"PostgreSQL: {database_url}")

    # Connessione SQLite
    sqlite_conn = sqlite3.connect(args.sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_tables = get_sqlite_tables(sqlite_conn)
    logger.info(f"Tabelle SQLite: {len(sqlite_tables)}")

    # Connessione PostgreSQL (solo se non dry-run)
    pg_conn = None
    if not args.dry_run:
        import psycopg2
        import psycopg2.extras
        pg_conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

        # Crea schema
        logger.info("Creazione schema PostgreSQL...")
        sys.path.insert(0, os.path.dirname(__file__))
        from db import init_pool, close_pool
        os.environ["DATABASE_URL"] = database_url
        init_pool()

        from storage import init_db
        init_db()
        from auth import init_auth_db
        init_auth_db()
        logger.info("Schema creato OK")

    # Migrazione
    logger.info("Inizio migrazione...")
    total_rows = 0
    migrated_tables = 0

    for table in TABLES_ORDER:
        if table not in sqlite_tables:
            continue
        count = migrate_table(sqlite_conn, pg_conn, table, dry_run=args.dry_run)
        total_rows += count
        if count > 0:
            migrated_tables += 1

    # Tabelle non nella lista (extra da SQLite)
    for table in sqlite_tables:
        if table not in TABLES_ORDER:
            count = migrate_table(sqlite_conn, pg_conn, table, dry_run=args.dry_run)
            total_rows += count
            if count > 0:
                migrated_tables += 1
            logger.warning(f"  Tabella non in lista: {table}")

    # Verifica
    if not args.dry_run:
        logger.info("\nReset serial sequences...")
        from db import get_conn, put_conn
        pg_conn2 = get_conn()
        try:
            pg_cur = pg_conn2.cursor()
            tables_with_serial = [
                ('messages', 'id'),
                ('conversation_memory', 'id'),
                ('personality_shifts', 'id'),
                ('audit_log', 'id'),
                ('moderation_flags', 'id'),
                ('mevacoins_transactions', 'id'),
                ('social_shares', 'id'),
                ('time_events', 'id'),
            ]
            for table, col in tables_with_serial:
                sql = f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), COALESCE((SELECT MAX({col}) FROM {table}), 1))"
                pg_cur.execute(sql)
                pg_cur.fetchone()
                logger.info(f"  {table}.{col}: sequence reset")
            pg_conn2.commit()
        finally:
            put_conn(pg_conn2)

        logger.info("\nVerifica conteggi PostgreSQL:")
        pg_conn2 = get_conn()
        try:
            pg_cur = pg_conn2.cursor()
            for table in TABLES_ORDER:
                try:
                    pg_cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                    pg_count = pg_cur.fetchone()["cnt"]
                    sqlite_count = get_row_count(sqlite_conn, table)
                    status = "OK" if pg_count == sqlite_count else "MISMATCH"
                    if pg_count != sqlite_count:
                        logger.warning(f"  {table}: SQLite={sqlite_count} PG={pg_count} [{status}]")
                    else:
                        logger.info(f"  {table}: {pg_count} righe [{status}]")
                except Exception as e:
                    logger.error(f"  {table}: errore verifica - {e}")
        finally:
            put_conn(pg_conn2)

    logger.info(f"\nRiepilogo: {migrated_tables} tabelle, {total_rows} righe totali")

    sqlite_conn.close()
    if pg_conn:
        pg_conn.close()

    if args.dry_run:
        logger.info("\nDry-run completato. Nessun dato scritto.")


if __name__ == "__main__":
    main()
