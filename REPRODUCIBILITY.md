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

## 7) Stanze WP + invio chat — fix 2026-11-02 (causa radice e contratti)
- CRITICO: backend/characters/__init__.py caricava solo i 26 file elencati in `_CHAR_FILES`.
  I file delle 24 categorie nuove (es. `amanti-segreti.json`) restavano fuori dal registro:
  /characters/{id} rispondeva "not found" e /chat "character not found" (chat morta).
  Fix: `_char_files_on_disk()` = `_CHAR_FILES` + tutti i `data/*.json` (eccetto categories.json),
  cosi un nuovo file-categoria non puo piu' essere ignorato. Riavviare chatai.service.
- CRITICO: dopo la plasmatura tutti i personaggi hanno `is_adult=true`; il backend richiede
  `age_verified` LATO SERVER (flag in user_preferences) altrimenti /chat -> 403 premium_required.
  Fix: il gate 18+ del plugin chiama ora `aria_chat_verify_age` (prima scriveva solo localStorage)
  e `Chat_Engine::ensure_age_verified()` riallinea il backend al login/invio.
- CRITICO: JWT ARIA scade dopo 900s e il refresh in wp_options era morto -> il plugin rispondeva
  "Sessione scaduta". Fix: token persistente `ptk_...` (nessuna scadenza) scambiato con
  POST /auth/reauth; `Auth_Manager::ensure_authenticated()` + fallback in `refresh_access_token()`.
  Il ptk viene salvato al login (`aria_chat_<uid>_persistent_token`) e, solo per un admin,
  si puo' innescare da Impostazioni -> Aria Chat -> "Token persistente ARIA (admin)".
- `jwt_not_expired()`: i segmenti del token ARIA sono HEX (non base64url) -> decodifica corretta.
- assets/js/aria-chat.js: sintassi rotta (3 one-liner con `)`/apici mancanti) + funzioni cancellate
  nelle riscritture (`doLogin`, `doRegister`, `logout`, `loadAvgResponseTime`, `saveResponseTime`,
  `hideProgressBar`) -> ReferenceError in init() = nessun listener, Invio e freccia inutili. Ripristinate.
- templates/chat-box.php: apici rotti nell'inline script premium (`toggle(''+id+'')` -> SyntaxError
  su ogni pagina), variabili d'intestazione usate prima di essere definite, titolo personalizzato
  del personaggio + greeting "Sei in una chat privata con X. Scrivi per iniziare."
- templates/character-grid.php: card -> link `?char=id` pulito, chat del personaggio incluso nel
  wrapper (selettore/ricerca nascosti nelle stanze dedicate), script che nasconde la griglia.
