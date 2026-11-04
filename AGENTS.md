# ChatAI - Agent instructions

- Ogni volta che si modificano i prompt (es. prompt_builder.py, BREVITY_RULE, regole di roleplay/lunghezza), aggiornare `/opt/aria/chatai_backup_3b.zip` includendo i file modificati (almeno `backend/prompt_builder.py` e i prompt correlati), mantenendo il backup fresco e aggiornato.

- MODELLO OBBLIGATORIO (UNICO AMMESSO): usare SEMPRE e SOLO il modello locale
  `hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M`
  (Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M). E' il modello che funziona bene:
  deve essere l'unico installato e l'unico usato dalle chat.
  `build_app.sh` deve installare sempre e soltanto questo modello.

- VIETATO installare modelli diversi: NON eseguire `ollama pull` di Qwen
  (compreso `hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF`,
  Qwen2.5-3B, Qwen2.5-7B, qwen3.5, qwen2.5-coder), ne' di Stheno/Lunaris/gpt-oss
  o di qualsiasi altro modello, salvo richiesta esplicita dell'utente.
  Se per prova ne viene scaricato uno, va rimosso con `ollama rm <modello>` e il
  default in `backend/ai_engine/registry.py` + `ai_engine/providers/ollama.py`
  deve restare Llama-3.2-3B-Instruct-abliterated.

- **AGGIORNAMENTO DEL MODELLO / DELLA LINGUA**: se l'utente chiede di aggiornare il modello o il
  vocabolario, seguire `PROCEDURA_LINGUA.md` (raccolta da fonti con licenza annotata -> qualificazione
  -> iniezione nel prompt -> misura -> correzioni). Vale per qualsiasi modello, attuale o futuro.
  Niente fine-tuning. Niente termini inventati. Fonti in `fonti.md`, misure contro una baseline.

- Non usare mai modelli cloud (Groq/OpenAI/Cerebras/etc.) come default: la chat
  deve girare solo sul modello locale obbligatorio (`CHAT_PROVIDER=ollama`).

- OGNI modifica che richieda pacchetti, servizi, file o configurazioni deve essere
  **installabile in modo idempotente da `build_app.sh`** (stesso risultato su server nuovo,
  nessun errore se già presente) e i file necessari vanno **sempre** aggiunti a
  `chatai_backup_3b.zip`. Vale per: dipendenze di sistema (es. `hunspell` + `hunspell-it`),
  nuove cartelle di dati (`backend/language/`), servizi systemd, cron, drop-in, SQL.
  Regola pratica: se dopo un ripristino da zero serve un comando manuale, la modifica non è
  finita. Prima di chiudere un lavoro: `bash -n build_app.sh` e verifica che i file siano
  nello zip.

# RULE: After every update to plugin, build_app, registry, prompts, behavior, or any file/info needed for reinstall, always update chatai_backup_3b.zip (zip -u with changed files + REPRODUCIBILITY.md).

# REGOLA COMPLETA DI BACKUP / RIPRISTINO (tutti i file e info utili)
- Dopo ogni modifica: aggiornare /opt/aria/chatai_backup_3b.zip con:
  * backend/ (prompt_builder, registry, ollama, chat_engine, chat_summary, shared_memory)
  * build_app.sh, opencode.json, .env
  * plugin WP: /var/www/pornovirtuale/wp-content/plugins/aria-chat/ (aria-chat.php, assets/js/aria-chat.js, includes/Chat_Engine.php)
  * DB: sql_chat_summaries.sql + sql per user_memory_items
  * Documentazione: REPRODUCIBILITY.md
- Se si disinstalla il plugin o si cambia server: `./restore_from_backup.sh` (estrae lo zip e
  lancia build_app.sh), poi eseguire gli SQL del DB, attivare il plugin e riavviare chatai.service.
  `build_app.sh` da solo NON estrae il backup: installa dipendenze e servizi.
