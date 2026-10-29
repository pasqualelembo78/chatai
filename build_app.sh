#!/usr/bin/env bash
#
# build_app.sh — Installazione ChatAI
# Backend Python, Apache, Redis, ClamAV, Ollama, APK Android e servizi di sistema.
#
# ATTENZIONE: questo script modifica pacchetti, servizi, firewall e file di sistema.
# Prima di usarlo su produzione, esaminare le opzioni e fare un backup del server.
#
# Opzioni:
#   --skip-py           Salta setup backend Python
#   --skip-apk          Salta build Android AAB/APK
#   --skip-ollama       Salta setup/download Ollama
#   --skip-audio        Salta dipendenze audio STT/TTS
#   --skip-apache       Salta configurazione Apache
#   --skip-letsencrypt  Salta setup HTTPS Let's Encrypt
#   --skip-firewall     Salta configurazione UFW
#   --skip-redis        Salta Redis
#   --skip-clamav       Salta ClamAV
#   --non-interactive   Non mostra prompt; senza --models seleziona i modelli predefiniti
#   --models "m1 m2"    Seleziona modelli Ollama; --models "" non seleziona nessun modello
#   --env-only          Termina dopo la configurazione del file .env
#   --domain nome.it    Dominio per HTTPS
#   --email a@b.it      Email Let's Encrypt
#   -h, --help          Mostra aiuto
#
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "    ${GREEN}$*${NC}"; }
warn() { echo -e "    ${YELLOW}$*${NC}"; }
err()  { echo -e "    ${RED}$*${NC}" >&2; }

show_help() {
    cat <<'HELP'
Uso: ./build_app.sh [opzioni]
  --skip-py           Salta setup backend Python
  --skip-apk          Salta build Android AAB/APK
  --skip-ollama       Salta setup/download Ollama
  --skip-audio        Salta dipendenze audio
  --skip-apache       Salta configurazione Apache
  --skip-letsencrypt  Salta HTTPS Let's Encrypt
  --skip-firewall     Salta configurazione UFW
  --skip-redis        Salta Redis
  --skip-clamav       Salta ClamAV
  --non-interactive   Non mostra prompt; usa i modelli predefiniti se --models manca
  --models "m1 m2"    Modelli Ollama da installare; --models "" salta tutti i modelli
  --env-only          Termina dopo la configurazione di backend/.env
  --domain nome.it    Dominio per HTTPS
  --email a@b.it      Email Let's Encrypt
  -h, --help          Mostra questo aiuto
HELP
}

# Defaults / model names.
ABLITERATED_MODELS='hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M'
UNCENSORED_MODELS='hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M'
DEFAULT_MODELS="$ABLITERATED_MODELS $UNCENSORED_MODELS"

SKIP_PY=false SKIP_APK=false SKIP_OLLAMA=false SKIP_AUDIO=false
SKIP_APACHE=false SKIP_LETSENCRYPT=false SKIP_FIREWALL=false
SKIP_REDIS=false SKIP_CLAMAV=false SKIP_PROMPTS=false ENV_ONLY=false
SELECTED_MODELS='' MODELS_ARG_PROVIDED=false DOMAIN='' EMAIL=''

# Parse arguments without conflating a missing --models option with --models "".
while (($#)); do
    case "$1" in
        -h|--help) show_help; exit 0 ;;
        --skip-py) SKIP_PY=true; shift ;;
        --skip-apk) SKIP_APK=true; shift ;;
        --skip-ollama) SKIP_OLLAMA=true; shift ;;
        --skip-audio) SKIP_AUDIO=true; shift ;;
        --skip-apache) SKIP_APACHE=true; shift ;;
        --skip-letsencrypt) SKIP_LETSENCRYPT=true; shift ;;
        --skip-firewall) SKIP_FIREWALL=true; shift ;;
        --skip-redis) SKIP_REDIS=true; shift ;;
        --skip-clamav) SKIP_CLAMAV=true; shift ;;
        --non-interactive) SKIP_PROMPTS=true; shift ;;
        --models)
            if (($# < 2)); then err "Manca il valore di --models (usa --models \"\" per nessun modello)."; exit 2; fi
            SELECTED_MODELS="$2"; MODELS_ARG_PROVIDED=true; shift 2 ;;
        --env-only) ENV_ONLY=true; shift ;;
        --domain)
            if (($# < 2)); then err "Manca il valore di --domain."; exit 2; fi
            DOMAIN="$2"; shift 2 ;;
        --email)
            if (($# < 2)); then err "Manca il valore di --email."; exit 2; fi
            EMAIL="$2"; shift 2 ;;
        *) err "Opzione sconosciuta: $1"; show_help; exit 2 ;;
    esac
done

_prompt_model_selection() {
    local model_choice individual_choice all_models model idx
    echo
    echo -e "${BLUE}=== Selezione Modelli Ollama ===${NC}"
    echo '  1) Tutti i modelli'
    echo '  2) Solo Qwen 3B abliterated RP (uncensored, roleplay)'
    echo '  3) Solo Qwen 3B abliterated (uncensored)'
    echo '  4) Selezione individuale'
    echo '  5) Nessun modello'
    if [[ "$SKIP_PROMPTS" == true ]]; then
        warn 'Modalità non interattiva: uso i modelli predefiniti.'
        OLLAMA_MODELS="$DEFAULT_MODELS"
        return
    fi
    read -r -p 'Scelta [1-5] (default 1): ' model_choice || model_choice=1
    model_choice="${model_choice:-1}"
    case "$model_choice" in
        1) OLLAMA_MODELS="$DEFAULT_MODELS" ;;
        2) OLLAMA_MODELS="$ABLITERATED_MODELS" ;;
        3) OLLAMA_MODELS="$UNCENSORED_MODELS" ;;
        4)
            echo '  1) hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M'
            echo '  2) hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M'
            read -r -p 'Seleziona numeri separati da spazi (oppure tutti): ' individual_choice || individual_choice=''
            if [[ "$individual_choice" == 'tutti' ]]; then
                OLLAMA_MODELS="$DEFAULT_MODELS"
            else
                OLLAMA_MODELS=''
                all_models="$ABLITERATED_MODELS $UNCENSORED_MODELS"
                for model in $all_models; do
                    idx=1
                    # Il numero corrisponde alla posizione nella lista di due modelli.
                    [[ "$model" == "$ABLITERATED_MODELS" ]] && idx=1
                    [[ "$model" == "$UNCENSORED_MODELS" ]] && idx=2
                    if [[ " $individual_choice " =~ (^|[[:space:]])${idx}([[:space:]]|$) ]]; then
                        OLLAMA_MODELS="${OLLAMA_MODELS:+$OLLAMA_MODELS }$model"
                    fi
                done
            fi
            ;;
        5) OLLAMA_MODELS='' ;;
        *) warn 'Scelta non valida: uso i modelli predefiniti.'; OLLAMA_MODELS="$DEFAULT_MODELS" ;;
    esac
}