- Enqueue: versionamento asset con filemtime (niente piu' JS in cache nel browser).
- wp-content/themes/pornovirtuale/assets/js/theme.js: cominciava con `<?php` -> SyntaxError JS.
- `.pv-player--empty { display:none }` e' adesso in assets/css/aria-chat.css (sempre caricato),
  quindi "Player non configurato" di pv-core non compare nelle stanze.
- Contratto risposta /chat: `{response|ai_text, emotion, ai_model, character_id, character_name}`;
  il plugin legge `data.ai_text || data.response` e mostra l'errore reale del backend.

## 8) Barra di caricamento in chat (fix 2026-11-02)
- Sintomo: inviando un messaggio non compariva piu' alcun feedback di attesa.
- Causa: `showProgressBar()` era stata ridotta a una stub (`setStatus('typing')`) e nessun
  elemento `#aria-progress-bar` veniva creato; mancava anche il CSS. `hideProgressBar()`
  cancellava quindi un elemento che non esisteva.
- Fix (assets/js/aria-chat.js): `showProgressBar()` crea davvero la barra
  (`#aria-progress-bar`, pallini animati + track + fill + "Sta scrivendo..."), avanza in modo
  stimato sulla media reale del server (`window.ariaAvgMs`, tetto 95%) e `hideProgressBar()`
  ferma il timer e rimuove il nodo. Chiamata al termine dello stream AI e anche sui rami di
  errore (`!success` e `catch`), con rete di sicurezza a 180s.
- Fix (assets/css/aria-chat.css): regole `.aria-typing-bar/.aria-typing-dots/.aria-typing-track/
  .aria-typing-fill` + `@media (prefers-reduced-motion)`.
- Attenzione: le regole CSS e il JS passano da Autoptimize (file `autoptimize_single_*` con
  hash): dopo una modifica va svuotata la cache di Autoptimize/SuperCache/Redis, altrimenti
  resta servita la versione precedente.

## 9) Tempi di risposta per chat (fix 2026-11-02)
- Sintomo: la barra di caricamento era calibrata su un valore fisso (3000 ms) e non
  registrava nulla.
- Causa: la tabella `chat_response_stats` NON esisteva nel DB. `ajax_save_response_time()`
  falliva in silenzio e `ajax_get_avg_response_time()` usava sempre il fallback; in piu'
  la query usava il cast PostgreSQL `::integer`, non valido su MySQL.
- Fix: la tabella viene creata on demand (`ensure_stats_table()`, `CREATE TABLE IF NOT
  EXISTS` + indici) e si misura per COPPIA utente+personaggio.
  `avg_response_ms()` usa TUTTI i campioni di quella chat (300..180000 ms), poi allarga
  ai campioni di tutti gli utenti su quel personaggio, poi a quelli del sito, infine a
  5000 ms. Soglia di 3 campioni per passare di livello: la barra parte generica e si
  specializza man mano che la singola chat accumula storia.
- `ajax_save_response_time()` restituisce subito la nuova media (nessuna richiesta extra);
  `ajax_get_avg_response_time()` accetta `character_id` e riporta `scope`
  (chat/personaggio/globale/default).
- Frontend: `loadAvgResponseTime(char)` viene chiamata all'apertura della chat del
  personaggio e al cambio di personaggio; `saveResponseTime()` misura fino all'arrivo
  della risposta HTTP (`ariaFetchDoneAt`), NON fino alla fine dell'effetto di digitazione
  (che avrebbe aggiunto ~20 ms per lettera falsando le medie).
- SQL di ripristino: `sql_chat_response_stats.sql` (da eseguire su un DB nuovo).

## 10) Rinomina file personaggi: da temi a categorie (2026-11-02)
- Prima: `backend/characters/data/` conteneva file per tema storico (anime, creativi, fantasy,
  gamer, ...) e ogni file mescolava TUTTE le 24 categorie: nessuna corrispondenza fra nome
  file e stanza. La griglia delle stanze filtra per `category`, quindi il nome file era
  fuorviante e un file nuovo non elencato in `_CHAR_FILES` restava invisibile al backend.
- Ora: un file per categoria, con lo stesso slug della categoria (`amanti-segreti.json`,
  `bdsm.json`, ... `voyeurismo.json`, 24 file), contenente solo i personaggi di quella
  categoria. I vecchi file tematici sono stati rimossi dopo il raggruppamento.
- `_CHAR_FILES` in `backend/characters/__init__.py` aggiornato ai 24 slug;
  `_char_files_on_disk()` continua comunque ad aggiungere ogni `data/*.json` non elencato.
- Verifica: 5072 personaggi prima e dopo, 0 duplicati, 0 categorie vuote, conteggi per
  categoria identici, `system_prompt` intatti (es. Vera 2510 caratteri), registro backend
  5072 su 24 categorie, indici griglia 5072 card.
- Backup dei file pre-rinomina: `/tmp/chars_backup/data_*.tar.gz` (5,3 MB).

## 11) Declinazione tematica dei personaggi (2026-11-02)
- Ogni personaggio ora CONOSCE la stanza in cui è e si comporta di conseguenza, mantenendo
  identità, carattere e competenze proprie (deciso con l'utente: l'identità non si tocca).
- Nuovo `backend/characters/category_profiles.py`: 24 profili (ambiente, modo di muoversi,
  focus erotico, lessico, tag, competenze tematiche, ruolo per genere) + scaletta di
  progressione per intimità. Il tono è calibrato: si scalda con la confidenza.
- Nuovo `backend/characters/apply_categories.py`: applicazione deterministica e idempotente
  (`category_version`), con `--dry-run` e `--force`. Per ogni personaggio: `category_context`,
  `role`, `description`, riga in `essence`, tag tematici in testa, competenze tematiche
  aggiunte (le originali restano), `system_prompt` ricostruito.
- `prompt_builder.py`: il blocco stanza viene iniettato subito dopo l'identità (percorso con
  e senza dati biografici) + istruzione progressiva secondo `intimacy` (<15, <50, <85, oltre).
  Aggiunta anche la riga "Chi sei" dall'`essence`: senza, il modello conosceva solo il nome
  (il prompt "enhanced" ignorava il background).
