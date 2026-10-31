# REPRODUCIBLE SETUP - Tutto ripetibile con build_app.sh

## 1) Model (default in build_app.sh / registry)
ABLITERATED_MODELS='hf.co/QuantFactory/Llama-3.2-3B-Instruct-abliterated-GGUF:Q4_K_M'
DEFAULT_MODEL = "barbara-quant-generic"  # con override SYSTEM generico (nessun nome fisso)

## 2) DB (ripetibile su qualsiasi sito WP)
sql_chat_summaries.sql -> esegui su PostgreSQL
Tabella: chat_summaries(user_id, character_id, summary_text, updated_at)

## 3) Prompt rules (sempre attivi)
backend/prompt_builder.py: BREVITY_RULE (max 15 parole, mai AI, mai fuori ruolo, accondiscendente)
+ escalation directive (intimacy >= 85)
+ summary injection (get_summary)

## 4) Plugin WP (copia file se sposti sito)
/var/www/pornovirtuale/wp-content/plugins/aria-chat/aria-chat.php (nickname, auto-refresh)
/var/www/pornovirtuale/wp-content/plugins/aria-chat/assets/js/aria-chat.js (nickname, auto-refresh)
/var/www/pornovirtuale/wp-content/plugins/aria-chat/includes/Chat_Engine.php (auto-refresh token, no logout)

## 5) Backend fixes
backend/ai_engine/response.py (no fallback local)
backend/ai_engine/streaming.py (no fallback)
backend/storage/shared_memory.py (jsonb cast)
backend/chat_summary.py (summary logic)
backend/chat_engine.py (auto-save compact summary)

## 6) Per reinstallare / ripristinare su nuovo server
- Esegui build_app.sh (installa modello QuantFactory)
- Esegui sql_chat_summaries.sql su DB
- Copia plugin aria-chat/ o reinstalla
- Aggiorna .env / opencode se serve
- Riavvia chatai.service
