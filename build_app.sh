#!/bin/bash
#
# build_app.sh — Build script sicuro per produzione
# ChatAI: installa backend + Apache + Redis + ClamAV + Firewall + Android APK
#
# Usage:
#   ./build_app.sh [options]
#
# Options:
#   --skip-py           Salva setup Python backend
#   --skip-apk          Salva build APK Android
#   --skip-ollama       Salva download modelli Ollama
#   --skip-audio        Salva installazione audio (STT/TTS)
#   --skip-apache       Salva configurazione Apache
#   --skip-letsencrypt  Salva setup HTTPS (Let's Encrypt)
#   --skip-firewall     Salva configurazione firewall
#   --skip-redis        Salva installazione Redis
#   --skip-clamav       Salva installazione ClamAV
#   --models "m1 m2"    Modelli Ollama specifici
#   --env-only          Solo configura .env e termina
#   --domain "nome.it"  Dominio per Let's Encrypt (obbligatorio per HTTPS)
#   --email "a@b.it"    Email per Let's Encrypt
#   -h, --help          Mostra aiuto
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ─── Help ────────────────────────────────────────────────────────
if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
    echo ""
    echo "Usage: ./build_app.sh [options]"
    echo ""
    echo "Options:"
    echo "  --skip-py           Skip Python backend setup"
    echo "  --skip-apk          Skip Android APK build"
    echo "  --skip-ollama       Skip Ollama model download"
    echo "  --skip-audio        Skip audio (STT/TTS) installation"
    echo "  --skip-apache       Skip Apache config"
    echo "  --skip-letsencrypt  Skip Let's Encrypt HTTPS"
    echo "  --skip-firewall     Skip firewall (ufw) config"
    echo "  --skip-redis        Skip Redis installation"
    echo "  --skip-clamav       Skip ClamAV installation"
    echo "  --models \"m1 m2\"   Ollama models to download"
    echo "  --env-only          Only configure .env and exit"
    echo "  --domain \"nome.it\"  Domain for Let's Encrypt"
    echo "  --email \"a@b.it\"    Email for Let's Encrypt"
    echo "  -h, --help          Show this help"
    echo ""
    echo "The script is idempotent: safe to run multiple times."
    exit 0
fi

# ─── Configurazione colori ─────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} ChatAI - Build Script Produzione${NC}"
echo -e "${BLUE} Sicurezza: JWT + Apache + Redis + ClamAV + HTTPS${NC}"
echo -e "${BLUE}==================================================${NC}"

# ─── Modelli predefiniti ────────────────────────────────────────
DEFAULT_MODELS="llama3.2:3b qwen2.5:7b"

# ─── Parsing argomenti ──────────────────────────────────────────
SKIP_PY=false
SKIP_APK=false
SKIP_OLLAMA=false
SKIP_AUDIO=false
SKIP_APACHE=false
SKIP_LETSENCRYPT=false
SKIP_FIREWALL=false
SKIP_REDIS=false
SKIP_CLAMAV=false
ENV_ONLY=false
SELECTED_MODELS=""
DOMAIN=""
EMAIL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-py) SKIP_PY=true; shift;;
        --skip-apk) SKIP_APK=true; shift;;
        --skip-ollama) SKIP_OLLAMA=true; shift;;
        --skip-audio) SKIP_AUDIO=true; shift;;
        --skip-apache) SKIP_APACHE=true; shift;;
        --skip-letsencrypt) SKIP_LETSENCRYPT=true; shift;;
        --skip-firewall) SKIP_FIREWALL=true; shift;;
        --skip-redis) SKIP_REDIS=true; shift;;
        --skip-clamav) SKIP_CLAMAV=true; shift;;
        --models) SELECTED_MODELS="$2"; shift 2;;
        --env-only) ENV_ONLY=true; shift;;
        --domain) DOMAIN="$2"; shift 2;;
        --email) EMAIL="$2"; shift 2;;
        *) echo "Opzione sconosciuta: $1"; exit 1;;
    esac
done

if [ -n "$SELECTED_MODELS" ]; then
    OLLAMA_MODELS="$SELECTED_MODELS"
else
    OLLAMA_MODELS="$DEFAULT_MODELS"
fi

# ─── Verifica root ─────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YELLOW}Alcuni passi richiedono root. Uso sudo dove necessario.${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 0: System packages & hardening
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> [0/9] System packages & hardening...${NC}"

$SUDO apt-get update -qq

# Installa pacchetti necessari
PACKAGES=""
if [ "$SKIP_APACHE" = false ]; then
    PACKAGES="$PACKAGES apache2"
fi
if [ "$SKIP_REDIS" = false ]; then
    PACKAGES="$PACKAGES redis-server"
fi
if [ "$SKIP_CLAMAV" = false ]; then
    PACKAGES="$PACKAGES clamav clamav-daemon"
fi
if [ "$SKIP_FIREWALL" = false ]; then
    PACKAGES="$PACKAGES ufw"
fi