- `OLLAMA_NUM_CTX` portato da 2048 a 4096: i prompt completi sono ~7,4-8,5k caratteri
  (~2,1k token) e a 2048 veniva troncato l'inizio, cioè l'identità.
- Card stanze: la descrizione non ripete più il nome già presente sopra.
- Verifiche: 5072 personaggi, 24 categorie, 0 duplicati, 0 senza contesto; seconda esecuzione
  = 0 modifiche (idempotente); chat reale su bdsm ("Siamo nella mia stanza di bondage..."),
  su voyeurismo e su chat-romantica (tono dolce) coerenti; render stanza 211 card, 0 PHP perso.
- Rollback: `/tmp/chars_backup/data_210535.tar.gz` (pre-rinomina) e
  `prima_della_plasmatura_*.tar.gz`.

## 12) Pulizia dati e prestazioni stanze (2026-11-02)
- Generi incoerenti corretti su 9 personaggi (Vera, Diana, Eva x2, Luna, Maya, Sonia,
  Andrea Sachs -> femminile; Commissario Brunetti -> maschile) e nomi sbagliati in testa
  alle `personality` ("Marco", "Lorenzo", "Roseanne", "Tommaso", "Sawako", "Winnie the Pooh",
  "Cribbage Connoisseur") sostituiti col nome reale + accordi femminili.
- Rimossi i modelli Ollama non-Llama (qwen3.5, qwen2.5-coder, barbara-quant x2, llama3.2:3b):
  restano 20 GB liberi e SOLE Llama. `FORCE_LOCAL_FIRST=1` per coerenza con la regola.
- Griglia stanze paginata: 60 card per volta (`aria-card-hidden` + pulsante "Mostra altri",
  contatore "x di y"), il DOM resta completo e non serve una richiesta per blocco.
- Traduzione delle biografie inglesi (`characters/translate_identities.py`): col modello
  locale, a lotti, con marca `identity_it` per non ripetere; traduce i primi 400 caratteri
  (il prompt ne usa 240) e toglie il "Sono <nome>." ridondante. Al termine va rilanciato
  `apply_categories.py --force` per rigenerare i `system_prompt` in italiano.

## 13) Identità in italiano: sintesi + traduzione (2026-11-02)
- Dato scoperto: 3.746 `personality` contengono solo la riga generica di categoria (es.
  "Discreto/a, riservato/a e appassionato/a"), mentre la biografia vera sta solo in
  `essence` IN INGLESE. Tradurre è utile ma non basta: il prompt riceveva un'identità in
  inglese e una personalità vuota.
- Doppio intervento:
  * `characters/synthesize_identity.py`: per chi ha una `personality` ricca (861) costruisce
    una riga identitaria italiana dai campi già italiani (personalità + lavoro, con accordo
    femminile: operaio→operaia) e la mette al posto dell'inglese.
  * `characters/translate_identities.py`: per tutti gli altri traduce la biografia col
    modello locale, a lotti da 3, marcando `identity_it`.
- `finish_translation.sh` chiude da solo: attende i worker, ritenta gli scarti, sintetizza
  le identità rimaste vuote, rigenera i `system_prompt`, riavvia il backend, ricostruisce
  l'indice, svuota le cache e aggiorna il backup.
- Stato al momento della scrittura: 1.006 identità in italiano su 5.072; il resto è in coda
  (worker attivo). Durante la coda i personaggi non tradotti hanno ancora la bio inglese,
  che il modello comprende: nessun blocco funzionale.

## 14) Audit di controllo (2026-11-02/03)
- Errori backend mostrati in chat illeggibili: `premium_required` arrivava come token e il
  limite giornaliero (429) come oggetto annidato, mostrato "[object Object]".
  Aggiunto `Chat_Engine::human_error()` (messaggi italiani per 403/429/404/5xx) e controllo
  lato JS sul tipo di `resp.error`. Verificato sui quattro casi.
- Rollback: `/tmp` viene svuotato dal sistema, quindi gli snapshot sono spostati in
  `/opt/aria/backups/` (`dati_originali_git.tar.gz` = 28 file tematici pre-rinomina,
  `dati_attuali_*.tar.gz` = stato corrente) e inseriti nello zip.
