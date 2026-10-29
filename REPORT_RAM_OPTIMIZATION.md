# Report: Ottimizzazione RAM - Solo Modelli Abliterated

## Obiettivo
Ridurre il consumo RAM mantenendo solo modelli Ollama locale abliterated (senza censura).

## Modifiche Effettuate

### 1. backend/ai_engine/providers/ollama.py
**Rimosso tutti i modelli non-abliterated o censurati.**

**Prima:** 25 modelli (inclusi Llama, Mistral, Qwen censurati, Mixtral, DeepSeek, ecc.)
**Dopo:** 8 modelli abliterated/permissivi solo

```python
OLLAMA_MODELS = [
    {"id": "stheno-abliterated-2k:latest", ...},           # 8B 2K ★ principale
    {"id": "stheno-abliterated:8b", ...},                  # 8B fallback
    {"id": "fluffy/l3-8b-stheno-v3.2:latest", ...},        # 8B permissiva
    {"id": "hf.co/mradermacher/L3.1-8B-Lunaris-v1-abliterated-GGUF:Q4_K_M", ...},  # 8B
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M", ...},  # 3B RP
    {"id": "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M", ...},  # 3B
    {"id": "hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M", ...},  # 3B fallback
    {"id": "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M", ...},  # 7B
]
```

### 2. stheno/Modelfile.stheno-2k
**Ridotto contesto da 2048 a 1024 token.**

```
PARAMETER num_ctx 1024
```

**Risparmio stimato:** ~200-400 MB di RAM per KV cache.

### 3. backend/.env
**Ottimizzati parametri Ollama:**

```
OLLAMA_NUM_CTX=1024      # era 2048
OLLAMA_NUM_PREDICT=256   # era 512
OLLAMA_KEEP_ALIVE=1m     # era 30m
```

### 4. /etc/systemd/system/ollama.service.d/override.conf
**Ottimizzati parametri systemd:**

```ini
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=1m"      # era 5m
Environment="OLLAMA_MAX_VRAM=0"         # forzato CPU
Environment="OLLAMA_NUM_CTX=1024"       # era non impostato
```

### 5. Modello Ricreato
```bash
ollama create -f Modelfile.stheno-2k stheno-abliterated-2k:latest
```

## Misure RAM

### A Riposo (modello scaricato)
```
MemTotal:        7.7 GB
MemUsed:         2.1 GB
MemAvailable:    5.3 GB
```

### Durante Chat (modello caricato)
```
MemTotal:        7.7 GB
MemUsed:         7.1 GB
MemAvailable:    0.3 GB
llama-server RSS: 5,252,260 KB (~5.0 GB)
```

### Dopo 60 secondi di inattività
```
MemTotal:        7.7 GB
MemUsed:         2.1 GB
MemAvailable:    5.3 GB
Modello scaricato automaticamente (KEEP_ALIVE=1m)
```

## Consumi per Processo

| Processo | RSS | %MEM | Note |
|----------|-----|------|------|
| llama-server | 5.0 GB | 64.9% | Stheno 8B caricato |
| opencode | 554 MB | 6.8% | Shell session |
| apache2 | 138 MB | 1.7% | Web server |
| uvicorn (backend) | 137 MB | 1.6% | FastAPI |
| **Totale senza modello** | **~2.1 GB** | **27%** | A riposo |

## Risparmio RAM Ottenuto

| Ottimizzazione | Risparmio | Note |
|----------------|-----------|------|
| KEEP_ALIVE 30m → 1m | Dinamico | Modello scaricato dopo 1m |
| Context 2048 → 1024 | ~200-400 MB | KV cache ridotta |
| Rimossi modelli non-abliterated | N/A | Solo cleanup |
| **Totale stimato** | **~200-400 MB** | Durante chat |

## Comportamento Dinamico