# Pacchetti sempre necessari
PACKAGES="$PACKAGES python3 python3-pip python3-venv curl wget git lsof"

if [ -n "$PACKAGES" ]; then
    $SUDO apt-get install -y -qq $PACKAGES
    echo -e "    ${GREEN}Pacchetti di sistema installati.${NC}"
fi

# Crea utente dedicato per il servizio
if ! id -u chatai &>/dev/null; then
    $SUDO useradd -r -s /bin/false -d /opt/chatai chatai 2>/dev/null || true
    echo -e "    ${GREEN}Utente chatai creato.${NC}"
fi

# Crea directory per upload con permessi restrittivi
$SUDO mkdir -p /tmp/chatai_uploads
$SUDO chmod 700 /tmp/chatai_uploads
$SUDO chown chatai:chatai /tmp/chatai_uploads 2>/dev/null || true
echo -e "    ${GREEN}/tmp/chatai_uploads con permessi 700.${NC}"

# ══════════════════════════════════════════════════════════════════
# PASSO 1: Python backend
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_PY" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [1/9] Installing Python backend...${NC}"

    cd "$ROOT_DIR/backend"

    if [ ! -f requirements.txt ]; then
        echo -e "${RED}ERROR: backend/requirements.txt not found${NC}"
        exit 1
    fi

    # Virtual environment (ricrea se mancante o corrotto)
    VENV_OK=false
    if [ -d venv ] && [ -f venv/bin/pip ]; then
        VENV_OK=true
    fi
    if [ "$VENV_OK" = false ]; then
        echo -e "    ${YELLOW}Creating/recreating virtual environment...${NC}"
        rm -rf venv
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip --quiet 2>&1 | tail -1
    pip install -r requirements.txt --quiet 2>&1 | grep -v "already satisfied" || true
    echo -e "    ${GREEN}Python dependencies installed.${NC}"

    # Verifica file Python
    python3 -c "
import py_compile, sys, os
files = ['app.py', 'auth_fastapi.py', 'storage.py', 'db.py', 'ai_engine.py', 'prompt_builder.py', 'evolution_engine.py', 'audio_utils.py', 'image_utils.py', 'avatar_tool.py', 'security_utils.py', 'characters.py']
for f in files:
    if os.path.exists(f):
        py_compile.compile(f, doraise=True)
print('    All Python files OK')
" || { echo -e "${RED}ERROR: Python syntax check failed${NC}"; exit 1; }

    deactivate
    cd "$ROOT_DIR"

    # Permessi restrittivi su backend
    $SUDO chgrp -R chatai "$ROOT_DIR" 2>/dev/null || true
    $SUDO chmod g+rwx "$ROOT_DIR/backend" 2>/dev/null || true
    $SUDO chmod -R g+rx "$ROOT_DIR/backend" 2>/dev/null || true
    $SUDO chmod 750 "$ROOT_DIR/backend/venv" 2>/dev/null || true
    $SUDO chmod 640 "$ROOT_DIR/backend/.env" 2>/dev/null || true
    $SUDO chmod g+w "$ROOT_DIR/backend" 2>/dev/null || true

    echo -e "    ${GREEN}Backend permissions set.${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# Hardening: read-only codice + watchdog integrità
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> [1b/9] Security hardening (read-only + watchdog)...${NC}"

# Rende tutti i .py in backend read-only (blocca modifiche da hacker)
$SUDO find "$ROOT_DIR/backend" -maxdepth 1 -name "*.py" -exec chmod a-w {} \;
echo -e "    ${GREEN}Python files: read-only (a-w).${NC}"

# Git integrity watchdog — ogni 5 min controlla che i file non siano stati modificati
INTEGRITY_SCRIPT="/usr/local/bin/chatai_integrity.sh"
$SUDO tee "$INTEGRITY_SCRIPT" > /dev/null << 'INTEGRITYEOF'
#!/bin/bash
# ChatAI integrity watchdog — eseguito via cron ogni 5 minuti
# LOG le modifiche ma NON reverta automaticamente (evita di cancellare fix legittimi)
ROOT="/opt/chatai"
cd "$ROOT" || exit 0
if [ -d .git ]; then
    MODIFIED=$(git diff --name-only -- backend/ 2>/dev/null | tr '\n' ' ')
    if [ -n "$MODIFIED" ]; then
        logger -t chatai-integrity "BACKEND FILES MODIFIED: $MODIFIED"
        # Rendi scrivibile (build_app.sh fa chmod a-w) e reverta SOLO storage.py se ha perso i PRAGMA
        chmod -R u+w backend/ 2>/dev/null || true
        if echo "$MODIFIED" | grep -q "storage.py" && ! grep -q "PRAGMA" backend/storage.py 2>/dev/null; then
            logger -t chatai-integrity "storage.py perso PRAGMA/timeout — ripristino da git"
            git checkout -- backend/storage.py 2>/dev/null || true
            systemctl restart chatai 2>/dev/null || true
        fi
    fi
    MODIFIED_APP=$(git diff --name-only -- app/ 2>/dev/null | tr '\n' ' ')
    if [ -n "$MODIFIED_APP" ]; then
        logger -t chatai-integrity "APP FILES MODIFIED: $MODIFIED_APP"
    fi
    UNTRACKED=$(git ls-files --others --exclude-standard backend/ app/ 2>/dev/null | head -10 | tr '\n' ' ')
    if [ -n "$UNTRACKED" ]; then
        logger -t chatai-integrity "UNTRACKED FILES: $UNTRACKED"
    fi