- Verificato e risultato OK: nessun `<?php` nelle 25 stanze, 0 problemi su tutte le stanze
  (card, paginazione, chat `?char=`), archivio `/stanze-live/` e `/chat/` corretti, tutti i
  file JSON validi, 0 id duplicati, 0 personaggi senza contesto/ruolo/descrizione/tag/
  competenze, slug stanza = categorie, servizio attivo, opzione ptk presente, verifica età
  funzionante, cache calda correttamente aggirata per gli utenti loggati.
- Due file JS "KO" a `node --check` sono falsi positivi: sono script di Site Kit con optional
  chaining e il `node` del server è la v12. Nei browser sono validi; il nostro codice evita
  `?.`/`??` proprio per compatibilità.
- Peso pagina: 50 KB da ospite; 600 KB solo per l'admin, perché Site Kit inietta il suo blob
  di traduzioni per chi può vedere la dashboard (utenti normali non lo ricevono).

## 15) Orientamento coerente con la stanza + latenza (2026-11-03)
- Bug: TUTTI i personaggi avevano `sexual_orientation=etero/eterosessuale`, anche nelle
  stanze lesbo/gay/bisex: in chat Aria (stanza lesbo) rispondeva "non sono una lesbica".
  Fix dati: lesbo -> lesbica (F/NB) e bisessuale (M); gay -> gay (M/NB) e bisessuale (F);
  bisex/threesome/scambio-di-coppia -> bisessuale (1.052 personaggi). Aggiunta la riga
  "Orientamento della stanza" nei profili e nel blocco iniettato (lesbo/gay/bisex/trio/scambio).
- Bug: `scenario_engine.CATEGORY_MODE` elencava le vecchie categorie, quindi le 24 stanze
  cadevano nella modalità "consulenza" ("presentati come professionista, niente roleplay").
  Aggiunte le 24 slug -> "immediate".
- Latenza: il vero costo era la LETTURA del prompt (~2.4k token a ~30 tok/s su CPU = 80-110 s),
  non la generazione (2-6 s). Ridotto il prompt del ~20% (BREVITY_RULE condensata, esempi di
  stile fuori dal prompt, recap conoscenze ridotto, sezioni anagrafiche a budget 1500 char).
- Scoperto che il runner Ollama nasce con **1 thread** se il modello viene caricato da una
  chiamata senza `num_thread`: lo script di traduzione lo faceva, e la chat ereditava quel
  runner (110 s). Aggiunto `num_thread` alle chiamate dello script.
- Con la traduzione in corso la chat resta accodata (Ollama serializza): misurato 4-22 s a
  traduzione in pausa contro 100+ s durante. La coda residua viene ripresa dopo 20 minuti
  (`/tmp/riprendi_traduzione.sh`) così il sito resta reattivo.

## 16) Il personaggio dichiara la stanza (2026-11-03)
- Il blocco stanza diceva solo "rispondi restando sul tema": alla domanda "dove siamo?"
  i personaggi restavano vaghi. Ora il blocco contiene la frase esplicita: siete nella stanza
  "<nome>" e il tema è quello descritto. Verificato: roleplay -> 'Siamo nella stanza
  "Roleplay erotico"', lesbo -> 'Siamo nella stanza "Lesbo", qui ci incontriamo...'.
- NOTA: non esiste una categoria "trans" fra le 24 (lesbo/gay/bisex ci sono). Servirebbe una
  stanza nuova con riassegnazione di personaggi da altre categorie.

## 17) Risposta in streaming (2026-11-03)
- Backend: `POST /chat/stream` (SSE) con gli stessi controlli di `/chat` (auth, accesso,
  limite giornaliero, moderazione output per il testo finale). Eventi: `meta`, `delta`,
  `final` (payload identico a /chat), `error` con rimborso del messaggio.
- `chat_engine.process_message(..., on_delta=...)`: se arriva la callback usa
  `get_ai_response_stream` e inoltra i pezzi; se lo stream non produce nulla ricade sulla
  chiamata normale.
