# Rapporto Tecnico Finale — ChatAI (configurazione modello 3B uncensored)

Data: 2026-10-29
Autore: opencode
Stato: COMPLETATO (deploy finale eseguito)

## 1. Obiettivo
Rendere ChatAI utilizzabile con un modello locale **3B uncensored** per contenuti sessuali espliciti/estremi
tra adulti consenzienti, mantenendo la leggerezza del modello (3B, ~2.1 GB), senza censura e senza rifiuti.

## 2. Workstream completato

### 2.1 Diagnosi RAM
- Causa principale: Stheno 8B (~4.9 GB) in RAM durante chat.
- Fix: OLLAMA_KEEP_ALIVE=1m, OLLAMA_NUM_CTX=1024→2048, OLLAMA_NUM_PREDICT=256→512, OLLAMA_MAX_VRAM=0.

### 2.2 Analisi modello + Phase 1/2
- Default spostato da Stheno a Qwen 2.5 3B abliterated RP_SLERP.
- Param: temperature 0.65, repeat_penalty 1.02, top_p 0.8.
- Prompt: SAFETY_GUARD, ROMANCE_AGENCY, BREVITY_RULE rilassati.
- Context: num_ctx 2048, num_predict 512.

### 2.3 Sblocco completo
- Pull modello: hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M.
- content_safety.moderate_output → allow (modalità adult).
- QA estremi (pompino, sborra, sega/fisting, scopata, penetrazione): tutti non bloccati.

### 2.4 Deploy / Repro / Commit / Push
- Servizi riavviati e verificati.
- build_app.sh: default Qwen 3B + PASSO 7b (restore da zip chatai_backup_3b.zip).
- Commit: f05fa34, fd73690, 2c7c3e9; push origin main → ok.

## 3. File chiave
- backend/ai_engine/registry.py — DEFAULT_MODEL = Qwen RP_SLERP.
- backend/ai_engine/init.py — fallback default RP_SLERP.
- backend/ai_engine/providers/ollama.py — temp/rp/default.
- backend/prompt_builder.py — SAFETY_GUARD/ROMANCE_AGENCY/BREVITY_RULE.
- backend/content_safety.py — moderate_output allow.
- build_app.sh — default Qwen 3B + PASSO 7b.
- installamodelli.sh — modelli include Qwen 3B.

## 4. Stato attuale
- Modello attivo: Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M.
- Backend running, Ollama running, QA ok, deploy ok.

## 5. Prossimi passi
- Fine-tuning (opzionale): non necessario per sblocco; solo per qualità/coerenza.
- APK build per il telefono (se serve).

## 6. Backup / Riproducibilità
- Git: build_app.sh, installamodelli.sh, backend ai_engine/prompt/safety, report.
- Zip: chatai_backup_3b.zip (in repo) → backend/.env + override Ollama.

## 7. FINE-TUNING (proposta)
- Obiettivo: migliorare coerenza narrativa, qualità dei contenuti espliciti, lingua italiana del modello 3B,
  senza perdere il comportamento uncensored raggiunto.
- Approccio proposto: QLoRA (NF4) sul modello base Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M.
- Dataset: ~1.000–2.000 esempi di chat (adult consensuali, contenuti estremi) in formato instruction/input/output.
- Risorse attuali: CPU-only (no GPU), RAM ~5 GB libere, swap 17 GB → QLoRA fattibile ma lenta (6–12h stimate).
- Iperparametri proposti: 1–3 epoch, LR ~2e-4.
- Fattibilità: MEDIA. Non necessario per il sblocco; opzionale per qualità/coerenza.
- Prossimo passo: preparare dataset → training → test → confronto.