fi
INTEGRITYEOF
$SUDO chmod +x "$INTEGRITY_SCRIPT"
echo -e "    ${GREEN}Integrity script: $INTEGRITY_SCRIPT${NC}"

# Aggiunge cron job se non già presente
CRON_LINE="*/5 * * * * root $INTEGRITY_SCRIPT"
if ! grep -q "chatai_integrity" /etc/crontab 2>/dev/null; then
    echo "$CRON_LINE" | $SUDO tee -a /etc/crontab > /dev/null
    echo -e "    ${GREEN}Integrity watchdog: ogni 5 min (crontab).${NC}"
else
    echo -e "    ${GREEN}Integrity watchdog già configurato.${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 2: Audio (STT/TTS)
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_PY" = false ] && [ "$SKIP_AUDIO" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [2/9] Installing audio dependencies...${NC}"

    if ! ldconfig -p 2>/dev/null | grep -q libsndfile; then
        echo -e "    Installing libsndfile1..."
        $SUDO apt-get install -y -qq libsndfile1 2>/dev/null || \
            echo -e "    ${YELLOW}libsndfile1 install failed.${NC}"
    else
        echo -e "    ${GREEN}libsndfile1 already installed.${NC}"
    fi

    # Piper TTS binary
    if ! command -v piper &>/dev/null; then
        echo -e "    ${YELLOW}Installing Piper TTS...${NC}"
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64)  PIPER_ARCH="amd64" ;;
            aarch64) PIPER_ARCH="aarch64" ;;
            armv7l)  PIPER_ARCH="armv7l" ;;
            *)       PIPER_ARCH="" ;;
        esac
        if [ -n "$PIPER_ARCH" ]; then
            PIPER_URL="https://github.com/rhasspy/piper/releases/download/v2023.11.14-2/piper_${PIPER_ARCH}.tar.gz"
            echo -e "    Downloading from $PIPER_URL ..."
            curl -sL "$PIPER_URL" | tar xz -C /tmp/ 2>/dev/null && \
            $SUDO cp /tmp/piper/piper /usr/local/bin/piper && \
            $SUDO chmod +x /usr/local/bin/piper && \
            $SUDO chown chatai:chatai /usr/local/bin/piper 2>/dev/null || true && \
            rm -rf /tmp/piper && \
            echo -e "    ${GREEN}Piper TTS installed.${NC}" || \
            echo -e "    ${YELLOW}Piper download failed, install manually.${NC}"
        else
            echo -e "    ${YELLOW}No prebuilt Piper for $ARCH, install manually.${NC}"
        fi
    else
        echo -e "    ${GREEN}Piper TTS already installed.${NC}"
    fi

    # Voci Italiane Piper
    VOICES_DIR="/usr/share/piper/voices"
    $SUDO mkdir -p "$VOICES_DIR"

    for voice in "it_IT-paola-medium" "it_IT-riccardo-medium"; do
        ONNX="$VOICES_DIR/${voice}.onnx"
        if [ ! -f "$ONNX" ]; then
            echo -e "    ${YELLOW}Downloading voice model: $voice ...${NC}"
            HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/${voice}"
            $SUDO curl -sL "${HF_BASE}/${voice}.onnx" -o "$ONNX" && \
            $SUDO curl -sL "${HF_BASE}/${voice}.json" -o "$VOICES_DIR/${voice}.json" 2>/dev/null || true
            $SUDO chmod 644 "$ONNX" 2>/dev/null || true
            if [ -f "$ONNX" ]; then
                echo -e "    ${GREEN}Voice model $voice ready.${NC}"
            else
                echo -e "    ${RED}Failed to download $voice${NC}"
            fi
        else
            echo -e "    ${GREEN}Voice model $voice already present.${NC}"
        fi
    done
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 3: Redis (JWT blacklist + rate limiting)
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_REDIS" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [3/9] Configuring Redis...${NC}"

    if command -v redis-server &>/dev/null; then
        $SUDO systemctl enable redis-server 2>/dev/null || true
        $SUDO systemctl start redis-server 2>/dev/null || true
        # Redis security: bind localhost only
        $SUDO sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf 2>/dev/null || true
        $SUDO sed -i 's/^protected-mode .*/protected-mode yes/' /etc/redis/redis.conf 2>/dev/null || true
        $SUDO systemctl restart redis-server 2>/dev/null || true
        echo -e "    ${GREEN}Redis running on localhost:6379${NC}"
    else
        echo -e "    ${RED}redis-server not found, install manually.${NC}"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 4: ClamAV (antivirus per upload)
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_CLAMAV" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [4/9] Configuring ClamAV...${NC}"

    if command -v clamd &>/dev/null || command -v clamdscan &>/dev/null; then
        # Ferma freshclam se in esecuzione per evitare conflitto
        $SUDO systemctl stop clamav-freshclam 2>/dev/null || true
        $SUDO ldconfig 2>/dev/null || true
        $SUDO freshclam --quiet || true
        $SUDO systemctl start clamav-freshclam 2>/dev/null || true

        $SUDO systemctl enable clamav-daemon 2>/dev/null || true
        $SUDO systemctl start clamav-daemon 2>/dev/null || true
        echo -e "    ${GREEN}ClamAV installed. Aggiornamento definizioni in corso...${NC}"
    else
        echo -e "    ${RED}ClamAV not found. Install with: apt-get install clamav clamav-daemon${NC}"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 5: Apache reverse proxy + HTTPS
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_APACHE" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [5/9] Configuring Apache...${NC}"

    # Abilita moduli necessari
    $SUDO a2enmod proxy proxy_http proxy_wstunnel ssl headers rewrite 2>/dev/null || true

    # Crea configurazione virtual host
    APACHE_SITE="/etc/apache2/sites-available/chatai.conf"

    SERVER_NAME="${DOMAIN:-localhost}"

    if [ -n "$DOMAIN" ]; then
        PROTO="https"
        WS_PROTO="wss"
        APCHE_SSL=":443"
        # Configurazione con SSL
        $SUDO tee "$APACHE_SITE" > /dev/null <<APACHEEOF