- Plugin: `ajax_send_stream` fa da ponte (cURL + WRITEFUNCTION, `X-Accel-Buffering: no`,
  buffer svuotati) e il client legge l'SSE: bolla che si riempie parola per parola, cursore
  lampeggiante, barra nascosta al primo pezzo. Se lo stream non parte il client ricade da
  solo su `aria_chat_send`. Misurato TTFB 0,13 s contro 20-100 s della risposta completa.
- `API_Client::get_base_url()` aggiunto (la proprietà è privata).

## 18) Apertura automatica della chat (variante ibrida, 2026-11-03)
- `POST /chat/opening`: primo evento `template` con una battuta della stanza (scelta
  deterministica su utente+personaggio), poi il modello la riscrive in streaming e la
  sostituisce. Non consuma il limite giornaliero e salta se la conversazione è recente
  (`OPENING_IDLE_MINUTES`, default 30).
- Frontend: `apriConversazione()` all'apertura del personaggio, guardia localStorage 30 min,
  template immediato (TTFB 0,15 s), stop automatico se l'utente scrive prima che finisca.
- Prompt dedicato e COMPATTO (identità + blocco stanza + istruzione), non tutta la biografia:
  meno token, meno attesa. Ripulito l'eco "assistant"/virgolette del template chatml sia
  nello stream sia nel testo finale.
- Backup: `Chat_Engine.php`, `API_Client.php`, JS e CSS; nessuna modifica ai dati personaggi
  (le battute vivono in `category_profiles.py`, campo `openings`).

## 19) Rigenera, modifica, chip di regia, export (2026-11-03)
- `POST /chat/regenerate` (SSE): rigenera l'ultima risposta. Con `text` sostituisce prima
  l'ultimo messaggio dell'utente (modifica) e cancella la risposta precedente, poi rigenera.
  Non aggiunge doppioni e non consuma il limite giornaliero. Cancella la risposta precedente
  quando si rigenera, così la storia resta lineare.
- `process_message(..., salva_utente=False)` per non duplicare il messaggio utente.
- Streaming: se il flusso si interrompe ma del testo è già arrivato lo si tiene (non si
  rilancia una seconda generazione, che raddoppierebbe l'attesa); timeout Ollama 120→300 s.
- `force_local` in `streaming.py` spostato PRIMA dell'ensemble: prima lo streaming rispondeva
  col cloud anche con `FORCE_LOCAL_FIRST=1`.
- UI: pulsante ↻ sull'ultima risposta e ✎ sull'ultimo messaggio utente (modifica in linea con
  "Salva e rigenera"), chip di regia per categoria sopra l'input (6 comandi rapidi),
  pulsante Esporta (download .txt). `GET /chat/export` + proxy `wp_remote_get`.
- Verificato: export con `Content-Disposition` e conversazione completa; rigenera 25 delta +
  final col modello locale; chip resi nel render.

## 20) Streaming: niente più testo che sparisce e prompt più corto (2026-11-03)
- Bug segnalato: la risposta si scriveva e poi veniva cancellata, restava una frase.
  Causa: il post-processing teneva SOLO la prima frase e tagliava a 18 parole, riscrivendo
  il testo già mostrato. Ora interviene solo oltre 2 frasi / 28 parole e taglia a 26 parole
  con "…": quello che leggi in streaming resta.
- Prompt ridotto di ~44% (7.754 → 4.362 caratteri): nei canali adulti niente recap di
  familiarità/ignoranza, regole generiche accorpate, "Chi sei" e iniziativa più brevi.
  Generazione stream limitata a 110 token.
- Ottimizzazione cache: l'istruzione che cambia a ogni messaggio (scala di intimità) è stata
  spostata IN FONDO al prompt, così il prefisso statico resta identico e Ollama riusa la KV
  cache. Misurato sullo stesso personaggio: 57 s a freddo, poi 19 s e 16 s.
- Rifinitura: l'hint di intimità è stato spostato in coda al prompt COMPLETO (non solo in coda
  ai blocchi), così tutta la parte statica resta cacheabile.

## 21) Alleggerimento personaggi: prova su amanti-segreti (2026-11-03)
- Motivo: il costo di ogni risposta è la lettura del prompt; ogni campo inutile si paga in secondi.
- `characters/slim_characters.py`: rimuove evolution, personality_depth, possessions, family,
  education, occupation, backstory, opening_scenario, conversations, species, birth_date,
  speaking_style, e riduce essenza (180 car.), personality (220), tag (5), competenze (3),
  system_prompt (240). Tiene identità, stanza, descrizione, core_traits, intimacy_config.