if [[ "$MODELS_ARG_PROVIDED" == true ]]; then
    # Un valore esplicitamente vuoto significa nessun modello: NON mostrare il menu.
    OLLAMA_MODELS="$SELECTED_MODELS"
elif [[ "$ENV_ONLY" == true ]]; then
    # In modalità solo-ambiente non chiedere né selezionare modelli.
    OLLAMA_MODELS=''
else
    _prompt_model_selection
fi

SUDO=''
if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then err 'Esegui come root oppure installa sudo.'; exit 1; fi
    SUDO='sudo'
    warn 'Alcuni passaggi richiedono privilegi amministrativi; uso sudo.'
fi

run_root() {
    if [[ -n "$SUDO" ]]; then "$SUDO" "$@"; else "$@"; fi
}

cat <<EOF

${BLUE}==================================================${NC}
${BLUE} ChatAI - Build Script${NC}
${BLUE} Backend + Apache + Redis + ClamAV + Ollama + Android${NC}
${BLUE}==================================================${NC}
EOF

# In modalità --env-only non eseguire installazioni di sistema, modifiche al
# firewall, configurazioni Apache o altri cambiamenti estranei al file .env.
if [[ "$ENV_ONLY" == false ]]; then

# -----------------------------------------------------------------------------
# PASSO 0 — pacchetti e directory necessarie
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}>>> [0/9] Pacchetti di sistema...${NC}"
run_root apt-get update -qq
PACKAGES='python3 python3-pip python3-venv curl wget git lsof bc openssl'
[[ "$SKIP_APACHE" == false ]] && PACKAGES+=' apache2'
[[ "$SKIP_REDIS" == false ]] && PACKAGES+=' redis-server'
[[ "$SKIP_CLAMAV" == false ]] && PACKAGES+=' clamav clamav-daemon'
[[ "$SKIP_FIREWALL" == false ]] && PACKAGES+=' ufw'
run_root apt-get install -y -qq $PACKAGES
if ! id -u chatai >/dev/null 2>&1; then
    run_root useradd -r -s /usr/sbin/nologin -d "$ROOT_DIR" chatai 2>/dev/null || true
fi
run_root mkdir -p /tmp/chatai_uploads
run_root chmod 700 /tmp/chatai_uploads
run_root chown chatai:chatai /tmp/chatai_uploads 2>/dev/null || true
info 'Pacchetti e directory di upload pronti.'

# -----------------------------------------------------------------------------
# PASSO 1 — backend Python
# -----------------------------------------------------------------------------
if [[ "$SKIP_PY" == false ]]; then
    echo; echo -e "${YELLOW}>>> [1/9] Backend Python...${NC}"
    cd "$ROOT_DIR/backend"
    [[ -f requirements.txt ]] || { err 'backend/requirements.txt non trovato.'; exit 1; }
    if [[ ! -x venv/bin/python3 || ! -x venv/bin/pip ]]; then
        warn 'Ambiente virtuale assente o incompleto: lo ricreo.'
        rm -rf -- venv
        python3 -m venv venv
    fi
    # Gli errori d'installazione non devono essere nascosti da tail/grep.
    venv/bin/python3 -m pip install --upgrade pip
    venv/bin/python3 -m pip install -r requirements.txt
    venv/bin/python3 - <<'PY'
import os, py_compile, sys
errors = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('venv', '__pycache__', '.git')]
    for name in files:
        if name.endswith('.py'):
            path = os.path.join(root, name)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(str(exc))
if errors:
    print('\n'.join('FAIL: ' + item for item in errors), file=sys.stderr)
    sys.exit(1)
print('Sintassi Python: OK')
PY
    cd "$ROOT_DIR"
    run_root mkdir -p "$ROOT_DIR/backend/characters/data"
    run_root chown -R chatai:chatai "$ROOT_DIR/backend/characters" 2>/dev/null || true
    run_root chgrp -R chatai "$ROOT_DIR" 2>/dev/null || true
    run_root chmod g+rwx "$ROOT_DIR/backend" 2>/dev/null || true
    run_root chmod -R g+rx "$ROOT_DIR/backend" 2>/dev/null || true
    run_root chmod 750 "$ROOT_DIR/backend/venv" 2>/dev/null || true
    [[ ! -f "$ROOT_DIR/backend/.env" ]] || run_root chmod 640 "$ROOT_DIR/backend/.env"
    info 'Backend Python installato e verificato.'
