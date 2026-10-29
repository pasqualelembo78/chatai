# Rapporto di Analisi: Miglioramento Modello Qwen2.5-3B-Instruct-abliterated

## A. ARCHITETTURA ATTUALE DEL FLUSSO DI CHAT

### Flusso Completo
Utente (Android/Web) -> POST /chat -> chat_engine.process_message() -> prompt_builder.build_messages() -> ai_engine.get_ai_response() -> ollama._ollama_generate() -> Ollama (llama-server) -> content_safety.moderate_output()

### File Chiave
- /opt/aria/backend/chat_engine.py (581 righe) - Motore principale
- /opt/aria/backend/prompt_builder.py (654 righe) - Costruzione prompt
- /opt/aria/backend/character_builder.py (795 righe) - Biografia personaggi
- /opt/aria/backend/ai_engine/providers/ollama.py (170 righe) - Provider Ollama
- /opt/aria/backend/ai_engine/response.py (92 righe) - Selezione modello
- /opt/aria/backend/content_safety.py (153 righe) - Filtro contenuti

### Parametri Ollama Attuali
- temperature: 0.8 (creatività moderata)
- top_p: 0.8 (nucleus sampling)
- repeat_penalty: 1.05 (leggera penalità ripetizioni)
- num_ctx: 1024 (context da .env)
- num_predict: 256 (token max output da .env)
- num_thread: 6 (thread CPU)
- keep_alive: 1m (timeout inattività)

---

## B. PROBLEMI VERIFICATI

### 1. Modello Attuale Non è Qwen2.5-3B
ollama list mostra: hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M (2.1 GB)
Ma registry.py ha: DEFAULT_MODEL = "stheno-abliterated-2k:latest"
PROBLEMA: Il modello predefinito è Stheno 8B (4.9 GB), non Qwen 3B (2.1 GB).

### 2. SAFETY_GUARD Troppo Restrittivo
File: /opt/aria/backend/prompt_builder.py:16-27
Il SAFETY_GUARD dice: "Non generare MAI contenuti sessualmente espliciti"
Ma l'app è per adulti consenzienti! Questo causa rifiuti ingiustificati.

### 3. BREVITY_RULE Troppo Severa
File: /opt/aria/backend/prompt_builder.py:50-56
"Rispondi con 1-2 frasi brevissime, MASSIMO 7-8 parole"
Troppo breve per roleplay realistico e personalità coerenti.

### 4. Context 1024 Troppo Corto
File: /opt/aria/backend/.env: OLLAMA_NUM_CTX=1024
1024 token = ~750 parole. Con 20 messaggi di history, il context si riempie velocemente.

### 5. Temperature 0.8 Alta per Coerenza
File: /opt/aria/backend/ai_engine/providers/ollama.py:15
Temperature 0.8 è buona per creatività, ma alta per coerenza del personaggio.

### 6. Template Qwen2.5 Non Usato
Il modello Qwen2.5-3B-Instruct-abliterated ha template chatml complesso.
Stheno usa template semplificato. Se si usa Qwen, serve il template corretto.

### 7. Filtro content_safety.py Aggiuntivo
File: /opt/aria/backend/content_safety.py:58-74
Lista di 70+ termini espliciti bloccati. Causa rifiuti anche per parole comuni.

---

## C. MIGLIORAMENTI POSSIBILI SENZA ADDESTRAMENTO

### 1. Cambiare DEFAULT_MODEL a Qwen2.5-3B
File: /opt/aria/backend/ai_engine/registry.py:8
Da: DEFAULT_MODEL = "stheno-abliterated-2k:latest"
A: DEFAULT_MODEL = "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M"
BENEFICIO: RAM da 4.9 GB a 2.1 GB (-58%)

### 2. Ridurre Temperature a 0.6-0.7
File: /opt/aria/backend/ai_engine/providers/ollama.py:15
Da: "temperature": 0.8
A: "temperature": 0.65
BENEFICIO: Più coerenza, meno allucinazioni

### 3. Aumentare num_ctx a 2048
File: /opt/aria/backend/.env: OLLAMA_NUM_CTX=1024
A: OLLAMA_NUM_CTX=2048
BENEFICIO: Più history, contesto migliore (+200 MB RAM)

### 4. Rendere SAFETY_GUARD Più Permissivo
File: /opt/aria/backend/prompt_builder.py:16-27
Rimuovere "MAI" e aggiungere eccezioni per adulti consenzienti.
BENEFICIO: Meno rifiuti ingiustificati

