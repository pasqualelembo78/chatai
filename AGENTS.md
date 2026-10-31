# ChatAI - Agent instructions

- Ogni volta che si modificano i prompt (es. prompt_builder.py, BREVITY_RULE, regole di roleplay/lunghezza), aggiornare `/opt/aria/chatai_backup_3b.zip` includendo i file modificati (almeno `backend/prompt_builder.py` e i prompt correlati), mantenendo il backup fresco e aggiornato.

- MODELLO OBBLIGATORIO: usare SEMPRE e SOLO il modello locale `hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M`. Non usare mai modelli cloud (Groq/OpenAI/etc.) come default. build_app.sh deve installare sempre questo modello.
