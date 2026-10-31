#!/bin/bash
# Script ripetibilità totale - eseguire prima di disinstallare
BACKUP=/tmp/chatai_reproduce_$(date +%Y%m%d).tar.gz

echo "Backup codice backend (prompt + registry + chat_engine):"
tar -czf $BACKUP -C /opt/aria backend/prompt_builder.py backend/ai_engine/registry.py backend/ai_engine/providers/ollama.py backend/chat_engine.py backend/chat_summary.py backend/storage/shared_memory.py opencode.json .env build_app.sh

echo "Backup plugin WP:"
tar -czf ${BACKUP}.wp.tar.gz -C /var/www/pornovirtuale wp-content/plugins/aria-chat/

echo "Backup DB SQL (chat_summaries):"
PGPASSWORD=chatai_secret pg_dump -h localhost -U chatai -d chatai -t chat_summaries --data-only --no-owner > /tmp/chat_summaries_backup.sql

echo "Backup completato in: $BACKUP, $BACKUP.wp.tar.gz, /tmp/chat_summaries_backup.sql"
echo "Per ripristinare: 1) build_app.sh 2) ripristina file dal tar 3) esegui sql_chat_summaries.sql (se DB vuoto) 4) copia plugin 5) riavvia chatai"
