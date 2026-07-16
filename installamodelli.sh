#!/bin/bash
#
# installamodelli.sh — Installa (pull) i modelli Ollama locali di ChatAI
#
# I modelli NON fanno parte del repo: risiedono in ~/.ollama/models ed
# è Ollama a gestirli. Questo script li scarica (idempotente: salta quelli
# già presenti).
#
# Usage:
#   ./installamodelli.sh            # modelli leggeri/medi (<= 27GB)
#   ./installamodelli.sh --heavy    # include anche i modelli da 40-45GB (server grande)
#   ./installamodelli.sh --all      # tutti, compresi i pesanti
#   ./installamodelli.sh --list     # mostra i modelli configurati e lo spazio richiesto
#
set -euo pipefail

# Modelli registrati in backend/ai_engine/providers/ollama.py (OLLAMA_MODELS)
MODELS=(
  "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M"
  "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M"
  "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M"
  "llama3.2:3b"
  "llama3.2:1b"
  "openchat/openchat-7b"
  "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M"
  "qwen2.5:7b"
  "llama3.1:8b"
  "mistral:7b"
  "gemma2:9b"
  "mixtral:8x7b"
  "qwen2.5:14b"
  "mistral-nemo:12b"
  "qwen2.5:32b"
  "deepseek-r1:7b"
  "llama3.3:70b"
  "llama3.1:70b"
  "qwen2.5:72b"
  "deepseek-r1:70b"
)

# Modelli "pesanti" (richiedono molto RAM/disco) — esclusi salvo --heavy/--all
HEAVY="llama3.3:70b llama3.1:70b qwen2.5:72b deepseek-r1:70b qwen2.5:32b mixtral:8x7b"

MODE="${1:---}"

is_heavy() {
  local m="$1"
  for h in $HEAVY; do
    [ "$m" = "$h" ] && return 0
  done
  return 1
}

# Assicura che ollama sia raggiungibile
if ! command -v ollama &>/dev/null; then
  echo "ERRORE: 'ollama' non trovato. Installa Ollama prima di procedere."
  exit 1
fi
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "AVVIO Ollama..."
  ollama serve > /tmp/ollama_serve.log 2>&1 &
  disown
  for i in $(seq 1 20); do
    curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

if [ "$MODE" = "--list" ]; then
  echo "Modelli configurati ($(printf '%s\n' "${MODELS[@]}" | wc -l)):"
  for m in "${MODELS[@]}"; do
    if is_heavy "$m"; then echo "  [HEAVY] $m"; else echo "  $m"; fi
  done
  exit 0
fi

echo "=================================================="
echo " ChatAI — Installazione modelli Ollama locali"
echo "=================================================="
echo " Directory modelli: ${OLLAMA_MODELS_DIR:-$HOME/.ollama/models}"
echo "=================================================="

PULLED=0
SKIPPED=0
for m in "${MODELS[@]}"; do
  if is_heavy "$m" && [ "$MODE" != "--heavy" ] && [ "$MODE" != "--all" ]; then
    echo "  [skip] $m (pesante — usa --heavy per installarlo)"
    continue
  fi
  if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$m"; then
    echo "  [ok]    $m già presente"
    SKIPPED=$((SKIPPED+1))
    continue
  fi
  echo "  [pull]  $m ..."
  if ollama pull "$m"; then
    echo "  [done]  $m"
    PULLED=$((PULLED+1))
  else
    echo "  [FAIL]  $m — pull non riuscito (rete o spazio insufficiente)"
  fi
done

echo "=================================================="
echo " Completato: $PULLED scaricati, $SKIPPED già presenti."
echo " Per usare i modelli: selezionali da ChatAI (catena free)."
echo "=================================================="