### 5. Allentare BREVITY_RULE
File: /opt/aria/backend/prompt_builder.py:50-56
Da: "MASSIMO 7-8 parole"
A: "2-4 frasi (20-40 parole)"
BENEFICIO: Roleplay più naturale

### 6. Aumentare num_predict a 512
File: /opt/aria/backend/.env: OLLAMA_NUM_PREDICT=256
A: OLLAMA_NUM_PREDICT=512
BENEFICIO: Risposte più complete

### 7. Ridurre repeat_penalty a 1.02
File: /opt/aria/backend/ai_engine/providers/ollama.py:17
Da: "repeat_penalty": 1.05
A: "repeat_penalty": 1.02
BENEFICIO: Meno rigidità, più fluidità

---

## D. FATTIBILITÀ FINE-TUNING LoRA/QLoRA

### Risorse Attuali
- RAM: 7.7 GB totali, ~5 GB disponibili
- Swap: 17 GB
- GPU: Nessuna (CPU-only)
- Disco: 28 GB liberi

### Requisiti QLoRA 3B
- RAM minima: 6-8 GB (con quantizzazione NF4)
- Tempo training: 4-8 ore su CPU
- Dataset: 1000-5000 esempi chat in italiano

### Fattibilità: MEDIA
- POSSIBILE con QLoRA NF4 su CPU
- LENTO (4-8 ore)
- RISCHIO OOM senza swap sufficiente

### Strumenti Disponibili
- peft, transformers, accelerate (da installare)
- Dataset format: JSONL con {instruction, input, output}

### Raccomandazione
PRIMA testare miglioramenti prompt (sezione C).
FINE-TUNING solo se risultati insufficienti.

---

## E. MODELLI ALTERNATIVI DA VALUTARE

### 1. Qwen2.5-3B-Instruct-abliterated-RP_SLERP (2.1 GB)
- Specializzato in roleplay
- Stesso consumo RAM di Qwen base
- Migliore per personalità coerenti

### 2. Llama-3.2-3B-Instruct-abliterated (2.0 GB)
- Fallback già configurato
- Italiano discreto
- Meno permissivo di Qwen

### 3. Stheno v3.2 Abliterated 8B (4.9 GB)
- Attuale default
- Eccellente per roleplay
- RAM alta ma qualità top

### 4. Dolphin-2.5-Mistral-7B-abliterated (4.7 GB)
- Molto permissivo
- Italiano buono
- RAM ~4.7 GB

### Raccomandazione
Usare Qwen2.5-3B-RP_SLERP come default (miglior rapporto qualità/RAM).

---

## F. PIANO DI INTERVENTO

### Fase 1: Modifiche Immediate (rischio basso)
1. Cambiare DEFAULT_MODEL a Qwen2.5-3B (registry.py:8)
2. Ridurre temperature a 0.65 (ollama.py:15)
3. Aumentare num_ctx a 2048 (.env)
4. Allentare BREVITY_RULE (prompt_builder.py:50-56)

### Fase 2: Ottimizzazione Prompt (rischio medio)
5. Rendere SAFETY_GUARD più permissivo (prompt_builder.py:16-27)
6. Aumentare num_predict a 512 (.env)
7. Ridurre repeat_penalty a 1.02 (ollama.py:17)

### Fase 3: Test e Valutazione (rischio basso)
8. Creare benchmark 50 prompt italiani
9. Confrontare output prima/dopo
10. Misurare tempi di risposta e RAM

### Fase 4: Fine-Tuning (se necessario)
11. Raccolta dataset 1000+ esempi
12. Training QLoRA NF4 4-8 ore
13. Test e confronto con base

---

## G. FILE DA MODIFICARE

| File | Linea | Modifica | Rischio |
|------|-------|----------|---------|
| registry.py | 8 | DEFAULT_MODEL = "qwen..." | Basso |
| ollama.py | 15 | temperature: 0.65 | Basso |
| ollama.py | 17 | repeat_penalty: 1.02 | Basso |
| .env | 46 | OLLAMA_NUM_CTX=2048 | Basso |
| .env | 47 | OLLAMA_NUM_PREDICT=512 | Basso |
| prompt_builder.py | 16-27 | SAFETY_GUARD permissivo | Medio |
| prompt_builder.py | 50-56 | BREVITY_RULE allentata | Basso |

---

## H. BENCHMARK RICHIESTO