fi

# -----------------------------------------------------------------------------
# Hardening / watchdog integrità
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> [1b/9] Watchdog integrità...${NC}"
run_root find "$ROOT_DIR/backend" -maxdepth 1 -type f -name '*.py' -exec chmod a-w {} \; 2>/dev/null || true
INTEGRITY_SCRIPT='/usr/local/bin/chatai_integrity.sh'
run_root tee "$INTEGRITY_SCRIPT" >/dev/null <<INTEGRITYEOF
#!/usr/bin/env bash
ROOT="$ROOT_DIR"
cd "\$ROOT" || exit 0
if [[ -d .git ]]; then
    MODIFIED=\$(git diff --name-only -- backend/ 2>/dev/null | tr '\n' ' ')
    [[ -z "\$MODIFIED" ]] || logger -t chatai-integrity "BACKEND FILES MODIFIED: \$MODIFIED"
    MODIFIED_APP=\$(git diff --name-only -- app/ 2>/dev/null | tr '\n' ' ')
    [[ -z "\$MODIFIED_APP" ]] || logger -t chatai-integrity "APP FILES MODIFIED: \$MODIFIED_APP"
    UNTRACKED=\$(git ls-files --others --exclude-standard backend/ app/ 2>/dev/null | head -10 | tr '\n' ' ')
    [[ -z "\$UNTRACKED" ]] || logger -t chatai-integrity "UNTRACKED FILES: \$UNTRACKED"
fi
INTEGRITYEOF
run_root chmod 750 "$INTEGRITY_SCRIPT"
if ! grep -qF "$INTEGRITY_SCRIPT" /etc/crontab 2>/dev/null; then
    echo "*/5 * * * * root $INTEGRITY_SCRIPT" | run_root tee -a /etc/crontab >/dev/null
fi
info 'Watchdog configurato.'

# -----------------------------------------------------------------------------
# PASSO 2 — audio STT/TTS (Piper)
# -----------------------------------------------------------------------------
if [[ "$SKIP_PY" == false && "$SKIP_AUDIO" == false ]]; then
    echo; echo -e "${YELLOW}>>> [2/9] Dipendenze audio...${NC}"
    if ! ldconfig -p 2>/dev/null | grep -q libsndfile; then
        run_root apt-get install -y -qq libsndfile1 || warn 'Installazione libsndfile1 non riuscita.'
    fi
    if ! command -v piper >/dev/null 2>&1; then
        ARCH="$(uname -m)"
        case "$ARCH" in x86_64) PIPER_ARCH=amd64;; aarch64) PIPER_ARCH=aarch64;; armv7l) PIPER_ARCH=armv7l;; *) PIPER_ARCH='';; esac
        if [[ -n "$PIPER_ARCH" ]]; then
            PIPER_URL="https://github.com/rhasspy/piper/releases/download/v2023.11.14-2/piper_${PIPER_ARCH}.tar.gz"
            TMP_PIPER="$(mktemp -d)"
            if curl -fLsS "$PIPER_URL" | tar xz -C "$TMP_PIPER"; then
                if [[ -x "$TMP_PIPER/piper/piper" ]]; then
                    run_root install -m 755 "$TMP_PIPER/piper/piper" /usr/local/bin/piper
                else
                    warn 'Archivio Piper scaricato ma binario non trovato.'
                fi
            else
                warn 'Download Piper non riuscito.'
            fi
            rm -rf -- "$TMP_PIPER"
        else
            warn "Architettura $ARCH non supportata dal binario Piper previsto."
        fi
    fi
    VOICES_DIR='/usr/share/piper/voices'
    run_root mkdir -p "$VOICES_DIR"
    for voice in it_IT-paola-medium it_IT-riccardo-medium; do
        ONNX="$VOICES_DIR/${voice}.onnx"
        if [[ ! -s "$ONNX" ]]; then
            HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/${voice}"
            if run_root curl -fLsS "$HF_BASE/${voice}.onnx" -o "$ONNX"; then
                run_root curl -fLsS "$HF_BASE/${voice}.json" -o "$VOICES_DIR/${voice}.json" || warn "Metadati voce $voice non scaricati."
                run_root chmod 644 "$ONNX" "$VOICES_DIR/${voice}.json" 2>/dev/null || true
                info "Voce $voice pronta."
            else
                warn "Download voce $voice non riuscito."
                run_root rm -f "$ONNX"
            fi
        else
            info "Voce $voice già presente."
        fi
    done
fi

# -----------------------------------------------------------------------------
# PASSO 3 — Redis
# -----------------------------------------------------------------------------
if [[ "$SKIP_REDIS" == false ]]; then
    echo; echo -e "${YELLOW}>>> [3/9] Redis...${NC}"
    if command -v redis-server >/dev/null 2>&1; then
        run_root systemctl enable redis-server 2>/dev/null || true
        run_root systemctl start redis-server 2>/dev/null || true
        REDIS_CONF='/etc/redis/redis.conf'
        if [[ -f "$REDIS_CONF" ]]; then
            if grep -qE '^\s*bind ' "$REDIS_CONF"; then
                run_root sed -i -E 's/^\s*bind .*/bind 127.0.0.1 ::1/' "$REDIS_CONF"
            else
                echo 'bind 127.0.0.1 ::1' | run_root tee -a "$REDIS_CONF" >/dev/null
            fi
            run_root systemctl restart redis-server 2>/dev/null || true
        fi
        info 'Redis configurato per ascoltare in locale (se la configurazione lo consente).'
    else warn 'redis-server non trovato.'; fi