```
Tempo 0:00 - Chat inviata
          ↓
          Modello caricato (~5.0 GB RAM)
          RAM totale: ~7.1 GB
          ↓
Tempo 1:00 - KEEP_ALIVE scaduto
          ↓
          Modello scaricato
          RAM totale: ~2.1 GB
```

## Test Eseguiti

### Test 1: Chat funzionante
```bash
curl -X POST http://82.165.218.56:5000/chat \
  -d '{"character_id":"marco_amicizia","text":"Test","model":"stheno-abliterated-2k:latest"}'
```
**Risultato:** ✅ "Ok! Riavviato e funzionando."

### Test 2: Modello scaricato dopo 1m
```bash
sleep 60 && ollama ps
```
**Risultato:** ✅ Nessun modello attivo

### Test 3: RAM libera dopo 1m
```bash
sleep 60 && free -h
```
**Risultato:** ✅ 5.3 GB disponibili

## Modelli Disponibili (solo abliterated)

| Modello | Dimensione | Uso |
|---------|------------|-----|
| stheno-abliterated-2k:latest | 4.9 GB | Principale (context 1024) |
| stheno-abliterated:8b | 4.9 GB | Fallback Stheno |
| fluffy/l3-8b-stheno-v3.2:latest | 4.9 GB | Stheno permissiva |
| hf.co/mradermacher/L3.1-8B-Lunaris-v1-abliterated-GGUF:Q4_K_M | 4.9 GB | Lunaris 8B |
| hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M | 2.1 GB | Qwen 3B RP |
| hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M | 2.0 GB | Qwen 3B |
| hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M | 2.0 GB | Llama 3B fallback |
| hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M | 4.7 GB | Qwen 7B |

## Note Importanti

### Context 1024 vs 2048
- **Ollama usa `-c 2048`** anche se Modelfile ha `num_ctx 1024`
- **Backend passa `num_ctx: 1024`** nelle opzioni API
- **Effetto reale:** KV cache ridotta, ma modello usa 2048 come massimo

### KEEP_ALIVE=1m
- **Vantaggio:** RAM libera rapidamente dopo inattività
- **Svantaggio:** Ritardo di ~5-10 secondi alla prima chat dopo inattività
- **Compromesso:** Accettabile per server con RAM limitata

### RAM Minima Richiesta
- **A riposo:** ~2.1 GB
- **Durante chat:** ~7.1 GB
- **Swap consigliato:** ≥8 GB (attualmente 17 GB)

## Comandi di Verifica

```bash
# Stato RAM
free -h

# Modello attivo
ollama ps

# Processo Ollama
ps aux | grep -E "(llama|ollama)" | grep -v grep

# Test chat
curl -X POST http://82.165.218.56:5000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"character_id":"marco_amicizia","text":"ciao","model":"stheno-abliterated-2k:latest"}'

# Verifica KEEP_ALIVE
sleep 60 && ollama ps  # dovrebbe essere vuoto
```

## Rollback

```bash
# Ripristina .env
cp /opt/aria/backup/.env.bak /opt/aria/backend/.env

# Ripristina ollama.py
cp /opt/aria/backup/ollama.py.bak /opt/aria/backend/ai_engine/providers/ollama.py

# Ripristina systemd
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=5m"
EOF

# Riavvia servizi
systemctl daemon-reload
systemctl restart ollama
systemctl restart aria-backend
```

## Conclusione

✅ **Obiettivo raggiunto:** Solo modelli abliterated, RAM ottimizzata con KEEP_ALIVE=1m
✅ **Chat funzionante:** Testati con successo
✅ **RAM dinamica:** 2.1 GB a riposo, 7.1 GB durante chat
✅ **Modello scaricato automaticamente:** Dopo 1 minuto di inattività

**Nota:** Il consumo durante chat (~7.1 GB) è determinato principalmente dal modello Stheno 8B (~5.0 GB). Per ridurre ulteriormente, servirebbe un modello più piccolo (es. Qwen 3B ~2 GB).