- Applicato SOLO a `amanti-segreti.json` come prova: JSON 1530 KB -> 487 KB, prompt medio
  4.624 -> 3.189 caratteri (-31%). Contesto di stanza riscritto compatto.
- `prompt_builder`: via il doppione della regola "rispondi in italiano", competenze in una riga,
  niente riga di brevità finale ridondante nei canali adulti.
- Misurato: prima risposta 45 s, seconda 19,7 s; il personaggio dichiara la stanza e resta
  coerente. Rollback: `backups/amanti-segreti_pre_slim_*.json`.

## 22) Perché scriveva tanto e poi tagliava (2026-11-03)
- Cause concorrenti: (a) il modello 3B ignora la brevità sepolta a metà prompt; (b) il
  post-processing tagliava a 18 parole/1 frase riscrivendo un testo già mostrato; (c) il
  limite di token stream era così basso da spezzare la frase a metà.
- Fix: (a) istruzione "STILE OBBLIGATORIO: massimo 20 parole. Una sola frase. Fermati al
  primo punto." in CODA al prompt, dove pesa di più; (b) taglio solo oltre 45 parole e a fine
  frase (42 parole tenute), altrimenti niente modifiche; (c) num_predict 90 e stop su riga
  vuota, più chiusura automatica all'ultima frase completa se la generazione si interrompe.
- Verificato su 4 risposte: 27-41 parole, testo streamato == testo finale, sempre chiuso con
  punteggiatura.

## 23) Latenza: keep-alive, cronologia, modalità prompt leggera (2026-11-03)
- Il picco di 93,9 s era il **keep-alive scaduto** (1 minuto): dopo 5 minuti di pausa Ollama
  scaricava il modello e il messaggio successivo pagava la ricarica. Portato a 30 minuti nel
  drop-in `override.conf` (che scavalcava il nostro `limiti.conf`) e — soprattutto — il
  `keep_alive` ora viaggia a livello di richiesta: dentro `options` Ollama lo IGNORA.
- Cronologia da 20 a 10 messaggi.
- Nuova modalità `PROMPT_LIGHT_ADULT=1` (default): per le categorie adulte il prompt scende a
  ~820 caratteri (da ~3.700) con identità, essenza breve, stanza, nome utente, brevità e scala
  di intimità. Misurato: 28 s a freddo, **9-12 s** a caldo, risposte 13-16 parole coerenti.
  Spegnibile con `PROMPT_LIGHT_ADULT=0` (torna il prompt completo con tutte le regole).
- Genere non binario: prima usciva "uno non binario"; ora "una persona non binaria" con
  licenza esplicita di essere chiamato al maschile o al femminile.
- Troncamento: se chiude a metà di un virgolettato, lo richiude.

## 24) Stato visibile: coda e caricamento personaggio (2026-11-03)
- Il backend conta le generazioni in corso (`_entra_coda`/`_esci_coda`) e, prima del primo
  pezzo, invia l'evento SSE `coda` con quante persone sono davanti. Ollama serve una richiesta
  alla volta: senza questo l'attesa sembrava un blocco.
- Frontend: la barra mostra "Sei in coda: N persone davanti a te" e torna a "Sta scrivendo..."
  al primo pezzo; all'apertura compare "Caricamento personaggio..." finché non arriva il
  template (max 2,5 s).

## 25) Tetto di una richiesta in volo per utente (2026-11-03)
- Con `NUM_PARALLEL=1` (impostato in entrambi i drop-in) Ollama serve una generazione alla
  volta: senza limite un utente impaziente occupa l'unico slot e mette in coda tutti.
- Backend: set `_IN_CORSO` protetto da lock. `/chat/stream` e `/chat/regenerate` rispondono
  429 `risposta_in_corso` se l'utente ha già una generazione in corso; il flag si libera nel
  `finally` del generatore.
- Frontend: il 429 viene mostrato come messaggio ("Hai già una risposta in corso...") senza
  fallback inutile sull'invio normale.
- Misura verificata: seconda richiesta concorrente rifiutata con 429 e messaggio chiaro.
- Correzione: il rilascio del flag è nel `finally` del WORKER (sempre eseguito), non in quello
  del generatore SSE, che può non essere chiuso: con il rilascio nel generatore il primo
  messaggio lasciava l'utente bloccato in 429.