fi

# -----------------------------------------------------------------------------
# PASSO 4 — ClamAV
# -----------------------------------------------------------------------------
if [[ "$SKIP_CLAMAV" == false ]]; then
    echo; echo -e "${YELLOW}>>> [4/9] ClamAV...${NC}"
    if command -v clamd >/dev/null 2>&1 || command -v clamdscan >/dev/null 2>&1; then
        run_root systemctl stop clamav-freshclam 2>/dev/null || true
        run_root freshclam --quiet || warn 'Aggiornamento definizioni ClamAV non riuscito; continuo.'
        run_root systemctl start clamav-freshclam 2>/dev/null || true
        run_root systemctl enable clamav-daemon 2>/dev/null || true
        run_root systemctl start clamav-daemon 2>/dev/null || true
        info 'ClamAV configurato.'
    else warn 'ClamAV non trovato; verificare l’installazione.'; fi
fi

# -----------------------------------------------------------------------------
# PASSO 5 — Apache reverse proxy / HTTPS
# -----------------------------------------------------------------------------
if [[ "$SKIP_APACHE" == false ]]; then
    echo; echo -e "${YELLOW}>>> [5/9] Apache reverse proxy...${NC}"
    run_root a2enmod proxy proxy_http proxy_wstunnel ssl headers rewrite 2>/dev/null || true
    APACHE_SITE='/etc/apache2/sites-available/chatai.conf'
    SERVER_NAME="${DOMAIN:-localhost}"
    if [[ -n "$DOMAIN" && -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" && -s "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]]; then
        run_root tee "$APACHE_SITE" >/dev/null <<APACHEEOF
<VirtualHost *:80>
    ServerName $SERVER_NAME
    Redirect permanent / https://$SERVER_NAME/
</VirtualHost>
<VirtualHost *:443>
    ServerName $SERVER_NAME
    SSLEngine On
    SSLCertificateFile /etc/letsencrypt/live/$SERVER_NAME/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/$SERVER_NAME/privkey.pem
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set Referrer-Policy "no-referrer"
    LimitRequestBody 26214400
    ProxyPreserveHost On
    ProxyPass /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPassReverse /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    ErrorLog \${APACHE_LOG_DIR}/chatai_error.log
    CustomLog \${APACHE_LOG_DIR}/chatai_access.log combined
</VirtualHost>
APACHEEOF
    else
        run_root tee "$APACHE_SITE" >/dev/null <<APACHEEOF
<VirtualHost *:80>
    ServerName $SERVER_NAME
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    LimitRequestBody 26214400
    ProxyPreserveHost On
    ProxyPass /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPassReverse /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    ErrorLog \${APACHE_LOG_DIR}/chatai_error.log
    CustomLog \${APACHE_LOG_DIR}/chatai_access.log combined
</VirtualHost>
APACHEEOF
    fi
    run_root a2dissite 000-default.conf 2>/dev/null || true
    run_root a2ensite chatai.conf 2>/dev/null || true
    if command -v apache2ctl >/dev/null 2>&1 && apache2ctl configtest; then
        run_root systemctl reload apache2 2>/dev/null || run_root systemctl restart apache2
        info "Apache configurato: $APACHE_SITE"
    else
        err 'Test configurazione Apache fallito: non ricarico Apache.'
        exit 1
    fi
    if [[ "$SKIP_LETSENCRYPT" == false && -n "$DOMAIN" && -n "$EMAIL" ]]; then
        run_root apt-get install -y -qq certbot python3-certbot-apache
        if command -v certbot >/dev/null 2>&1; then
            run_root certbot --apache -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || warn 'Certbot non riuscito; controlla DNS e porte 80/443.'
        fi
    elif [[ -n "$DOMAIN" && -z "$EMAIL" ]]; then
        warn 'Dominio specificato ma email mancante: salto Certbot.'
    fi
fi

fi # fine blocco installazione di sistema (saltato da --env-only)

# -----------------------------------------------------------------------------
# PASSO 6 — .env
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> [6/9] Configurazione .env...${NC}"
ENV_FILE="$ROOT_DIR/backend/.env"
ENV_EXAMPLE="$ROOT_DIR/backend/.env.example"
run_root mkdir -p "$ROOT_DIR/backend"
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then cp "$ENV_EXAMPLE" "$ENV_FILE"; else touch "$ENV_FILE"; fi
fi
if grep -q '^JWT_SECRET=changeme_in_production' "$ENV_FILE" 2>/dev/null || ! grep -q '^JWT_SECRET=' "$ENV_FILE" 2>/dev/null; then
    NEW_SECRET="$(openssl rand -hex 64)"
    if grep -q '^JWT_SECRET=' "$ENV_FILE" 2>/dev/null; then
        sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" "$ENV_FILE"
    else printf 'JWT_SECRET=%s\n' "$NEW_SECRET" >> "$ENV_FILE"; fi
    info 'JWT_SECRET generato.'
fi
if ! grep -q '^REDIS_URL=' "$ENV_FILE" 2>/dev/null; then
    printf '%s\n' 'REDIS_URL=redis://localhost:6379/0' >> "$ENV_FILE"
fi
if ! grep -q '^PORT=' "$ENV_FILE" 2>/dev/null; then printf '%s\n' 'PORT=5000' >> "$ENV_FILE"; fi
if grep -q '^FLASK_ENV=development' "$ENV_FILE" 2>/dev/null; then
    sed -i 's/^FLASK_ENV=development/FLASK_ENV=production/' "$ENV_FILE"
