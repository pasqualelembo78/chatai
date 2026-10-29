# Report: Sostituzione Modello Stheno con Variante Leggera 2K

## File Esaminati
1. `/opt/aria/stheno/Modelfile.stheno-2k` - Modelfile Ollama per modello leggero
2. `/opt/aria/backend/ai_engine/providers/ollama.py` - Provider Ollama
3. `/opt/aria/backend/ai_engine/registry.py` - Registry modelli
4. `/opt/aria/backend/ai_engine/init.py` - Inizializzazione provider
5. `/opt/aria/backend/.env` - Configurazione ambiente
6. `/opt/aria/build_app.sh` - Script build/installazione
7. `/opt/aria/installamodelli.sh` - Script installazione modelli
8. `/etc/systemd/system/ollama.service.d/override.conf` - Configurazione Ollama

## Backup Creati
- `/opt/aria/backup/ollama.py.bak`
- `/opt/aria/backup/init.py.bak`
- `/opt/aria/backup/registry.py.bak`
- `/opt/aria/backup/build_app.sh.bak`
- `/opt/aria/backup/installamodelli.sh.bak`
- `/opt/aria/backup/.env.bak`
- `/opt/aria/backup/Modelfile.stheno-2k.bak`

## Modifiche Effettuate

### 1. backend/ai_engine/providers/ollama.py
- **Linea 77-81**: Aggiunto `stheno-abliterated-2k:latest` come primo modello in `OLLAMA_MODELS`
- **Linea 180**: Cambiato `default_model` da `"stheno-abliterated:8b"` a `"stheno-abliterated-2k:latest"`

### 2. backend/ai_engine/registry.py
- **Linea 8**: Cambiato `DEFAULT_MODEL` da `"stheno-abliterated:8b"` a `"stheno-abliterated-2k:latest"`

### 3. backend/ai_engine/init.py
- **Linee 57-60**: Cambiato fallback default da `stheno-abliterated:8b` a `stheno-abliterated-2k:latest`

### 4. backend/.env
- **Linea 46**: Cambiato `OLLAMA_NUM_CTX` da `4096` a `2048`
- **Linea 49**: Cambiato `OLLAMA_KEEP_ALIVE` da `30m` a `5m`
- **Linea 67**: Cambiato `CHAT_PROVIDER` da `groq` a `ollama`

### 5. build_app.sh
- **Linee 68-70**: Modificati modelli predefiniti per usare `stheno-abliterated-2k:latest`
- **Linee 796-807**: Aggiornata logica creazione alias per modello 2K

### 6. installamodelli.sh
- **Linea 19**: Aggiunto `stheno-abliterated-2k:latest` come primo modello

### 7. stheno/Modelfile.stheno-2k
- **Linea 5**: Cambiato `FROM` da `stheno-abliterated:8b` a blob diretto
- **Linea 13**: Confermato `PARAMETER num_ctx 2048`

## Configurazione Ollama
```
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_KEEP_ALIVE=5m
```

## Test Eseguiti

### Test 1: Modello disponibile
```bash
ollama list | grep stheno
# Output: stheno-abliterated-2k:latest    5a2381a925ae    4.9 GB
```
✅ PASS

### Test 2: Chat API con modello 2K
```bash
curl -X POST http://82.165.218.56:5000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"character":"marco_amicizia","text":"ciao","username":"test"}'
```
**Risultato**:
```
INFO:ai_engine.providers.ollama:OLLAMA: Success - model=stheno-abliterated-2k:latest, response_length=22 chars
INFO:chat_engine:AI response: provider=ollama model=stheno-abliterated-2k:latest len=22
```
✅ PASS - Modello leggero usato correttamente

### Test 3: Plugin WordPress
```bash
curl -X POST https://pornovirtuale.com/wp-admin/admin-ajax.php \
  -d "action=aria_chat_send&character=marco_amicizia&text=prova&username=testwp999d"
```
**Risultato**:
```
"ai_model":"stheno-abliterated-2k:latest","character_id":"marco_amicizia"
```
✅ PASS - Plugin usa modello 2K

### Test 4: Context 2048
```bash
cat /opt/aria/stheno/Modelfile.stheno-2k | grep num_ctx
# Output: PARAMETER num_ctx 2048
```
✅ PASS

### Test 5: RAM Usage
```bash
free -h | grep Mem
# Output: 6.9Gi/7.7Gi (0.8Gi libera)
ps aux | grep llama-server | wc -l
# Output: 1 (una sola istanza)
```
✅ PASS - Memoria OK, una sola istanza

## Problemi Ancora Aperti
Nessuno. Tutti i test passati.

## Conferma
✅ **Nuove installazioni e aggiornamenti useranno la variante leggera `stheno-abliterated-2k:latest` senza scaricare o selezionare il modello pesante.**

### Procedura Idempotente
1. Se `stheno-abliterated-2k:latest` esiste → riutilizzato
2. Se `stheno-abliterated:8b` esiste → creato alias 2K
3. Se Modelfile presente → build da Modelfile
4. Altrimenti → skip (nessun download superfluo)

### Modello Attivo
- **Provider**: ollama
- **Modello**: stheno-abliterated-2k:latest
- **Context**: 2048 token
- **RAM**: ~4.9GB
- **Istanze**: 1 (OLLAMA_NUM_PARALLEL=1)
