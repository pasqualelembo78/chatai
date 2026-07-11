#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$ROOT_DIR/backend/avatar_tool.py"
TOKEN_FILE="$ROOT_DIR/backend/.hf_token"
ENV_FILE="$ROOT_DIR/backend/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  ChatAI - Generatore Avatar & Biografie${NC}"
echo -e "${BLUE}  Sistema gratuito: Pexels (foto reali) + Groq${NC}"
echo -e "${BLUE}====================================================${NC}"

# ─── 1. Verifica dipendenze ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/5] Verifica dipendenze...${NC}"

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}python3 non trovato. Installa Python 3.${NC}"
    exit 1
fi

VENV_DIR="$ROOT_DIR/backend/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "    Creazione virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Installa dipendenze minime
pip install requests pillow python-dotenv -q 2>&1 | tail -1
echo -e "    ${GREEN}Dipendenze pronte.${NC}"

# ─── 2. Carica API keys ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/5] Caricamento API keys...${NC}"

# Carica GROQ_API_KEY e PEXELS_API_KEY da .env
GROQ_KEY=""
PEXELS_KEY=""

if [ -f "$ENV_FILE" ]; then
    GROQ_KEY=$(grep "^GROQ_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "')
    PEXELS_KEY=$(grep "^PEXELS_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "')
fi

if [ -z "$GROQ_KEY" ]; then
    GROQ_KEY="${GROQ_API_KEY:-}"
fi
if [ -z "$PEXELS_KEY" ]; then
    PEXELS_KEY="${PEXELS_API_KEY:-}"
fi

if [ -n "$PEXELS_KEY" ]; then
    echo -e "    ${GREEN}Pexels API key: ${PEXELS_KEY:0:12}...${NC}"
else
    echo -e "    ${YELLOW}PEXELS_API_KEY non trovata. Usa Pollinations.AI come fallback.${NC}"
fi

if [ -n "$GROQ_KEY" ]; then
    echo -e "    ${GREEN}Groq API key: ${GROQ_KEY:0:12}...${NC}"
else
    echo -e "    ${YELLOW}GROQ_API_KEY non trovata. Biografie non disponibili.${NC}"
fi

# ─── 3. Modalità ────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/5] Scegli modalita:${NC}"
echo -e "    ${CYAN}1)${NC} Genera avatar mancanti (Pexels + fallback)"
echo -e "    ${CYAN}2)${NC} Genera biografie italiane (Groq 70B)"
echo -e "    ${CYAN}3)${NC} Genera avatar + biografie (completo)"
echo -e "    ${CYAN}4)${NC} Genera icone categorie"
echo -e "    ${CYAN}5)${NC} Elenca personaggi senza avatar"
echo -e "    ${CYAN}6)${NC} Test generazione singola"
echo -e "    ${CYAN}7)${NC} Esci"
read -p "    Scegli [1-7] (default 3): " MODE

case "${MODE:-3}" in
    1) ACTION="avatars" ;;
    2) ACTION="bios" ;;
    3) ACTION="both" ;;
    4) ACTION="icons" ;;
    5) ACTION="list" ;;
    6) ACTION="test" ;;
    *) ACTION="both" ;;
esac

# ─── 4. Limiti ──────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/5] Limiti di generazione:${NC}"

if [ "$ACTION" = "avatars" ] || [ "$ACTION" = "both" ]; then
    echo -e "    ${CYAN}Quanti avatar generare?${NC}"
    echo -e "    Pexels limiti:"
    echo -e "      200 req/ora, 20000 req/mese (gratis)"
    echo -e "      Foto reali di fotografi professionisti"
    echo -e "    + Fallback: Pollinations.AI, ThisPersonDoesNotExist, PrAvatar, DiceBear"
    read -p "    Numero (default 50, 0=tutti): " AVATAR_LIMIT
    AVATAR_LIMIT="${AVATAR_LIMIT:-50}"
else
    AVATAR_LIMIT=0
fi

if [ "$ACTION" = "bios" ] || [ "$ACTION" = "both" ]; then
    echo -e "    ${CYAN}Quante biografie generare?${NC}"
    echo -e "    (Groq: 1000/giorno, ~30 RPM)"
    read -p "    Numero (default 50, 0=tutti): " BIO_LIMIT
    BIO_LIMIT="${BIO_LIMIT:-50}"
else
    BIO_LIMIT=0
fi

# ─── 5. Esegui ──────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] Esecuzione...${NC}"

export GROQ_API_KEY="$GROQ_KEY"
export PEXELS_API_KEY="$PEXELS_KEY"

case "$ACTION" in
    avatars)
        echo -e "    Generazione avatar con Pexels (foto reali)..."
        "$VENV_DIR/bin/python3" "$TOOL" \
            --generate-all \
            --model pexels \
            --limit "$AVATAR_LIMIT"
        ;;
    bios)
        echo -e "    Generazione biografie italiane con Groq..."
        "$VENV_DIR/bin/python3" "$TOOL" \
            --generate-all \
            --bio \
            --limit "$BIO_LIMIT"
        ;;
    both)
        echo -e "    Generazione avatar + biografie..."
        "$VENV_DIR/bin/python3" "$TOOL" \
            --generate-all \
            --model pexels \
            --bio \
            --avatar-limit "$AVATAR_LIMIT" \
            --bio-limit "$BIO_LIMIT"
        ;;
    icons)
        echo -e "    Generazione icone categorie..."
        "$VENV_DIR/bin/python3" "$TOOL" \
            --generate-category-icons \
            --model pexels
        ;;
    list)
        "$VENV_DIR/bin/python3" "$TOOL" --list-missing
        ;;
    test)
        echo -e "    Test generazione singola..."
        read -p "    ID personaggio (default: sofia): " TEST_ID
        TEST_ID="${TEST_ID:-sofia}"
        "$VENV_DIR/bin/python3" "$TOOL" \
            --generate "$TEST_ID" \
            --model pexels \
            --bio
        ;;
    *)
        echo -e "    ${YELLOW}Nessuna operazione.${NC}"
        exit 0
        ;;
esac

# ─── Riepilogo ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}  Operazione completata!${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""
echo -e "  ${CYAN}Prossimi passi:${NC}"
echo -e "    bash generate_avatars.sh        — Rilancia il tool"
echo -e "    python3 backend/avatar_tool.py --help  — Tutte le opzioni"
echo ""
echo -e "  ${CYAN}Limiti API:${NC}"
echo -e "    Pexels: 200 req/ora, 20000 req/mese (gratis, foto reali)"
echo -e "    + Fallback: Pollinations.AI, ThisPersonDoesNotExist, PrAvatar, DiceBear"
echo -e "    Groq: 1000 richieste/giorno, 30 RPM (gratis)"
echo ""