elif ! grep -q '^FLASK_ENV=' "$ENV_FILE" 2>/dev/null; then printf '%s\n' 'FLASK_ENV=production' >> "$ENV_FILE"; fi
if ! grep -q '^MODEL_REFRESH_TTL=' "$ENV_FILE" 2>/dev/null; then printf '%s\n' 'MODEL_REFRESH_TTL=3600' >> "$ENV_FILE"; fi
if ! grep -q '^EVENTLET_NO_GREENDNS=' "$ENV_FILE" 2>/dev/null; then printf '%s\n' 'EVENTLET_NO_GREENDNS=yes' >> "$ENV_FILE"; fi

# Load environment file for values already configured. This file is trusted local config.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

_prompt_key() {
    local var_name="$1" display_name="$2" current_val
    current_val="${!var_name:-}"
    [[ -n "$current_val" ]] && { info "$display_name già configurato."; return 0; }
    [[ "$SKIP_PROMPTS" == true ]] && { warn "$display_name non configurato (prompt saltato)."; return 0; }
    local key_val
    read -r -p "$display_name (Invio per saltare): " key_val || key_val=''
    if [[ -n "$key_val" ]]; then
        printf '%s=%s\n' "$var_name" "$key_val" >> "$ENV_FILE"
        export "$var_name=$key_val"
        info "$display_name salvato."
    fi
}

for spec in \
    'GEMINI_API_KEY|Google Gemini API Key' \
    'GROQ_API_KEY|Groq API Key' \
    'OPENROUTER_API_KEY|OpenRouter API Key' \
    'MISTRAL_API_KEY|Mistral AI API Key' \
    'HUGGINGFACE_API_KEY|Hugging Face API Key' \
    'GITHUB_TOKEN|GitHub Token' \
    'OPENAI_API_KEY|OpenAI API Key' \
    'ANTHROPIC_API_KEY|Anthropic API Key' \
    'TOGETHER_API_KEY|Together AI API Key' \
    'CEREBRAS_API_KEY|Cerebras API Key' \
    'CLOUDFLARE_API_TOKEN|Cloudflare Workers AI Token' \
    'CLOUDFLARE_ACCOUNT_ID|Cloudflare Account ID' \
    'COHERE_API_KEY|Cohere API Key' \
    'DEEPINFRA_API_KEY|DeepInfra API Key' \
    'FIREWORKS_API_KEY|Fireworks API Key' \
    'SAMBANOVA_API_KEY|SambaNova API Key' \
    'NEBIUS_API_KEY|Nebius API Key' \
    'NOVITA_API_KEY|Novita API Key' \
    'INFERENCE_API_KEY|Inference.net API Key' \
    'LLAMACPP_API_KEY|llama.cpp API Key' \
    'GOOGLE_CLIENT_ID|Google Client ID' \
    'MASTER_KEY|Master Key per crittografia dati' \
    'SENTRY_DSN|Sentry DSN' \
    'TELEGRAM_BOT_TOKEN|Telegram Bot Token' \
    'TELEGRAM_CHAT_ID|Telegram Chat ID'; do
    IFS='|' read -r var_name display_name <<< "$spec"
    _prompt_key "$var_name" "$display_name"
done
run_root chmod 640 "$ENV_FILE" 2>/dev/null || true
if [[ "$ENV_ONLY" == true ]]; then
    echo; info "Configurazione .env terminata: $ENV_FILE"; exit 0
fi

