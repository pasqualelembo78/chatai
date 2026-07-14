#!/bin/bash
#
# build_admin.sh — Build APK Admin Panel (signed release)
#
# Costruisce l'APK firmato dell'admin panel collegato al server
# ChatAI principale (82.165.218.56). Nessun server duplicato.
#
# Usage:
#   ./build_admin.sh [--install]
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE} ChatAI Admin Panel - Build Signed APK${NC}"
echo -e "${BLUE}==================================================${NC}"

# ─── Server URL (server principale già attivo) ──────────────────
SERVER_URL="http://82.165.218.56"
echo -e "  Server: ${GREEN}$SERVER_URL${NC}"

# ─── Aggiorna Constants.java ─────────────────────────────────────
CONSTANTS_FILE="$ROOT_DIR/app/src/main/java/com/intelligame/chatai/Constants.java"
if [ -f "$CONSTANTS_FILE" ]; then
    sed -i "s|DEFAULT_SERVER_URL = \".*\"|DEFAULT_SERVER_URL = \"$SERVER_URL\"|" "$CONSTANTS_FILE"
    echo -e "  Constants.java: ${GREEN}OK${NC}"
else
    echo -e "${RED}ERROR: Constants.java non trovato${NC}"
    exit 1
fi

# ─── Android SDK ─────────────────────────────────────────────────
if [ -z "${ANDROID_HOME:-}" ]; then
    for dir in "$HOME/Android/Sdk" /opt/android-sdk /usr/lib/android-sdk /root/Android/Sdk; do
        if [ -d "$dir" ]; then export ANDROID_HOME="$dir"; break; fi
    done
fi
if [ -z "${ANDROID_HOME:-}" ]; then
    echo -e "${RED}ERROR: ANDROID_HOME non trovato${NC}"
    exit 1
fi
echo -e "  SDK:        ${GREEN}$ANDROID_HOME${NC}"

if [ ! -f "$ROOT_DIR/local.properties" ]; then
    echo "sdk.dir=$ANDROID_HOME" > "$ROOT_DIR/local.properties"
fi

# ─── Build Signed Release APK ───────────────────────────────────
echo ""
echo -e "${YELLOW}>>> Building signed release APK...${NC}"

chmod +x gradlew 2>/dev/null || true
./gradlew assembleRelease --no-daemon --console=plain

APK_FILE="$ROOT_DIR/app/build/outputs/apk/release/app-release.apk"

if [ ! -f "$APK_FILE" ]; then
    echo -e "${RED}BUILD FALLITO${NC}"
    exit 1
fi

APK_SIZE=$(stat -c%s "$APK_FILE" 2>/dev/null || stat -f%z "$APK_FILE" 2>/dev/null)
APK_SIZE_MB=$(echo "scale=1; $APK_SIZE/1048576" | bc)

echo ""
echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN} BUILD SUCCESSFUL${NC}"
echo -e "${GREEN} APK:   $APK_FILE${NC}"
echo -e "${GREEN} Size:  ${APK_SIZE_MB}MB${NC}"
echo -e "${GREEN} Server: $SERVER_URL${NC}"
echo -e "${GREEN}==================================================${NC}"

# ─── Install opzionale ──────────────────────────────────────────
if [ "${1:-}" = "--install" ]; then
    echo ""
    echo -e "${YELLOW}>>> Installazione su dispositivo...${NC}"
    if command -v adb &>/dev/null; then
        DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep "device$" | wc -l)
        if [ "$DEVICES" -gt 0 ]; then
            adb install -r "$APK_FILE"
            echo -e "${GREEN}Installato!${NC}"
        else
            echo -e "${YELLOW}Nessun dispositivo connesso.${NC}"
        fi
    else
        echo -e "${YELLOW}adb non trovato. Installa manualmente: adb install -r $APK_FILE${NC}"
    fi
fi

echo ""
echo "  Installa: adb install -r $APK_FILE"
echo "  Login con account admin/moderator su $SERVER_URL"