<VirtualHost *:80>
    ServerName $SERVER_NAME
    Redirect permanent / https://$SERVER_NAME/
</VirtualHost>

<VirtualHost *:443>
    ServerName $SERVER_NAME

    SSLEngine On
    SSLCertificateFile /etc/letsencrypt/live/$SERVER_NAME/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/$SERVER_NAME/privkey.pem

    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "no-referrer"
    Header always set Permissions-Policy "microphone=(), camera=(), geolocation=()"

    # Limiti upload
    LimitRequestBody 26214400
    LimitXMLRequestBody 26214400

    # Proxy verso backend Flask
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    # WebSocket proxy
    ProxyPass /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPassReverse /socket.io/ ws://127.0.0.1:5000/socket.io/

    # Log
    ErrorLog \${APACHE_LOG_DIR}/chatai_error.log
    CustomLog \${APACHE_LOG_DIR}/chatai_access.log combined
</VirtualHost>
APACHEEOF
        LE_READY=true
    else
        PROTO="http"
        WS_PROTO="ws"
        # Configurazione senza SSL
        $SUDO tee "$APACHE_SITE" > /dev/null <<APACHEEOF
<VirtualHost *:80>
    ServerName $SERVER_NAME

    # Security headers (solo per HTTP, ma meglio di niente)
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set X-XSS-Protection "1; mode=block"

    # Limiti upload
    LimitRequestBody 26214400
    LimitXMLRequestBody 26214400

    # Proxy verso backend Flask
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    # WebSocket proxy
    ProxyPass /socket.io/ ws://127.0.0.1:5000/socket.io/
    ProxyPassReverse /socket.io/ ws://127.0.0.1:5000/socket.io/

    # Log
    ErrorLog \${APACHE_LOG_DIR}/chatai_error.log
    CustomLog \${APACHE_LOG_DIR}/chatai_access.log combined
</VirtualHost>
APACHEEOF
        LE_READY=false
    fi

    # Disabilita default site, abilita chatai
    $SUDO a2dissite 000-default.conf 2>/dev/null || true
    $SUDO a2ensite chatai.conf 2>/dev/null || true
    $SUDO systemctl reload apache2 2>/dev/null || true

    echo -e "    ${GREEN}Apache configurato: $APACHE_SITE${NC}"

    # Let's Encrypt
    if [ "$SKIP_LETSENCRYPT" = false ] && [ -n "$DOMAIN" ] && [ -n "$EMAIL" ]; then
        echo ""
        echo -e "${YELLOW}>>> [5b/9] Let's Encrypt HTTPS...${NC}"

        $SUDO apt-get install -y -qq certbot python3-certbot-apache 2>/dev/null || true

        if command -v certbot &>/dev/null; then
            $SUDO certbot --apache -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || \
                echo -e "${YELLOW}Certbot non è riuscito. Prova manualmente.${NC}"
            echo -e "    ${GREEN}HTTPS configurato per $DOMAIN${NC}"
        else
            echo -e "    ${YELLOW}certbot non installato.${NC}"
        fi
    elif [ -n "$DOMAIN" ] && [ -z "$EMAIL" ]; then
        echo -e "    ${YELLOW}Specifica --email per Let's Encrypt. Salta HTTPS.${NC}"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 6: JWT Secret + .env configuration
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> [6/9] JWT Secret & API Key Configuration...${NC}"

