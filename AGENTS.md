# ChatAI - Agent instructions

- Ogni volta che si modificano i prompt (es. prompt_builder.py, BREVITY_RULE, regole di roleplay/lunghezza), aggiornare `/opt/aria/chatai_backup_3b.zip` includendo i file modificati (almeno `backend/prompt_builder.py` e i prompt correlati), mantenendo il backup fresco e aggiornato.

- MODELLO OBBLIGATORIO: usare SEMPRE e SOLO il modello locale `hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M`. Non usare mai modelli cloud (Groq/OpenAI/etc.) come default. build_app.sh deve installare sempre questo modello.

# RULE: After every update to plugin, build_app, registry, prompts, behavior, or any file/info needed for reinstall, always update chatai_backup_3b.zip (zip -u with changed files + REPRODUCIBILITY.md).

# REGOLA COMPLETA DI BACKUP / RIPRISTINO (tutti i file e info utili)
- Dopo ogni modifica: aggiornare /opt/aria/chatai_backup_3b.zip con:
  * backend/ (prompt_builder, registry, ollama, chat_engine, chat_summary, shared_memory)
  * build_app.sh, opencode.json, .env
  * plugin WP: /var/www/pornovirtuale/wp-content/plugins/aria-chat/ (aria-chat.php, assets/js/aria-chat.js, includes/Chat_Engine.php)
  * DB: sql_chat_summaries.sql + sql per user_memory_items
  * Documentazione: REPRODUCIBILITY.md
- Se si disinstalla il plugin o si cambia server: copiare file WP, eseguire SQL DB, lanciare build_app.sh, riavviare chatai.service.
