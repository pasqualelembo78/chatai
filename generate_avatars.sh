#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$ROOT_DIR/backend/avatar_tool.py"
ENV_FILE="$ROOT_DIR/backend/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  ChatAI - Generatore Avatar & Biografie${NC}"
echo -e "${BLUE}====================================================${NC}"

# ─── Verifica dipendenze ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[1/4] Verifica dipendenze...${NC}"

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}python3 non trovato.${NC}"
    exit 1
fi

VENV_DIR="$ROOT_DIR/backend/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "    Creazione virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install requests pillow python-dotenv -q 2>&1 | tail -1
echo -e "    ${GREEN}Dipendenze pronte.${NC}"

# ─── Carica API keys ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/4] Caricamento API keys...${NC}"

GROQ_KEY=""
PEXELS_KEY=""
POLLINATIONS_KEY=""

if [ -f "$ENV_FILE" ]; then
    GROQ_KEY=$(grep "^GROQ_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "')
    PEXELS_KEY=$(grep "^PEXELS_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "')
    POLLINATIONS_KEY=$(grep "^POLLINATIONS_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' "')
fi

if [ -z "$GROQ_KEY" ]; then
    GROQ_KEY="${GROQ_API_KEY:-}"
fi
if [ -z "$PEXELS_KEY" ]; then
    PEXELS_KEY="${PEXELS_API_KEY:-}"
fi
if [ -z "$POLLINATIONS_KEY" ]; then
    POLLINATIONS_KEY="${POLLINATIONS_API_KEY:-}"
fi

if [ -n "$POLLINATIONS_KEY" ]; then
    echo -e "    ${GREEN}Pollinations: ${POLLINATIONS_KEY:0:12}...${NC}"
else
    echo -e "    ${YELLOW}Pollinations: non trovata (usa anonymous)${NC}"
fi

if [ -n "$PEXELS_KEY" ]; then
    echo -e "    ${GREEN}Pexels: ${PEXELS_KEY:0:12}...${NC}"
else
    echo -e "    ${YELLOW}Pexels: non trovata (usa fallback)${NC}"
fi

if [ -n "$GROQ_KEY" ]; then
    echo -e "    ${GREEN}Groq: ${GROQ_KEY:0:12}...${NC}"
else
    echo -e "    ${YELLOW}Groq: non trovata${NC}"
fi

# ─── Scegli azione ────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/4] Scegli:${NC}"
echo -e "    ${CYAN}1)${NC} Genera tutto (avatar + bio + scenario)"
echo -e "    ${CYAN}2)${NC} Mostra stato"
echo -e "    ${CYAN}3)${NC} Esci"
read -p "    Scegli [1-3] (default 1): " MODE

case "${MODE:-1}" in
    1) ACTION="generate" ;;
    2) ACTION="status" ;;
    3) exit 0 ;;
    *) ACTION="generate" ;;
esac

# ─── Esegui ───────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/4] Esecuzione...${NC}"

export GROQ_API_KEY="$GROQ_KEY"
export PEXELS_API_KEY="$PEXELS_KEY"
export POLLINATIONS_API_KEY="$POLLINATIONS_KEY"

if [ "$ACTION" = "status" ]; then
    "$VENV_DIR/bin/python3" "$TOOL" --status
    exit 0
fi

echo -e "    Quanti personaggi generare?"
echo -e "    ${CYAN}0 = TUTTI${NC} (può volerci tempo)"
read -p "    Numero (default 50): " LIMIT
LIMIT="${LIMIT:-50}"

echo ""
echo -e "    ${GREEN}>>> GENERAZIONE COMPLETA: avatar + bio + scenario <<<${NC}"
echo ""

"$VENV_DIR/bin/python3" "$TOOL" \
    --generate-all \
    --model pollinations \
    --bio \
    --limit "$LIMIT"

# ─── Riepilogo ────────────────────────────────────────────────
echo ""
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}  Operazione completata!${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""
echo -e "  ${CYAN}Rilancia per continuare o vedere stato:${NC}"
echo -e "    bash generate_avatars.sh"
echo ""