ENV_FILE="$ROOT_DIR/backend/.env"
ENV_EXAMPLE="$ROOT_DIR/backend/.env.example"

# Crea .env se non esiste
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        touch "$ENV_FILE"
    fi
fi

# Genera JWT_SECRET sicuro
if grep -q "^JWT_SECRET=changeme_in_production" "$ENV_FILE" 2>/dev/null || \
   ! grep -q "^JWT_SECRET=" "$ENV_FILE" 2>/dev/null; then
    NEW_SECRET=$(openssl rand -hex 64)
    if grep -q "^JWT_SECRET=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" "$ENV_FILE"
    else
        echo "JWT_SECRET=$NEW_SECRET" >> "$ENV_FILE"
    fi
    echo -e "    ${GREEN}JWT_SECRET generato (64 byte hex).${NC}"
else
    echo -e "    ${GREEN}JWT_SECRET già configurato.${NC}"
fi

# Assicura REDIS_URL
if ! grep -q "^REDIS_URL=" "$ENV_FILE" 2>/dev/null; then
    REDIS_PASS=$(redis-cli CONFIG GET requirepass 2>/dev/null | tail -1)
    if [ -n "$REDIS_PASS" ] && [ "$REDIS_PASS" != '""' ]; then
        echo "REDIS_URL=redis://:${REDIS_PASS}@localhost:6379/0" >> "$ENV_FILE"
    else
        echo "REDIS_URL=redis://localhost:6379/0" >> "$ENV_FILE"
    fi
    echo -e "    ${GREEN}REDIS_URL configurato.${NC}"
fi

# Assicura PORT
if ! grep -q "^PORT=" "$ENV_FILE" 2>/dev/null; then
    echo "PORT=5000" >> "$ENV_FILE"
fi

# Assicura FLASK_ENV=production
if grep -q "FLASK_ENV=development" "$ENV_FILE" 2>/dev/null; then
    sed -i "s/FLASK_ENV=development/FLASK_ENV=production/" "$ENV_FILE"
elif ! grep -q "^FLASK_ENV=" "$ENV_FILE" 2>/dev/null; then
    echo "FLASK_ENV=production" >> "$ENV_FILE"
fi

# Carica .env
set -a
source "$ENV_FILE"
set +a

echo -e "    Config file: $ENV_FILE"

_prompt_key() {
    local var_name="$1"
    local display_name="$2"
    local current_val="${!var_name:-}"
    if [ -n "$current_val" ]; then
        echo -e "    ${GREEN}$display_name already configured.${NC}"
        return
    fi
    echo -e "    ${YELLOW}$display_name not configured.${NC}"
    read -p "    Enter $display_name (or press Enter to skip): " key_val
    if [ -n "$key_val" ]; then
        echo "$var_name=$key_val" >> "$ENV_FILE"
        echo -e "    ${GREEN}$display_name saved.${NC}"
    fi
}

# Chiavi API — l'utente le configura tramite prompt
# Provider esistenti
_prompt_key "GEMINI_API_KEY" "Google Gemini API Key"
_prompt_key "GROQ_API_KEY" "Groq API Key"
_prompt_key "OPENROUTER_API_KEY" "OpenRouter API Key"
_prompt_key "MISTRAL_API_KEY" "Mistral AI API Key"
_prompt_key "HUGGINGFACE_API_KEY" "Hugging Face API Key"
_prompt_key "GITHUB_TOKEN" "GitHub Token"
_prompt_key "OPENAI_API_KEY" "OpenAI API Key"
_prompt_key "ANTHROPIC_API_KEY" "Anthropic API Key"

# Nuovi provider (opzionali — inserisci solo quelli che vuoi usare)
echo -e "\n    ${BLUE}--- Nuovi Provider AI (opzionali) ---${NC}"
echo -e "    ${YELLOW}Premi Invio per saltare. Puoi configurarli dopo in .env${NC}\n"
_prompt_key "TOGETHER_API_KEY" "Together AI API Key"
_prompt_key "CEREBRAS_API_KEY" "Cerebras API Key"
_prompt_key "CLOUDFLARE_API_TOKEN" "Cloudflare Workers AI Token"
_prompt_key "CLOUDFLARE_ACCOUNT_ID" "Cloudflare Account ID"
_prompt_key "COHERE_API_KEY" "Cohere API Key"
_prompt_key "DEEPINFRA_API_KEY" "DeepInfra API Key"
_prompt_key "FIREWORKS_API_KEY" "Fireworks AI API Key"
_prompt_key "SAMBANOVA_API_KEY" "SambaNova Cloud API Key"
_prompt_key "NEBIUS_API_KEY" "Nebius AI Studio API Key"
_prompt_key "NOVITA_API_KEY" "Novita AI API Key"
_prompt_key "INFERENCE_API_KEY" "Inference.net API Key"
_prompt_key "LLAMACPP_API_KEY" "llama.cpp API Key (opzionale, solo se usi autenticazione)"