# -----------------------------------------------------------------------------
# PASSO 7 — Ollama e modelli. --skip-py NON disabilita più Ollama.
# -----------------------------------------------------------------------------
if [[ "$SKIP_OLLAMA" == false ]]; then
    echo; echo -e "${YELLOW}>>> [7/9] Ollama e modelli AI...${NC}"
    if ! command -v ollama >/dev/null 2>&1; then
        warn 'Installazione Ollama...'
        curl -fsSL https://ollama.com/install.sh | run_root sh
    fi
    OLLAMA_READY=false
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        OLLAMA_READY=true
    else
        run_root systemctl enable ollama 2>/dev/null || true
        run_root systemctl start ollama 2>/dev/null || true
        for _ in $(seq 1 20); do
            if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then OLLAMA_READY=true; break; fi
            sleep 1
        done
    fi
    if [[ "$OLLAMA_READY" != true ]]; then
        err 'API Ollama non disponibile. Non eseguo pull/create; controlla: systemctl status ollama.'
    elif [[ -z "${OLLAMA_MODELS//[[:space:]]/}" ]]; then
        info 'Nessun modello selezionato: salto tutti i download e la creazione locale.'
    else
        info "Modelli selezionati: $OLLAMA_MODELS"
        MODEL_FAILED=false
        for model in $OLLAMA_MODELS; do
            [[ "$model" == *stheno* ]] && continue
            if ollama list 2>/dev/null | awk -v m="$model" 'NR > 1 && $1 == m {found=1} END {exit !found}'; then
                info "Modello '$model' già presente."
            else
                warn "Download modello '$model'..."
                if ! ollama pull "$model"; then
                    err "Download fallito per '$model'."
                    MODEL_FAILED=true
                    break
                fi
            fi
        done

        if [[ "$MODEL_FAILED" == true ]]; then
            err 'Errore nel download dei modelli; non proseguo con la configurazione dei modelli.'
        elif [[ " $OLLAMA_MODELS " == *"stheno"* ]]; then
            MODelfile_2k="$ROOT_DIR/stheno/Modelfile.stheno-2k"
            BASE_MODEL='hf.co/mradermacher/L3-8B-Stheno-v3.2-abliterated-GGUF:Q4_K_M'
            STHENO_2K="$ABLITERATED_MODELS"
            if [[ ! -f "$MODelfile_2k" ]]; then
                err "Modelfile selezionato ma non trovato: $MODelfile_2k"
                exit 1
            fi
            if ! grep -Fxq "FROM $BASE_MODEL" "$MODelfile_2k"; then
                err "Il FROM nel Modelfile non corrisponde alla base attesa: $BASE_MODEL"
                err 'Correggi il Modelfile prima di creare il modello.'
                exit 1
            fi
            if ollama list 2>/dev/null | awk -v m="$STHENO_2K" 'NR > 1 && $1 == m {found=1} END {exit !found}'; then
                CURRENT_CTX="$(ollama show "$STHENO_2K" --modelfile 2>/dev/null | awk '$1 == "PARAMETER" && $2 == "num_ctx" {print $3; exit}')"
                if [[ "$CURRENT_CTX" == '2048' ]]; then
                    info "Modello '$STHENO_2K' già presente con num_ctx=2048."
                else
                    warn "Contesto esistente '$CURRENT_CTX' (atteso 2048): ricreo l'alias locale dal Modelfile."
                    # Il modello base deve essere disponibile prima di creare l'alias.
                    if ! ollama show "$BASE_MODEL" >/dev/null 2>&1; then
                        warn "Base non presente; scarico '$BASE_MODEL'..."
                        ollama pull "$BASE_MODEL" || { err 'Download base fallito; modello locale non aggiornato.'; exit 1; }
                    fi
                    ollama create -f "$MODelfile_2k" "$STHENO_2K"
                fi
            else
                # Verifica la base con il nome esatto; se non è in cache, scaricala.
                if ! ollama show "$BASE_MODEL" >/dev/null 2>&1; then
                    warn "Download base GGUF: $BASE_MODEL"
                    ollama pull "$BASE_MODEL" || { err 'Download base fallito. Creazione interrotta.'; exit 1; }
                else
                    info 'Base GGUF già disponibile in Ollama.'
                fi
                # IMPORTANTE: create viene eseguito sia quando la base esisteva già,
                # sia dopo un download riuscito.
                ollama create -f "$MODelfile_2k" "$STHENO_2K"
            fi
            FINAL_CTX="$(ollama show "$STHENO_2K" --modelfile 2>/dev/null | awk '$1 == "PARAMETER" && $2 == "num_ctx" {print $3; exit}')"
            if [[ "$FINAL_CTX" != '2048' ]]; then
                err "Verifica dopo creazione fallita: num_ctx='$FINAL_CTX', atteso 2048."
                exit 1
            fi
            info "Modello '$STHENO_2K' verificato: num_ctx=2048."
        fi
    fi
fi

# -----------------------------------------------------------------------------
# PASSO 8 — DNS fallback. Non modifica la configurazione se resolvectl manca.
# -----------------------------------------------------------------------------
if command -v resolvectl >/dev/null 2>&1; then
    echo; echo -e "${YELLOW}>>> [8/9] DNS fallback...${NC}"
    IFACE="$(ip -o link show up 2>/dev/null | awk -F': ' '$2 !~ /docker|lo|veth/ {print $2; exit}')"
    if [[ -n "$IFACE" ]]; then
        CURRENT_DNS="$(resolvectl dns "$IFACE" 2>/dev/null | sed "s/^$IFACE: *//" || true)"
        if [[ "$CURRENT_DNS" != *'8.8.8.8'* ]]; then
            # Aggiunge DNS fallback senza azzerare l'intera configurazione di rete.
            read -r -a DNS_ARGS <<< "$CURRENT_DNS"
            run_root resolvectl dns "$IFACE" "${DNS_ARGS[@]}" 8.8.8.8 8.8.4.4 2>/dev/null || warn 'Impostazione DNS temporanea non riuscita.'
        fi
    fi
    run_root mkdir -p /etc/systemd/resolved.conf.d
    run_root tee /etc/systemd/resolved.conf.d/dns.conf >/dev/null <<'DNSEOF'
[Resolve]
FallbackDNS=8.8.8.8 8.8.4.4 1.1.1.1
Cache=yes
DNSEOF
    run_root systemctl restart systemd-resolved 2>/dev/null || true
    info 'Fallback DNS configurato.'
fi

# -----------------------------------------------------------------------------
# PASSO 9 — UFW. Non esegue ufw reset: preserva le regole preesistenti.
# -----------------------------------------------------------------------------
if [[ "$SKIP_FIREWALL" == false ]]; then
    echo; echo -e "${YELLOW}>>> [9/9] UFW firewall...${NC}"
    if command -v ufw >/dev/null 2>&1; then
        # Aggiunge regole idempotenti senza cancellare regole custom/SSH già presenti.
        run_root ufw default deny incoming
        run_root ufw default allow outgoing
        run_root ufw allow ssh
        run_root ufw allow 80/tcp
        [[ -z "$DOMAIN" ]] || run_root ufw allow 443/tcp
        # La porta 5000 è mantenuta per compatibilità con l'app attuale.
        # Per esporre SOLO Apache, verificare prima la configurazione Android e poi
        # rimuovere questa regola e fare ascoltare Uvicorn su 127.0.0.1.
        run_root ufw allow 5000/tcp
        run_root ufw --force enable
        info 'Regole UFW aggiornate senza azzerare quelle preesistenti.'
    else warn 'UFW non trovato.'; fi
fi

