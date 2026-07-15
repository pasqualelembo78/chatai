#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/chatai}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

cd "$(dirname "$0")"

DB="roleplay_data.db"
ENV=".env"

if [ -f "$DB" ]; then
    cp "$DB" "$BACKUP_DIR/db_${TIMESTAMP}.db"
    gzip -f "$BACKUP_DIR/db_${TIMESTAMP}.db"
    echo "DB backup: $BACKUP_DIR/db_${TIMESTAMP}.db.gz"
fi

if [ -f "$ENV" ]; then
    cp "$ENV" "$BACKUP_DIR/env_${TIMESTAMP}.txt"
    echo "ENV backup: $BACKUP_DIR/env_${TIMESTAMP}.txt"
fi

find "$BACKUP_DIR" -name "db_*.db.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "env_*.txt" -mtime +$RETENTION_DAYS -delete

echo "Backup completato. Retention: $RETENTION_DAYS giorni"