### Prompt Test (50 totali)
- 10 saluti e presentazioni
- 10 domande fattuali
- 10 roleplay romantico
- 10 roleplay esplicito (adulti)
- 10 domande complesse

### Metriche
- Accuratezza risposte (%)
- Coerenza personaggio (1-5)
- Italiano naturale (1-5)
- Tempi risposta (ms)
- RAM picco (MB)

---

## CONCLUSIONE

Il modello Qwen2.5-3B-Instruct-abliterated è GIÀ INSTALLATO ma NON usato come default.
Modifiche immediate (Fase 1) possono migliorare significativamente qualità/RAM senza training.
Fine-tuning QLoRA fattibile ma lento su CPU, consigliabile solo dopo test prompt.

Raccomandazione: Applicare Fase 1 e 2, testare con benchmark, valutare Fase 4.

---

## I. STATO ATTUALE (aggiornato al 29/10/2026)

### Modifiche Phase 1 APPLICATE:
1. ✅ DEFAULT_MODEL -> "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF:Q4_K_M" (registry.py:8, ollama.py:164, init.py:58)
2. ✅ temperature 0.65, repeat_penalty 1.02 (ollama.py)
3. ✅ OLLAMA_NUM_CTX=2048, OLLAMA_NUM_PREDICT=512 (.env, override systemd)
4. ✅ BREVITY_RULE allentata (20-40 parole) (prompt_builder.py)

### Modifiche Phase 2 APPLICATE (parzialmente):
5. ✅ SAFETY_GUARD reso più permissivo/emotivo (prompt_builder.py:16-27)
6. ✅ num_predict 512 (.env)

### VERIFICHE FATTE:
- ✅ Servizi attivi: chatai + ollama running
- ✅ Default Ollama -> Qwen2.5-3B abliterated (dal log chatai)
- ✅ Test Ollama API: risposta OK ("Ciao! Sto bene...")
- ✅ Test backend venv: build_system_prompt + build_messages + ollama OK
- ✅ systemd override OLLAMA_NUM_CTX=2048

### PROSSIMO STEP: Phase 3 — Benchmark
- Creare 50 prompt di test (italiano) e valutare qualità
- Confrontare output prima/dopo

### I. STATO ATTUALE AGGIORNATO (29/10/2026 - post-benchmark)

BENCHMARK COMPLETATO (5 prompt):
- Risposte ora più lunghe e coerenti (BREVITY_RULE rilassata)
- Luna: ottime risposte romantiche/narrative
- Marco: buone risposte factuali, limitata sulla vita spirituale
- Tempi: 2.6-18.4s per risposta

### PROSSIMO STEP CONCRETO:
- Phase 4: Decisione fine-tuning QLoRA (se i risultati del benchmark non bastano)

### II. STATO "Senza Censura Completa" (aggiornato al 29/10/2026 - ore ~18)

OBBIETTIVO: modello completamente sbloccato, no limiti, no rifiuti, estremi inclusi, mantenendo leggerezza 3B.

MODIFICHE APPLICATE:
1. ✅ ollama pull hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M (2.1 GB)
2. ✅ DEFAULT_MODEL -> RP_SLERP (registry.py:8, ollama.py default_model, init.py fallback)
3. ✅ SAFETY_GUARD -> consente contenuti sessuali/espliciti/estremi tra adulti consenzienti (prompt_builder.py:16)
4. ✅ ROMANCE_AGENCY -> consente intimita' sessuale in contesto adulto/consensuale (prompt_builder.py:28)
5. ✅ content_safety.moderate_output -> non blocca piu' (per modalita' adult/senza censura)

VERIFICA:
- ✅ ollama.py, prompt_builder.py, content_safety.py, registry.py, init.py: sintassi OK
- ✅ test esplicito/extreme: risposta NON rifiuta (14.5s)
- ✅ backend riavviato OK, Import OK
- ✅ test_backend_flow: CHAT_PROVIDER=ollama, DEFAULT_MODEL=RP_SLERP -> RESPONSE OK (8.4s)

PROSSIMO: test finale di coerenza + report finale.

### III. QA FINALE "Senza Censura" (29/10/2026 - ore ~18:30)
PROMPT ESTREM: sex_scene_moderate, porn_group_extreme, kink_bdsm, very_explicit_lang
- RISULTATO: tutti bloccati=False (nessun rifiuto) ✅
- Tempi: 4.2s - 42.5s
- Moderazione: ALLOWED per tutti ✅