# -----------------------------------------------------------------------------
# Fail2ban (se già installato)
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> Fail2ban...${NC}"
if command -v fail2ban-server >/dev/null 2>&1; then
    [[ ! -f "$ROOT_DIR/backend/fail2ban-chatai.conf" ]] || run_root install -m 644 "$ROOT_DIR/backend/fail2ban-chatai.conf" /etc/fail2ban/filter.d/chatai.conf
    [[ ! -f "$ROOT_DIR/backend/fail2ban-jail.conf" ]] || run_root install -m 644 "$ROOT_DIR/backend/fail2ban-jail.conf" /etc/fail2ban/jail.d/chatai.conf
    run_root systemctl enable fail2ban 2>/dev/null || true
    run_root systemctl restart fail2ban 2>/dev/null || true
    info 'Fail2ban configurato (se i file di configurazione esistono).'
else warn 'Fail2ban non installato: salto la configurazione.'; fi

# -----------------------------------------------------------------------------
# Backup database cron
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> Cron backup database...${NC}"
BACKUP_SCRIPT="$ROOT_DIR/backend/backup.sh"
if [[ -f "$BACKUP_SCRIPT" ]]; then
    chmod 750 "$BACKUP_SCRIPT"
    BACKUP_CMD="sudo -u chatai $BACKUP_SCRIPT"
    CURRENT_CRON="$(run_root crontab -l 2>/dev/null || true)"
    { printf '%s\n' "$CURRENT_CRON" | grep -vF "$BACKUP_SCRIPT" || true; echo "0 3 * * * $BACKUP_CMD"; } | run_root crontab -
    info 'Backup schedulato ogni giorno alle 03:00 (verificare permessi e retention in backup.sh).'
fi

# -----------------------------------------------------------------------------
# Pruning dati: query parametrizzate correttamente in PostgreSQL
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> Cron pruning dati...${NC}"
PRUNE_SCRIPT="$ROOT_DIR/backend/prune_cron.py"
if [[ ! -f "$PRUNE_SCRIPT" ]]; then
    cat > "$PRUNE_SCRIPT" <<'PYEOF'