# Google Client ID (obbligatorio per Google Sign-In)
_prompt_key "GOOGLE_CLIENT_ID" "Google Client ID (da Google Cloud Console)"
_prompt_key "MASTER_KEY" "Master Key (64 char esadecimale per crittografia dati)"
_prompt_key "SENTRY_DSN" "Sentry DSN (opzionale, per monitoring errori)"
_prompt_key "TELEGRAM_BOT_TOKEN" "Telegram Bot Token (opzionale, per alert)"
_prompt_key "TELEGRAM_CHAT_ID" "Telegram Chat ID (opzionale, per alert)"

# Auto-refresh TTL
if ! grep -q "^MODEL_REFRESH_TTL=" "$ENV_FILE" 2>/dev/null; then
    echo "MODEL_REFRESH_TTL=3600" >> "$ENV_FILE"
fi
if ! grep -q "^EVENTLET_NO_GREENDNS=" "$ENV_FILE" 2>/dev/null; then
    echo "EVENTLET_NO_GREENDNS=yes" >> "$ENV_FILE"
fi

set -a
source "$ENV_FILE"
set +a

if [ "$ENV_ONLY" = true ]; then
    echo ""
    echo -e "${GREEN}=== Configurazione ambiente completata ===${NC}"
    echo -e "    File: $ENV_FILE"
    exit 0
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 7: Ollama + modelli AI
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_OLLAMA" = false ] && [ "$SKIP_PY" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [7/9] Setting up Ollama AI models...${NC}"

    if ! command -v ollama &>/dev/null; then
        echo -e "    ${YELLOW}Installing Ollama...${NC}"
        curl -fsSL https://ollama.com/install.sh | sh
        # Fix ownership so systemd can run Ollama as user ollama
        $SUDO chown -R ollama:ollama /usr/share/ollama/.ollama 2>/dev/null || true
        $SUDO systemctl enable ollama 2>/dev/null || true
        $SUDO systemctl start ollama 2>/dev/null || true
        echo -e "    ${GREEN}Ollama installed.${NC}"
    else
        OLLAMA_VER=$(ollama --version 2>/dev/null || echo "version unknown")
        echo -e "    ${GREEN}Ollama already installed: $OLLAMA_VER${NC}"
    fi

    # Ensure Ollama is running (fixes stale llama-server processes)
    echo -e "    ${YELLOW}Checking Ollama API...${NC}"
    if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo -e "    ${YELLOW}Ollama not responding — fixing permissions and restarting...${NC}"
        $SUDO chown -R ollama:ollama /usr/share/ollama/.ollama 2>/dev/null || true
        $SUDO systemctl restart ollama 2>/dev/null || true
        # Wait up to 15s for Ollama to start
        for i in $(seq 1 15); do
            if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        # If still not up, start manually as root fallback
        if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            echo -e "    ${YELLOW}Starting Ollama manually...${NC}"
            pkill -x ollama 2>/dev/null || true
            sleep 1
            ollama serve > /tmp/ollama_serve.log 2>&1 &
            disown
            sleep 3
        fi
    fi
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo -e "    ${GREEN}Ollama API ready.${NC}"
    else
        echo -e "    ${RED}Ollama API not available — skipping model pull.${NC}"
    fi

    echo -e "    Models to download: ${BLUE}$OLLAMA_MODELS${NC}"
    for model in $OLLAMA_MODELS; do
        if curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | grep -q "\"$model\"" 2>/dev/null; then
            echo -e "    ${GREEN}Model '$model' already downloaded.${NC}"
        else
            echo -e "    ${YELLOW}Downloading model '$model' (this may take a while)...${NC}"
            ollama pull "$model" 2>&1 | tail -1
            echo -e "    ${GREEN}Model '$model' ready.${NC}"
        fi
    done
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 8: DNS (fallback a Google DNS per evitare timeout risoluzione)
# ══════════════════════════════════════════════════════════════════
if command -v resolvectl &>/dev/null; then
    echo ""
    echo -e "${YELLOW}>>> Configuring DNS fallback...${NC}"
    # Aggiunge Google DNS come fallback per i provider esterni (OpenRouter, Mistral, etc.)
    IFACE=$(ip -o link show | awk -F': ' '/state UP/ && !/docker|lo/ {print $2; exit}')
    if [ -n "$IFACE" ]; then
        CURRENT_DNS=$(resolvectl dns "$IFACE" 2>/dev/null | grep -v "^$IFACE:" | tr -d '\n')
        if ! echo "$CURRENT_DNS" | grep -q "8.8.8.8"; then
            $SUDO resolvectl dns "$IFACE" $CURRENT_DNS 8.8.8.8 8.8.4.4 2>/dev/null || true
        fi
    fi
    # Drop-in persistente per FallbackDNS
    $SUDO mkdir -p /etc/systemd/resolved.conf.d
    echo -e "[Resolve]\nFallbackDNS=8.8.8.8 8.8.4.4 1.1.1.1\nCache=yes" | \
        $SUDO tee /etc/systemd/resolved.conf.d/dns.conf > /dev/null
    $SUDO systemctl restart systemd-resolved 2>/dev/null || true
    echo -e "    ${GREEN}DNS fallback configurato (Google DNS 8.8.8.8 + Cloudflare 1.1.1.1).${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# PASSO 9: Firewall (UFW)
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_FIREWALL" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> [9/9] Configuring firewall...${NC}"

    if command -v ufw &>/dev/null; then
        $SUDO ufw --force reset 2>/dev/null || true
        $SUDO ufw default deny incoming
        $SUDO ufw default allow outgoing
        $SUDO ufw allow ssh
        $SUDO ufw allow 5000/tcp
        if [ -n "$DOMAIN" ]; then
            $SUDO ufw allow 80/tcp
            $SUDO ufw allow 443/tcp
        else
            $SUDO ufw allow 80/tcp
        fi
        $SUDO ufw --force enable 2>/dev/null || true
        echo -e "    ${GREEN}Firewall configurato.${NC}"
    else
        echo -e "    ${YELLOW}ufw non installato. Installa con: apt-get install ufw${NC}"
    fi