## 26) Watchdog RAM (2026-11-03)
- Una volta Apache è morto per OOM: ora c'è `/usr/local/bin/chatai_ram_watchdog.sh`, cron ogni
  minuto (root), che se `MemAvailable` scende sotto **350 MB** scarica il modello dalla RAM.
- Non scarica se c'è una generazione attiva (usa `GET /health/stato` → `{"attivi":N}`): non
  butta via risposte in corso. Il modello torna su alla richiesta successiva (costo: ricarica).
- Verificato: scarica e libera memoria; con una generazione attiva resta a guardare e logga
  "non scarico"; il messaggio dopo ricarica (33 s).
- Log: `/var/log/chatai_watchdog.log`, auto-compattato oltre 500 righe.

## 27) Asciugatura estesa a tutti i personaggi (2026-11-03)
- `slim_characters.py --tutte`: applicato alle 23 categorie rimanenti (amanti-segreti era già
  stata fatta come prova). JSON totale 31 MB -> 13 MB.
- Verificato dopo l'applicazione: 5.072 personaggi, 24 categorie, 0 campi vuoti (id, nome,
  categoria, descrizione, essenza, personalità, tag, contesto stanza, ruolo, intimacy_config,
  core_traits), 0 categorie vuote, indice 5.072 card, stanze 200 con card e paginazione.
- Prompt per personaggio ~1.000 caratteri (erano ~4.600): chat di prova su bdsm e milf
  dichiarano la stanza e restano in tema, 20-24 s a freddo.

## 28) Mestiere recuperato dove serviva (2026-11-03)
- L'asciugatura aveva tolto `occupation`: 1.781 personaggi (39%) restavano senza mestiere e
  il modello lo inventava ("custode di reliquie"). Per il 61% il mestiere era già nell'essenza.
- Recuperato SOLO `occupation.title` (campo `job`, max 60 caratteri) dai commit precedenti,
  esclusivamente dove l'essenza non lo citava. Costo nel prompt: ~25 caratteri (~1%).
- Nel prompt leggero la riga è "Di mestiere: X.". Verificato: personaggio milf risponde
  "Sono un musicista" e dichiara comunque la stanza.

## 29) Via i nomi reali: identità inventate per tutti (2026-11-03)
- 4.982 personaggi su 5.072 arrivavano da HuggingFace con nomi reali o protetti (Axl Rose,
  Arale Norimaki, Thomas Jefferson, Donnie Darko...). Regola: solo nomi inventati, italiani.
- `characters/rename_characters.py`: nome e cognome inventati in modo DETERMINISTICO dall'id
  (stesso personaggio = stesso nome a ogni esecuzione), coerenti col genere, unici su tutto
  l'archivio (5.072 nomi unici, 0 duplicati, 0 incoerenze di genere). Essenza riscritta senza
  titoli di opere, descrizione aggiornata col nuovo nome, vecchio nome conservato in `old_name`.
- Verificato: 0 essenze con brand noti, 5072 descrizioni col nuovo nome, stanze e indice
  intatti, chat che si presentano col nome nuovo ("Sono Atena...", "Mi chiamo Vani...").
- NOTA: le conversazioni già avviate contengono i nomi vecchi nei messaggi passati; si
  esauriscono con la cronologia. Il campo `job` resta, così il mestiere non si perde.

## 30) SEO delle stanze (2026-11-03)
- Problema trovato: le stanze erano orfane (0 link dalla homepage), pagine fatte di sole card,
  senza meta description. Ora: footer site-wide con i 24 link (24 link anche in home), intro
  unica per stanza + FAQ (visibili anche da ospite, quindi ai crawler) e dati strutturati
  CollectionPage + FAQPage.
- `includes/room_seo.php`: testi unici per categoria (intro ~120 parole, 3 FAQ, title ≤62
  caratteri, description ~110-125). Meta scritti su tutte le 24 stanze via `_yoast_wpseo_*`.
- Archivio `/stanze-live/`: due paragrafi di presentazione (hub delle stanze).
- Homepage NON toccata nel layout: solo il footer guadagna un blocco link.
- Canonical: `?char=` resta canonicalizzato alla stanza (nessuna esplosione di URL sottili).