#!/usr/bin/env python3
"""Elimina dati oltre la retention configurata (default 90 giorni)."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prune_cron")
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def load_database_url():
    value = os.environ.get("DATABASE_URL")
    if value:
        return value
    try:
        with open(ENV_FILE, encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    raise RuntimeError("DATABASE_URL non trovato")


def main():
    import psycopg2
    retention = int(os.environ.get("PRUNE_RETENTION_DAYS", "90"))
    if retention < 1 or retention > 3650:
        raise ValueError("PRUNE_RETENTION_DAYS deve essere compreso tra 1 e 3650")
    conn = psycopg2.connect(load_database_url(), connect_timeout=15)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE timestamp < NOW() - (%s * INTERVAL '1 day')", (retention,))
                messages = cur.rowcount
                cur.execute("DELETE FROM conversation_memory WHERE created_at < NOW() - (%s * INTERVAL '1 day')", (retention,))
                memories = cur.rowcount
                cur.execute("DELETE FROM personality_shifts WHERE created_at < NOW() - (%s * INTERVAL '1 day')", (retention,))
                shifts = cur.rowcount
                cur.execute("DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '365 days'")
                audit = cur.rowcount
        log.info("Pruning completato: messages=%s memories=%s shifts=%s audit=%s", messages, memories, shifts, audit)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("Pruning fallito: %s", exc)
        sys.exit(1)
PYEOF
    chmod 750 "$PRUNE_SCRIPT"
fi
if [[ -x "$ROOT_DIR/backend/venv/bin/python3" ]]; then
    CURRENT_CRON="$(run_root crontab -l 2>/dev/null || true)"
    { printf '%s\n' "$CURRENT_CRON" | grep -vF "$PRUNE_SCRIPT" || true; echo "0 4 * * * sudo -u chatai $ROOT_DIR/backend/venv/bin/python3 $PRUNE_SCRIPT >> /var/log/chatai_prune.log 2>&1"; } | run_root crontab -
    info 'Pruning schedulato ogni giorno alle 04:00.'
else
    warn 'Pruning non schedulato: backend/venv/bin/python3 non esiste.'
fi

# -----------------------------------------------------------------------------
# Systemd service backend
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> Configurazione systemd...${NC}"
SERVICE_FILE='/etc/systemd/system/chatai.service'
run_root tee "$SERVICE_FILE" >/dev/null <<SERVICEEOF
[Unit]
Description=ChatAI Backend
After=network.target redis-server.service
Wants=redis-server.service
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User=chatai
Group=chatai
WorkingDirectory=$ROOT_DIR/backend
ExecStartPre=$ROOT_DIR/backend/venv/bin/python3 -c "import app; print('Import OK')"
ExecStart=$ROOT_DIR/backend/venv/bin/python3 -m uvicorn app:socket_app --host 0.0.0.0 --port 5000 --workers 1
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
EnvironmentFile=$ROOT_DIR/backend/.env
StandardOutput=append:/var/log/chatai.log
StandardError=append:/var/log/chatai.log
NoNewPrivileges=true
ReadWritePaths=$ROOT_DIR/backend $ROOT_DIR/backend/static/uploads $ROOT_DIR/backend/characters /tmp/chatai_uploads /var/log/chatai.log

[Install]
WantedBy=multi-user.target
SERVICEEOF
run_root systemctl daemon-reload
info "Unit systemd scritto: $SERVICE_FILE"

# -----------------------------------------------------------------------------
# Build Android AAB + APK
# -----------------------------------------------------------------------------
if [[ "$SKIP_APK" == false ]]; then
    echo; echo -e "${YELLOW}>>> Build Android AAB + APK...${NC}"
    [[ -f "$ROOT_DIR/gradlew" ]] || { err 'gradlew non trovato.'; exit 1; }
    chmod +x "$ROOT_DIR/gradlew"
    if [[ -z "${ANDROID_HOME:-}" ]]; then
        for dir in "$HOME/Android/Sdk" /opt/android-sdk /usr/lib/android-sdk; do
            if [[ -d "$dir" ]]; then ANDROID_HOME="$dir"; export ANDROID_HOME; break; fi
        done
    fi
    [[ -n "${ANDROID_HOME:-}" && -d "$ANDROID_HOME" ]] || { err 'ANDROID_HOME non impostato o SDK non trovato.'; exit 1; }
    [[ -f "$ROOT_DIR/local.properties" ]] || printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$ROOT_DIR/local.properties"

    # Non incorporare una password keystore nel sorgente: fornire KEYSTORE_PASS
    # nell'ambiente oppure inserirla al prompt. Deve corrispondere alla password
    # configurata dal progetto Gradle per firmare la release.
    KEYSTORE_FILE="$ROOT_DIR/app/release.keystore"
    KEY_ALIAS='chatai'
    if [[ ! -f "$KEYSTORE_FILE" ]]; then
        if [[ -z "${KEYSTORE_PASS:-}" ]]; then
            if [[ "$SKIP_PROMPTS" == true ]]; then
                err 'Keystore assente: imposta KEYSTORE_PASS nell’ambiente prima della build non interattiva.'
                exit 1
            fi
            read -r -s -p 'Password per il nuovo keystore (deve corrispondere alla configurazione Gradle): ' KEYSTORE_PASS
            echo
            [[ -n "$KEYSTORE_PASS" ]] || { err 'Password vuota: annullo la generazione del keystore.'; exit 1; }
        fi
        command -v keytool >/dev/null 2>&1 || { err 'keytool non trovato.'; exit 1; }
        mkdir -p "$ROOT_DIR/app"
        keytool -genkeypair -v -keystore "$KEYSTORE_FILE" -alias "$KEY_ALIAS" \
            -keyalg RSA -keysize 2048 -validity 10000 \
            -storepass "$KEYSTORE_PASS" -keypass "$KEYSTORE_PASS" \
            -dname 'CN=ChatAI, OU=Dev, O=IntelliGame, L=Unknown, ST=Unknown, C=IT'
    fi
    ./gradlew bundleRelease --no-daemon --console=plain
    ./gradlew assembleRelease --no-daemon --console=plain
    AAB_FILE="$ROOT_DIR/app/build/outputs/bundle/release/app-release.aab"
    APK_FILE="$ROOT_DIR/app/build/outputs/apk/release/app-release.apk"
    [[ -f "$AAB_FILE" ]] || { err 'Build AAB fallita.'; exit 1; }
    info "AAB: $AAB_FILE ($(du -h "$AAB_FILE" | awk '{print $1}'))"
    if [[ -f "$APK_FILE" ]]; then info "APK: $APK_FILE ($(du -h "$APK_FILE" | awk '{print $1}'))"; else warn 'APK non trovato, anche se AAB è stata generata.'; fi
fi

# -----------------------------------------------------------------------------
# Avvio servizio e controllo locale
# -----------------------------------------------------------------------------
echo; echo -e "${YELLOW}>>> Avvio servizio ChatAI...${NC}"
PORT="${PORT:-5000}"
if command -v systemctl >/dev/null 2>&1; then
    run_root systemctl daemon-reload
    run_root systemctl enable chatai
    if ! run_root systemctl restart chatai; then
        err 'Avvio del servizio chatai fallito; controlla journalctl -u chatai -n 80.'
        exit 1
    fi
else
    warn 'systemctl non disponibile: avvio diretto.'
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    cd "$ROOT_DIR/backend"
    nohup venv/bin/python3 -m uvicorn app:socket_app --host 0.0.0.0 --port "$PORT" > /tmp/chatai.log 2>&1 &
    echo $! > /tmp/chatai.pid
    cd "$ROOT_DIR"
fi

SERVER_READY=false
for i in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then SERVER_READY=true; info "Backend raggiungibile localmente in ${i}s."; break; fi
    sleep 1
done
if [[ "$SERVER_READY" != true ]]; then
    warn 'Backend non raggiungibile dopo 60 secondi.'
    warn 'Controlla: systemctl status chatai e journalctl -u chatai -n 80.'
fi

echo
echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} Build terminata${NC}"
echo -e "${BLUE}==================================================${NC}"
echo "  Root progetto: $ROOT_DIR"
echo "  Backend locale: http://127.0.0.1:${PORT}"
[[ -z "$DOMAIN" ]] || echo "  Dominio configurato: $DOMAIN"
if command -v apache2 >/dev/null 2>&1; then echo '  Apache: installato'; else echo '  Apache: non installato'; fi
if command -v redis-cli >/dev/null 2>&1; then echo "  Redis: $(redis-cli ping 2>/dev/null || echo non raggiungibile)"; fi
if command -v clamdscan >/dev/null 2>&1; then echo '  ClamAV: installato'; else echo '  ClamAV: non trovato'; fi
if command -v ufw >/dev/null 2>&1; then echo "  Firewall: $(ufw status 2>/dev/null | head -1)"; fi
echo '  Log: journalctl -u chatai -f'
echo '  Stop: systemctl stop chatai'
echo "  Test: curl -s http://127.0.0.1:${PORT}/"