fi

# ══════════════════════════════════════════════════════════════════
# Fail2Ban per brute-force su /auth/login
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> Configuring Fail2ban...${NC}"

if command -v fail2ban-server &>/dev/null; then
    $SUDO cp "$ROOT_DIR/backend/fail2ban-chatai.conf" /etc/fail2ban/filter.d/chatai.conf 2>/dev/null || true
    $SUDO cp "$ROOT_DIR/backend/fail2ban-jail.conf" /etc/fail2ban/jail.d/chatai.conf 2>/dev/null || true
    $SUDO systemctl enable fail2ban 2>/dev/null || true
    $SUDO systemctl restart fail2ban 2>/dev/null || true
    echo -e "    ${GREEN}Fail2ban configurato per /auth/login${NC}"
else
    echo -e "    ${YELLOW}fail2ban non installato, salta configurazione.${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# Backup automatico DB (cron)
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> Configuring backup cron...${NC}"

BACKUP_SCRIPT="$ROOT_DIR/backend/backup.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
    chmod +x "$BACKUP_SCRIPT"
    CRON_LINE="0 3 * * * $SUDO -u chatai $BACKUP_SCRIPT"
    (crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT"; echo "$CRON_LINE") | crontab - 2>/dev/null || true
    echo -e "    ${GREEN}Backup cron: ogni giorno alle 3:00${NC}"
    echo -e "    ${GREEN}Retention: 30 giorni${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# Systemd service per backend Flask
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> Configuring systemd service...${NC}"

SERVICE_FILE="/etc/systemd/system/chatai.service"

$SUDO tee "$SERVICE_FILE" > /dev/null <<SERVICEEOF
[Unit]
Description=ChatAI Backend
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=chatai
Group=chatai
WorkingDirectory=$ROOT_DIR/backend
ExecStart=$ROOT_DIR/backend/venv/bin/python3 -m uvicorn app:app --host 127.0.0.1 --port 5000 --workers 1
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=3
TimeoutStartSec=120
EnvironmentFile=$ROOT_DIR/backend/.env
StandardOutput=append:/var/log/chatai.log
StandardError=append:/var/log/chatai.log

# Hardening
NoNewPrivileges=true
ReadWritePaths=$ROOT_DIR/backend $ROOT_DIR/backend/static/uploads /tmp/chatai_uploads /var/log/chatai.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

$SUDO systemctl daemon-reload 2>/dev/null || true
echo -e "    ${GREEN}Service file: $SERVICE_FILE${NC}"

# ══════════════════════════════════════════════════════════════════
# Android APK Build
# ══════════════════════════════════════════════════════════════════
if [ "$SKIP_APK" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> Building Android AAB + APK (Play Store + direct install)...${NC}"

    if [ ! -f gradlew ]; then
        echo -e "${RED}ERROR: gradlew not found${NC}"
        exit 1
    fi
    chmod +x gradlew

    if [ -z "${ANDROID_HOME:-}" ]; then
        for dir in "$HOME/Android/Sdk" /opt/android-sdk /usr/lib/android-sdk; do
            if [ -d "$dir" ]; then
                export ANDROID_HOME="$dir"
                break
            fi
        done
        if [ -z "${ANDROID_HOME:-}" ]; then
            echo -e "${RED}ERROR: ANDROID_HOME not set. Set it and try again.${NC}"
            exit 1
        fi
    fi

    if [ ! -f "$ROOT_DIR/local.properties" ]; then
        echo "sdk.dir=$ANDROID_HOME" > "$ROOT_DIR/local.properties"
    fi

    echo -e "    ANDROID_HOME=$ANDROID_HOME"
    echo -e "    Java: $(java -version 2>&1 | head -1)"
    echo ""

    # Build AAB (Play Store)
    echo -e "    ${YELLOW}Building AAB...${NC}"
    ./gradlew bundleRelease --no-daemon --console=plain
    AAB_FILE="$ROOT_DIR/app/build/outputs/bundle/release/app-release.aab"

    # Build APK (direct install)
    echo -e "    ${YELLOW}Building APK...${NC}"
    ./gradlew assembleRelease --no-daemon --console=plain
    APK_FILE="$ROOT_DIR/app/build/outputs/apk/release/app-release.apk"

    if [ -f "$AAB_FILE" ]; then
        AAB_SIZE=$(stat -c%s "$AAB_FILE" 2>/dev/null || stat -f%z "$AAB_FILE" 2>/dev/null)
        AAB_SIZE_MB=$(echo "scale=1; $AAB_SIZE/1048576" | bc)
        echo -e "    ${GREEN}AAB: $AAB_FILE (${AAB_SIZE_MB}MB)${NC}"
    else
        echo -e "${RED}AAB build failed!${NC}"
        exit 1
    fi

    if [ -f "$APK_FILE" ]; then
        APK_SIZE=$(stat -c%s "$APK_FILE" 2>/dev/null || stat -f%z "$APK_FILE" 2>/dev/null)
        APK_SIZE_MB=$(echo "scale=1; $APK_SIZE/1048576" | bc)
        echo -e "    ${GREEN}APK: $APK_FILE (${APK_SIZE_MB}MB)${NC}"
    else
        echo -e "    ${YELLOW}APK build failed (AAB OK).${NC}"
    fi

    echo ""
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${GREEN} BUILD SUCCESSFUL${NC}"
    echo -e "${GREEN} AAB → Google Play Console: $AAB_FILE${NC}"
    [ -f "$APK_FILE" ] && echo -e "${GREEN} APK → Direct install:     $APK_FILE${NC}"
    echo -e "${GREEN}==================================================${NC}"
fi

# ══════════════════════════════════════════════════════════════════
# Avvio server
# ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}>>> Starting server...${NC}"

PORT=${PORT:-5000}

# Usa systemd se disponibile
if command -v systemctl &>/dev/null; then
    $SUDO systemctl daemon-reload 2>/dev/null || true
    $SUDO systemctl enable chatai 2>/dev/null || true
    $SUDO systemctl restart chatai 2>/dev/null || true
    echo -e "    ${GREEN}Service avviato con systemd.${NC}"
else
    echo -e "    ${YELLOW}systemctl non disponibile, avvio diretto...${NC}"
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    cd "$ROOT_DIR/backend"
    nohup venv/bin/python3 server.py > /tmp/chatai.log 2>&1 &
    echo $! > /tmp/chatai.pid
    cd "$ROOT_DIR"
    echo -e "    ${GREEN}Server started in background (PID $(cat /tmp/chatai.pid))${NC}"
fi

echo -e "    ${YELLOW}Waiting for server (max 60s)...${NC}"
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:${PORT}/ > /dev/null 2>&1; then
        echo -e "    ${GREEN}Server running on http://127.0.0.1:${PORT} (${i}s)${NC}"
        if [ -n "$DOMAIN" ]; then
            echo -e "    ${GREEN}Accessibile via https://${DOMAIN}${NC}"
        fi
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then echo -e "    ${YELLOW}Waiting... ${i}s${NC}"; fi
    sleep 1
    if [ "$i" -eq 60 ]; then
        echo -e "    ${YELLOW}Server non raggiungibile dopo 60s.${NC}"
        echo -e "    ${YELLOW}Controlla i log: journalctl -u chatai -n 50${NC}"
    fi
done

echo ""
echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} Build complete!${NC}"
echo -e "${BLUE}==================================================${NC}"
echo ""
echo "  Backend:    http://127.0.0.1:${PORT}"
if [ -n "$DOMAIN" ]; then
    echo "  Pubblico:   https://${DOMAIN}"
fi
echo "  Apache:     $(which apache2 2>/dev/null && echo 'configurato' || echo 'non installato')"
REDIS_PASS=$(grep '^REDIS_URL=' "$ENV_FILE" 2>/dev/null | sed 's|.*:\([^@]*\)@.*|\1|')
echo "  Redis:      $(REDISCLI_AUTH="$REDIS_PASS" redis-cli ping 2>/dev/null || echo 'non raggiungibile')"
echo "  ClamAV:     $(command -v clamdscan && echo 'installato' || echo 'non installato')"
echo "  DNS:        $(resolvectl dns $(ip -o link show | awk -F': ' '/state UP/ && !/docker|lo/ {print $2; exit}') 2>/dev/null | tr '\n' ' ' || echo 'non configurato')"
echo "  Firewall:   $(ufw status 2>/dev/null | head -1 || echo 'non configurato')"
echo "  JWT_SECRET: $(grep '^JWT_SECRET=' "$ROOT_DIR/backend/.env" 2>/dev/null | cut -d= -f2 | head -c 16)..."
echo ""
echo "  Log:  journalctl -u chatai -f"
echo "  Stop: systemctl stop chatai"
echo "  Test: curl -s http://127.0.0.1:${PORT}/"
