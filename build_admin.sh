#!/bin/bash
#
# build_admin.sh — Build script per Admin Panel Android
#
# Costruisce l'APK dell'admin panel e lo configura per connettersi
# al server ChatAI già esistente.
#
# Usage:
#   ./build_admin.sh [options]
#
# Options:
#   --server-url "http://..."   URL del server ChatAI (default: http://82.165.218.56)
#   --skip-apk                  Salta build APK
#   --install                   Installa APK su dispositivo connesso (adb)
#   --release                   Build release (default: debug)
#   -h, --help                  Mostra aiuto
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ─── Help ────────────────────────────────────────────────────────
if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
    echo ""
    echo "Usage: ./build_admin.sh [options]"
    echo ""
    echo "Options:"
    echo "  --server-url \"http://...\"  Server URL (default: http://82.165.218.56)"
    echo "  --skip-apk               Skip Android APK build"
    echo "  --install                Install APK on connected device via adb"
    echo "  --release                Build release APK (default: debug)"
    echo "  -h, --help               Show this help"
    echo ""
    exit 0
fi

# ─── Configurazione colori ─────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} ChatAI Admin Panel - Build Script${NC}"
echo -e "${BLUE}==================================================${NC}"

# ─── Parsing argomenti ──────────────────────────────────────────
SKIP_APK=false
INSTALL_APK=false
BUILD_RELEASE=false
SERVER_URL="http://82.165.218.56"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-url) SERVER_URL="$2"; shift 2;;
        --skip-apk) SKIP_APK=true; shift;;
        --install) INSTALL_APK=true; shift;;
        --release) BUILD_RELEASE=true; shift;;
        *) echo -e "${RED}Opzione sconosciuta: $1${NC}"; exit 1;;
    esac
done

# ─── Verifica branch admin ──────────────────────────────────────
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$CURRENT_BRANCH" != "admin" ]; then
    echo -e "${YELLOW}Attenzione: branch corrente è '$CURRENT_BRANCH', non 'admin'.${NC}"
    echo -e "${YELLOW}Passa al branch admin con: git checkout admin${NC}"
    read -p "Continuare comunque? (s/N): " confirm
    if [ "$confirm" != "s" ] && [ "$confirm" != "S" ]; then
        exit 1
    fi
fi

# ─── Verifica Android SDK ───────────────────────────────────────
if [ "$SKIP_APK" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> Verifica Android SDK...${NC}"

    if [ -z "${ANDROID_HOME:-}" ]; then
        for dir in "$HOME/Android/Sdk" /opt/android-sdk /usr/lib/android-sdk /root/Android/Sdk; do
            if [ -d "$dir" ]; then
                export ANDROID_HOME="$dir"
                break
            fi
        done
        if [ -z "${ANDROID_HOME:-}" ]; then
            echo -e "${RED}ERROR: ANDROID_HOME non impostato.${NC}"
            echo -e "${YELLOW}Impostalo con: export ANDROID_HOME=/percorso/android-sdk${NC}"
            exit 1
        fi
    fi

    if [ ! -f "$ROOT_DIR/local.properties" ]; then
        echo "sdk.dir=$ANDROID_HOME" > "$ROOT_DIR/local.properties"
    fi

    echo -e "    ${GREEN}ANDROID_HOME: $ANDROID_HOME${NC}"
    echo -e "    ${GREEN}Java: $(java -version 2>&1 | head -1)${NC}"
fi

# ─── Aggiorna Constants.java con server URL ─────────────────────
echo ""
echo -e "${YELLOW}>>> Configurazione server URL: $SERVER_URL${NC}"

CONSTANTS_FILE="$ROOT_DIR/app/src/main/java/com/intelligame/chatai/Constants.java"
if [ -f "$CONSTANTS_FILE" ]; then
    sed -i "s|DEFAULT_SERVER_URL = \".*\"|DEFAULT_SERVER_URL = \"$SERVER_URL\"|" "$CONSTANTS_FILE"
    echo -e "    ${GREEN}Constants.java aggiornato: $SERVER_URL${NC}"
else
    echo -e "    ${RED}Constants.java non trovato!${NC}"
    exit 1
fi

# ─── Build APK ──────────────────────────────────────────────────
if [ "$SKIP_APK" = false ]; then
    echo ""
    echo -e "${YELLOW}>>> Build Android APK...${NC}"

    chmod +x gradlew 2>/dev/null || true

    if [ "$BUILD_RELEASE" = true ]; then
        echo -e "    ${YELLOW}Building RELEASE APK...${NC}"
        ./gradlew assembleRelease --no-daemon --console=plain
        APK_FILE="$ROOT_DIR/app/build/outputs/apk/release/app-release.apk"
    else
        echo -e "    ${YELLOW}Building DEBUG APK...${NC}"
        ./gradlew assembleDebug --no-daemon --console=plain
        APK_FILE="$ROOT_DIR/app/build/outputs/apk/debug/app-debug.apk"
    fi

    if [ -f "$APK_FILE" ]; then
        APK_SIZE=$(stat -c%s "$APK_FILE" 2>/dev/null || stat -f%z "$APK_FILE" 2>/dev/null)
        APK_SIZE_MB=$(echo "scale=1; $APK_SIZE/1048576" | bc)
        echo ""
        echo -e "${GREEN}==================================================${NC}"
        echo -e "${GREEN} BUILD SUCCESSFUL${NC}"
        echo -e "${GREEN} APK: $APK_FILE (${APK_SIZE_MB}MB)${NC}"
        echo -e "${GREEN} Server: $SERVER_URL${NC}"
        echo -e "${GREEN}==================================================${NC}"
    else
        echo -e "${RED}APK build fallito!${NC}"
        exit 1
    fi

    # Install via adb
    if [ "$INSTALL_APK" = true ]; then
        echo ""
        echo -e "${YELLOW}>>> Installazione APK su dispositivo...${NC}"
        if command -v adb &>/dev/null; then
            DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep "device$" | wc -l)
            if [ "$DEVICES" -gt 0 ]; then
                adb install -r "$APK_FILE"
                echo -e "    ${GREEN}APK installato con successo!${NC}"
            else
                echo -e "    ${YELLOW}Nessun dispositivo connesso. Collega un dispositivo e riprova.${NC}"
                echo -e "    ${YELLOW}Oppure installa manualmente: adb install -r $APK_FILE${NC}"
            fi
        else
            echo -e "    ${YELLOW}adb non trovato. Installa manualmente: adb install -r $APK_FILE${NC}"
        fi
    fi
fi

echo ""
echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} Admin Panel pronto!${NC}"
echo -e "${BLUE}==================================================${NC}"
echo ""
echo "  Server URL: $SERVER_URL"
echo "  Branch:     $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'N/A')"
if [ -f "${APK_FILE:-}" ]; then
    echo "  APK:        $APK_FILE"
    echo ""
    echo "  Installa:   adb install -r $APK_FILE"
fi
echo ""
echo "  L'app chiede login con account admin/moderator."
echo "  Assicurati che il server sia attivo su: $SERVER_URL"
