#!/bin/bash
# Ripristino completo da chatai_backup_3b.zip.
#
# NON basta lanciare build_app.sh su un server vuoto: quello installa dipendenze e servizi,
# ma non estrae il backup. Questo script mette prima i file al loro posto, poi chiama
# build_app.sh (idempotente) e alla fine elenca i passaggi che restano da fare a mano.
#
# Uso: sudo ./restore_from_backup.sh [percorso-zip]

set -uo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ZIP="${1:-$ROOT_DIR/chatai_backup_3b.zip}"
shift || true

if [[ ! -f "$ZIP" ]]; then
    echo "Backup non trovato: $ZIP" >&2
    exit 1
fi
if ! command -v unzip >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq unzip || { echo "unzip non installabile" >&2; exit 1; }
fi

echo "== Estrazione dei file applicativi in $ROOT_DIR =="
# parti relative al progetto
unzip -o "$ZIP" -d "$ROOT_DIR" 'backend/*' 'AGENTS.md' 'REPRODUCIBILITY.md' 'BACKLINK.md' \
    'build_app.sh' 'restore_from_backup.sh' '*.sql' 'wordpress-plugin/*' 'crea_stanze_wp.*' \
    'opencode.json' 'ollama_override.conf' 'backend.env' >/dev/null
# il .env storico è salvato come backend.env
if [[ -f "$ROOT_DIR/backend.env" && ! -f "$ROOT_DIR/backend/.env" ]]; then
    cp "$ROOT_DIR/backend.env" "$ROOT_DIR/backend/.env"
fi

echo "== Estrazione delle parti di sistema (WordPress, opt, /usr/local) =="
unzip -o "$ZIP" -d / 'var/www/*' 'opt/aria/*' 'usr/local/*' 'etc/*' >/dev/null 2>&1 || true

echo "== Permessi =="
id -u chatai >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$ROOT_DIR" chatai
chown -R chatai:chatai "$ROOT_DIR/backend" 2>/dev/null || true
[[ -d /var/www ]] && chown -R www-data:www-data /var/www 2>/dev/null || true

echo "== Installazione dipendenze, modelli e servizi (build_app.sh) =="
# senza flag: installazione completa. Passa le stesse opzioni di build_app.sh se servono.
bash "$ROOT_DIR/build_app.sh" "${@:2}" || {
    echo "build_app.sh è terminato con errori: controlla l'output sopra." >&2
}

cat <<'FINE'

== FATTO. Passaggi che restano da fare a mano ==
1. Database PostgreSQL: crea il DB e applica gli SQL del progetto:
     psql "$DATABASE_URL" -f backend/sql_chat_summaries.sql
     psql "$DATABASE_URL" -f backend/sql_chat_response_stats.sql
2. WordPress: attiva il plugin aria-chat, verifica i permalink e il login obbligatorio.
3. Impostazioni → Aria Chat: incolla il token persistente `ptk_...` dell'admin ARIA.
4. Token GitHub per i push futuri (fuori dal repo, per definizione).
5. Verifica: curl -s localhost:5000/health/stato e una chat reale.
FINE
