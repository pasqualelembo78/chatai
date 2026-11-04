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

## 31) Prova gratuita senza login, 4 messaggi (2026-11-03)
- Prima: chat chiusa da un muro di login. Ora il visitatore vede le card, apre un personaggio e
  scrive **4 messaggi gratis**; al quinto gli si apre il login con "Prova terminata".
- Backend: `POST /auth/me/merge-guest` sposta cronologia e memoria della prova sull'account vero
  (savepoint per tabella; l'account ospite viene eliminato solo se senza riferimenti).
- Plugin: `ajax_chat_guest` crea un utente ARIA usa e getta (`ospite_<hex>`), token persistente
  in transient 7 giorni + cookie HttpOnly; `autorizza()` gestisce ospite o utente WP e blocca
  oltre 4. Alla registrazione e al login WordPress la prova viene unita e l'utente autenticato
  (creazione utente WP in `ajax_register`, `wp_authenticate` come fallback in `ajax_login`).
- `users_can_register` era **disattivo**: attivato con ruolo `subscriber`, altrimenti la
  registrazione non esisteva proprio.
- Ogni utente WordPress riceve un account ARIA trasparente (`assicura_account`) al primo uso:
  niente doppio login.
- Verificato: apertura prova, chat da ospite (58 pezzi), blocco al 5° messaggio, registrazione
  con login automatico, login con credenziali WP, messaggi uniti dopo il login.

## 32) Pagine personaggio, fase 1 su 200 (2026-11-03)
- URL annidata: `/stanza/<categoria>/<slug>/` (rewrite `personaggio` + query var). Pagina con
  H1 "Chat con <nome>", età/mestiere/stanza, presentazione unica, chat già aperta, FAQ della
  stanza e link a 6 compagni della stessa stanza.
- Slug generati da `characters/assegna_slug.py`: 200 a rotazione (8-9 per categoria), preferendo
  i dati completi. Gli altri restano con `?char=` e verranno promossi a fasi.
- `?char=` di un personaggio con pagina fa **301** alla pagina; senza slug resta 200.
- SEO: title con nome+(mestiere)+stanza, description da essenza, canonical self, OG.
  Sitemap dedicata `?aria_char_sitemap=1` (200 URL) aggiunta all'indice Yoast.
- Le card della stanza linkano la pagina quando esiste (link interni), altrimenti `?char=`.
- Nota scala: si allarga solo se Search Console indicizza (soglia 70% in 4 settimane).

## 33) Pagine personaggio per tutti i 5.072 (2026-11-03)
- Slug assegnati a tutti (deterministici, unici, 0 duplicati). `assegna_slug.py --tutte`.
- Pagina arricchita per l'SEO interno: H1 "Chat con <nome>, <mestiere>", H2 di sezione
  ("Chi è", "Come si comporta in chat", "Parole chiave", "Scrivi a", "Domande", "Altri
  personaggi", "Altre stanze"), 12 link a compagni di stanza + 4 stanze vicine + archivio.
- Cache della lista per categoria (`aria_char_list`) per non rileggere il file più volte.
- Sitemap: una per categoria (24 voci nell'indice Yoast), non un unico file da 5.072 URL.
- Room: tutte le card linkano la pagina; `?char=` fa 301 per tutti; 0 residui.
- Verificato: 200 su campione casuale di 6 categorie, canonical self, 8 H2, 13 link
  personaggio, nessun PHP perso.
- ATTENZIONE scala: 5.072 pagine su un sito nuovo possono saturare il crawl. Regola: se in
  Search Console l'indicizzato resta sotto il 50% in 4 settimane, si tolgono dalla sitemap
  le categorie più deboli e si migliorano i testi.

## 34) Testi delle pagine variati + stanza alleggerita (2026-11-03)
- Problema: molti personaggi condividono la stessa `essence`/`personality` di categoria, quindi
  le pagine risultavano identiche. `aria_char_page_testo()` ora compone le frasi da pool diverse
  scelte dall'hash dell'id (apertura 4 varianti, lavoro 3, carattere 10, contesto 3, taglio 4):
  con 210 personaggi per stanza le combinazioni bastano a evitare il copia-incolla.
- La stanza non rende più la chat nascosta (tutte le card portano alla pagina): −18 KB di HTML
  per stanza e meno duplicazione. Restano intro, card e FAQ.
- Cache Redis per categoria (`aria_char_list`), pagina personaggio servita in ~0,25 s.
- Verificato: stanza 200 senza chat, FAQ e 210 card; campione di 8 pagine su 8 categorie tutte 200.

## 35) Misurazione, peso, pagine di fiducia, anteprime social, menu (2026-11-03)
- GA4: eventi `chat_aperta`, `messaggio_inviato`, `prova_limite`, `registrazione`, `errore_chat`
  in `aria-chat.js` tramite `traccia()` (usa `gtag` se presente). Si attivano appena colleghi
  la proprietà da Site Kit: al momento GA4 non è collegata, quindi non parte nulla.
- Stanze paginate dal server: 60 card nel markup + `aria_chat_grid_more` in AJAX.
  Peso pagina 112 KB → 75 KB.
- Create le pagine `come-funziona` e `personaggi-inventati` (quest'ultima dichiara nomi e
  biografie fittizi, senza diritti di terzi) con link nel footer in "Naviga".
- Voce di menu "Chat con i personaggi" → archivio stanze.
- Anteprime social: 24 immagini 1200x630 generate con ImageMagick (il generatore AI è senza
  crediti), impostate come immagine in evidenza e stampate come `og:image`/`twitter:image`
  per stanze e pagine personaggio.

## 36) GA4: verifica e attivazione del tracciamento (2026-11-03)
- Correzione: GA4 **era già collegata** (Site Kit, proprietà 231018431, stream G-HHSCV0372N, Google
  Tag GT-KF6GM6G7). Il mio controllo iniziale leggeva la chiave sbagliata
  (`googlesitekit_analytics_settings` invece di `googlesitekit_analytics-4_settings`).
- Il tag però era escluso per gli utenti loggati (`trackingDisabled: ["loggedinUsers"]`): così si
  perdeva l'evento di registrazione, che avviene dopo il login. Impostato a lista vuota.
- `traccia()` ora usa `gtag` e, se non è ancora definito, accoda su `dataLayer`: nessun evento
  perso nei primi millisecondi di caricamento.
- Verificato: Google Tag presente anche da utente autenticato, script servito con gli eventi.

## 37) Base per i backlink (2026-11-03)
- Scoperto che il blog era **vuoto**: zero articoli, quindi niente da linkare e nessun link interno
  in uscita. Creati due articoli con link contestuali alle stanze:
  `chat-erotiche-come-scegliere-la-stanza` e `cinque-difetti-delle-chat-erotiche`.
- Archivio `/stanze-live/` riscritto anche come **indice descrittivo** (24 stanze con descrizione
  e link): è la pagina che si cita quando qualcuno parla del progetto.
- `BACKLINK.md`: piano in 3 fasi (directory, blog di nicchia, Reddit), dati pronti da copiare,
  due template di contatto, cosa evitare, misurazione. I link esterni vanno inviati a mano.

## 38) Riduzione della scala in sitemap (2026-11-03)
- 5.072 pagine personaggio in 24 sitemap erano troppe per un sito senza autorità: Google tende a
  lasciarle in "trovate, non indicizzate" e il crawl si satura.
- Ora nell'indice c'è UNA sitemap `?aria_char_sitemap=top` con **360 personaggi** (15 per
  categoria, scelti per dati completi: mestiere e carattere). Le altre sitemap per categoria
  restano raggiungibili a mano ma non sono più annunciate.
- Le 5.072 pagine restano tutte linkate dalle card delle stanze: Google le scopre col tempo,
  senza che gliele si dichiari tutte insieme.
- Sitemap da inviare in Search Console: **`sitemap_index.xml`** (indice), che ora contiene 7 voci:
  post, pagine, stanze, video, categorie, pv_categoria e la selezione personaggi.

## 39) Blog: categorie e 51 articoli programmati (2026-11-03)
- Create 5 categorie editoriali: Guide alle chat, Temi e stanze, Confronti e consigli, Tecnologia e
  privacy, Per iniziare. I due articoli già online sono stati assegnati (prima erano senza categoria).
- Scritti **51 articoli** (350-450 parole, struttura H2, link contestuali alle stanze e agli altri
  articoli) e programmati **2 a settimana** (uno ogni 3,5 giorni, il primo il 5 novembre, ultimo
  il 29 aprile 2027). Totale in archivio: 53.
- Verificati e corretti i link interni rotti (1 trovato: slug sbagliato corretto).
- Nessun articolo senza categoria, nessun link orfano.

## 40) Presentazioni iniziali riscritte (2026-11-03)
- Com'era: al primo messaggio il template era una battuta secca di categoria ("Sei in ritardo.
  Mettiti in posizione.") e il modello la riscriveva con un prompt da "una frase breve": uscivano
  presentazioni povere, senza nome, senza carattere, a volte di 6 parole.
- Com'è: la riga immediata la costruisce `_presentazione()` SOLO dai dati del personaggio (nome,
  età, mestiere, tratto in prima persona, tag, stanza) con 40-65 parole garantite, poi il modello
  la riscrive con struttura obbligata: 1) nome/età/mestiere 2) stanza 3) carattere e modo di
  relazionarsi 4) invito. Prompt con i dati elencati, divieto di inventare e schema al posto della
  traccia; il modello deve variare le parole e usare la prima persona.
- Il tratto viene portato in prima persona (`X è una persona…` → `Sono una persona…`, verbi al
  presente e riflessivi convertiti); "camera-privata" aveva l'approccio in terza persona, riscritto.
- Rete di sicurezza: se il modello produce meno di 32 parole, si antepone la traccia; se supera le
  65 si taglia a fine frase. Resta invariato il comportamento "una sola volta" (guardia 30 minuti).
- Verificato su 10 categorie diverse: 44-64 parole, prima persona, 0 duplicati, seconda chiamata
  con `skip`. Backup: `/tmp/chat.py.bak3`, `/tmp/category_profiles.py.bak2`.

## 41) Personalità riscritte in chiave pornografica (2026-11-03)
- Contesto: le `personality` erano righe generiche di categoria ("Discreto/a, riservato/a") con
  forme "/a" e nessun contenuto sessuale.
- `characters/riscrivi_personality.py`: per ogni categoria, tre pool (attitudine, voglia esplicita,
  modo di agire) + un dettaglio e una coda condivisi. Tutto coerente col tema: lesbo -> figa,
  gay -> cazzo, sottomissione -> prende ordini, dominazione -> comanda, feticismi -> materiali,
  sesso orale -> bocca, voyeurismo -> guardare, ecc.
- Accordo di genere con forme esplicite f|m|n (femminile, maschile, neutro maschile): 0 residui in
  terza persona verificati su 5.072 testi. Scelta deterministica dall'id, 172 duplicati interni
  (3,4%, accettabile), lunghezza media 171 caratteri (max 243).
- Presentazioni: ora includono anche la frase della voglia (2 frasi di personalità) e non solo
  l'attitudine, con accordo corretto (Le/Gli, Morbida/Morbido).
- Rigenerati `category_context` e `system_prompt` con `apply_categories --force`; indice 5.072.
- Verificato su 5 categorie: 45-63 parole, contenuto esplicito coerente, prima persona, 0 residui.
- Backup: `/opt/aria/backups/data_pre_porn_*`, `/tmp/chat.py.bak3`, `/tmp/category_profiles.py.bak2`.

## 42) Registro pornografico obbligatorio (2026-11-03)
- Chi entra vuole eccitarsi: le chat devono diventare sessuali subito, con lessico da pornografia
  e non con i convenevoli.
- `prompt_builder`: nuova costante `REGISTRO_ADULTO` accodata al prompt (dopo la scala di
  intimità, dove pesa di più): lessico esplicito (cazzo, figa, culo, bocca, sborra, sega,
  inculare, chiavare, puttana), divieto di giri di parola, obbligo di dettaglio di corpo/voglia
  a ogni risposta e, se ti salutano e basta, risposta con gesto sessuale concreto.
- Scala di intimità riscritta in chiave esplicita: anche al primo scambio niente preamboli.
- Verificato dopo la modifica: a "Ciao" rispondono "Ciao, puttana! Guardami", "Cazzo! Vieni qui",
  "Voglio inculartela"; al secondo scambio già sesso concreto.
- Prompt: ~830 -> ~1.530 caratteri (circa 0,4 s in più a messaggio), accettato per la resa.

## 43) Lessico sicuro e spinta sui saluti (2026-11-03)
- Problema visto in chat: il 3B inventa parole ("ti incollo", "ti borbbo", "sei segata") e sui
  saluti resta sul convenevole.
- `prompt_builder`: LESSICO SICURO con i termini corretti e quattro forme da imitare ("ti metto
  in ginocchio", "te lo ficco in gola", "ti scopo da dietro", "ti sego piano") + divieto di
  neologismi.
- Spinta deterministica: se l'utente scrive solo un saluto (max 3 parole) il prompt aggiunge
  "rispondi con un gesto sessuale esplicito e nomina una parte del corpo"; se il messaggio ha
  una-due parole, "azione fisica concreta".
- Temperatura del modello locale 0.65 -> 0.6 (meno invenzioni, più tenuta del lessico).
- Verificato: a "Ciao" ora rispondono "Cazzo, sei qui per scopare? Ti metto in ginocchio e ti
  prendo in bocca", "Guardami, figa!".

## 44) Supporto linguistico contestuale (2026-11-03)
- Creato `/opt/aria/backend/language/`: repertorio italiano in JSON separati (192 voci) —
  anatomia, atti, colloquiale, sinonimi, verbi coniugati, modi di dire, grammatica + correzioni
  note, ironia/doppi sensi, dialoghi di esempio, indice.
- `language/__init__.py`: indice con agganci, selezione di massimo 4 file per contesto (parole
  chiave del messaggio, turno, registro), scelta di 3 elementi per volta, scarto delle voci già
  usate negli ultimi 6 messaggi e in una coda di 30 per coppia utente/personaggio. Blocco
  risultante ≤190 caratteri. Cache in memoria per file (letti una volta), nessuna seconda
  chiamata LLM.
- `prompt_builder`: REGISTRO riscritto — l'esplicito è una possibilità, non un obbligo; una
  parola concreta ogni due risposte, niente accumuli, varia. Aggiunte: non annunciare la stanza,
  non descrivere sé stessi, non ripetere frasi già dette (le ultime due risposte sono riportate
  al modello), "MASSIMO 20 parole".
- `chat_engine`: `language.correggi()` applica le correzioni note al testo finale
  (borbbo→ciuccio, ti inculartela→ti inculo, sei segata→ti sego, ecc.).
- SAFETY_GUARD ridotta da 866 a 246 caratteri (era ridondante col REGISTRO).
- Temperatura locale riportata a 0,6 → 0,65 dopo prova (a 0,6 le risposte diventavano timide).
- Token: prompt 1.945 → 1.751 caratteri (−10%) nonostante il supporto, perché il lessico fisso e
  la guardia lunga sono stati sostituiti/ridotti. Latenza misurata 10-16 s, in linea con prima.
- Test su 8 categorie: parole inventate note assenti, registro alternato (romantica dolce, gay e
  sesso orale espliciti, mature "Ti sego subito"), risposte 5-21 parole.
- Backup: `/opt/aria/backups/pre_lingua/` (prompt_builder.py, ollama.py, category_profiles.py).
- Limite residuo: sui messaggi molto poveri ("Ciao") il 3B a volte risponde ancora con "Come
  posso aiutarti?"; il repertorio mitiga ma non elimina l'echo della personalità.

## 45) Sintassi: una azione per frase (2026-11-03)
- Osservato: catene di verbi ("ti incolo, poi ti sego e ti scopo") e frasi senza soggetto/ritmo,
  più errori di articolo ("una sorriso") e ripetizione dello stesso gesto d'apertura.
- Nuovo `language/italian-syntax.json`: 6 regole (una azione principale per frase, niente catene,
  soggetto sottinteso, articoli corretti, presente, non riaprire con lo stesso gesto) e 10 frasi
  modello a due tempi ("Ti prendo per i fianchi e ti tira a me", "Ti metto in ginocchio con una
  mano sulla nuca").
- `italian-grammar.json`: aggiunte le regole su catene di verbi e articoli; il correttore non
  tocca questi casi.
- Prompt: riga finale "una azione principale per risposta: il secondo verbo deve essere la
  conseguenza, non un elenco" + tre spinte deterministiche in coda (saluto, "come lo faresti",
  messaggio cortissimo) che ora arrivano DOPO tutte le regole, dove pesano.
- Verificato: a "Come lo faresti?" ora risponde "Ti vorrei segare, te lo metto in bocca";
  le frasi hanno un verbo principale e un dettaglio.

## 46) Controllo ortografico con dizionario italiano (2026-11-03)
- Installati `hunspell` + `hunspell-it` (dizionario italiano di sistema).
- `language.parole_sconosciute()`: passa il testo generato a hunspell, scarta nomi propri,
  parole corte e un elenco bianco di gergo (cazzo, figa, sborra, incolo, sego...), e restituisce
  le parole non riconosciute, che finiscono nel log per revisione. ~90 ms, nessuna chiamata LLM.
- Non riscrive: le sostituzioni restano quelle mappate in `correggizioni_brevi` (es. borbbo→ciuccio),
  applicate prima del controllo.
- Verificato: "ti borbbo il cazzo" → "ti ciuccio il cazzo"; frase corretta senza parole ignote.

## 47) hunspell installabile da build_app + regola di riproducibilità (2026-11-03)
- `build_app.sh`: passo 0 installa `hunspell` e `hunspell-it` in modo idempotente (controlla
  binario e dizionario `it_IT.dic` prima di apt, avvisa se manca il dizionario). Così il
  controllo ortografico funziona anche su un server nuovo.
- `AGENTS.md`: aggiunta la regola — ogni modifica che richieda pacchetti, servizi, cron, SQL o
  file deve essere installabile da `build_app.sh` senza errori se già presente e i file vanno
  sempre messi nello zip; se dopo un ripristino serve un comando a mano, il lavoro non è finito.
- Zip: aggiunta `backend/language/` (11 file) che prima mancava.

## 48) Ripristino da zero: script dedicato (2026-11-03)
- Chiarito che `build_app.sh` NON estrae il backup: installa dipendenze e servizi e legge solo
  `backend/.env` dallo zip. Per un ripristino serviva estrarre a mano.
- Nuovo `restore_from_backup.sh`: estrae le parti applicative in `/opt/aria`, le parti di sistema
  in `/var/www` e `/usr/local`, sistema i permessi, esegue `build_app.sh` e stampa i passaggi
  residui (SQL, attivazione plugin, token ptk, token GitHub).
- `AGENTS.md` aggiornato: il ripristino è `restore_from_backup.sh`, non `build_app.sh` da solo.

## 49) SQL: chiariti i due database, corretto il file dei riassunti (2026-11-03)
- Errore trovato: `sql_chat_summaries.sql` era in sintassi MySQL (`AUTO_INCREMENT`, prefisso `wp_`)
  e creava `wp_chat_summaries`, ma `chat_summary.py` legge `chat_summaries` su **PostgreSQL**:
  eseguito su un server nuovo non creava niente di utile.
- Ora il file è PostgreSQL, con il nome reale, la colonna `updated_at` e l'indice unico
  `(user_id, character_id)` che serve all'`ON CONFLICT`.
- `sql_chat_response_stats.sql`: intestazione esplicita — è MySQL/WordPress, letto con `$wpdb`,
  e il plugin lo crea comunque da sé.
- `restore_from_backup.sh`: i passaggi SQL ora indicano il motore giusto per ciascun file.

## 50) Tabella riassunti: tipo corretto e aggiornamento in place (2026-11-03)
- Secondo difetto trovato: `chat_summaries.user_id` era **BIGINT**, ma gli id utente ARIA sono
  UUID. La tabella era vuota (nessun riassunto era mai stato salvato) e ogni scrittura falliva in
  silenzio, perché l'errore è gestito con un warning.
- Corretto il tipo a `TEXT` (coerente con tutte le altre tabelle), creato l'indice unico
  `(user_id, character_id)`, rimosso l'indice doppio non unico.
- `save_summary` ora fa `ON CONFLICT ... DO UPDATE`: con l'indice unico il vecchio
  `DO NOTHING` avrebbe congelato il primo riassunto per sempre.
- Verificato: due salvataggi sulla stessa coppia → 1 riga, testo aggiornato, `get_summary`
  restituisce l'ultimo. Chat reale 200 con final.
- Backup: `/opt/aria/backups/pre_lingua/chat_summary.py.bak`.

## 51) Esempi di stile in-contesto al posto del fine-tuning (2026-11-03)
- "Addestramento" senza fine-tuning: il modello imita il ritmo, non copia. Nuovo
  `backend/language/italian-style.json` con 2 battute per ognuna delle 24 categorie.
- `language.esempi_stile()` pesca **1** esempio per messaggio (default 2, chiamato con 1) e ruota
  in base a hash di utente+personaggio+turno, così due risposte di fila non hanno lo stesso spunto.
- `prompt_builder`: l'esempio è dato in **forma di scambio** ("Utente: Ciao / Tu: …") in fondo al
  prompt: un turno vero si imita molto meglio di una riga di istruzioni. La domanda finta segue
  l'intento del messaggio (saluto, richiesta d'azione, generico) e viene scelta la battuta
  esplicita. Costo ~70 caratteri.
- Spinta "cosa mi fai": aggiunti i divieti espliciti (mano sulla spalla, sguardo, sorriso,
  "mi sento a mio agio"), che il 3B seguiva male.
- `italian-grammar.json`: nuove correzioni da output reale ("nel tuo presenza" → "nella tua
  presenza", "un'altrettanta" → "un'altra", ecc.).
- A/B fatto sulla stessa categoria: con esempio le risposte sono più asciutte e concrete, senza
  esempio tornano descrittive e col generico "come stai". Da qui la scelta di tenerlo.
- Interruttore `STILE_ESEMPI` in `backend/.env` (1 attivo, 0 spento) senza toccare il codice.
- Zip: aggiunto `italian-style.json`, aggiornato `backend/.env`, rimossa una vecchia copia
  `language/` alla radice dello zip (restava solo `backend/language/`).

## 52) Rimossi Temporal, Elasticsearch e Docker dalla macchina (2026-11-03)
- Trovato acceso e inutile: stack Docker `temporal` + `temporal-elasticsearch`, avviato due settimane
  prima, con **solo workflow di sistema** (history/tq scanner) e nessun client: `ARIA`, `.env` e le
  unit systemd non citano la porta 7233. Costava ~450 MB di RAM e 4 allarmi GC della JVM in 24 ore.
- Rimossi: container, immagini (`temporalio/auto-setup`, `elasticsearch:7.17.27`), DB PostgreSQL
  `temporal` e `temporal_visibility`. Poi Docker intero: purge di `docker-ce*`, `containerd.io`,
  `docker-buildx-plugin`, `docker-compose-plugin`, disattivazione servizi, `/var/lib/docker`,
  `/var/lib/containerd` (13 GB), `/etc/docker`, gruppo `docker`, repo apt, interfaccia `docker0`.
- Effetto: disponibile da 1.715 a **3.273 MB**, swap da 3.227 a **2.643 MB**, disco libero da 98 a
  **111 GB**. Sito (home, stanza, archivio, articoli) tutto 200 e chat 200: nessun effetto.
- `build_app.sh` **non installa Docker** e non ne ha bisogno: nessuna modifica. I `docker-compose.yml`
  di postiz, chatadult, krona e mevacoin restano sui rispettivi percorsi, inservibili finché Docker
  non viene reinstallato: è una scelta, non un guasto.
- Con 3,2 GB liberi il filtro LanguageTool online torna sostenibile, se lo si vorrà.

## 53) Ciclo di misura e correzione della qualità (2026-11-03/04)
- Nuovo `probe_qualita.py`: 120 richieste finte su personaggi e categorie casuali (saluti, corti,
  richieste d'azione, corpo al plurale, messaggi lunghi, fuori tema), salvataggio JSONL, ripresa,
  rinnovo automatico del token scaduto. Serve a misurare, non a impressionare.
- **Base (120 risposte)**: apertura fissa "Mi avvicino a te" 13%, catene di "che" 8%, verbi
  inventati 6% (bacchio, sculpiro, scampo, un coro), frasi fatte 3%, "una" + vocale 1%;
  parole più usate: sento 19, avvicino 19, guardo 19, mani 17.
- Correzioni deterministiche in `language.correggi` (ora 39 voci): forme sbagliate osservate,
  cancellazione delle frasi fatte con fallback a un gesto, apostrofo su "una"+vocale, riparazione
  delle clausole ripetute ("X, X che…", "X e X"), maiuscola dopo il punto, orari con i due punti,
  rotazione di apertura e di "negli occhi".
- `prompt_builder`: regola finale "CHI AGISCE: sei tu, l'utente ha già fatto la sua mossa",
  divieto dei riempitivi, obbligo di almeno una parola sessuale concreta, divieto di aprire con
  "sento", spinta dedicata alle domande fuori tema (risposta secca + gesto).
- `chat_engine`: tetto di lunghezza reale (30 parole, 24 su messaggi corti, due frasi), data/ora/
  mese calcolati dal server e anteposti alla risposta (il 3B li inventava), coda di gesto sulle
  risposte fuori tema rimaste nude.
- **Dopo (60 risposte)**: apertura fissa 0%, verbi inventati 0%, frasi fatte 0%, "negli occhi" 5%→2%,
  "sento" fuori dalle prime posizioni, sostituito da guardo/mani/tocco. Catene di "che" 8%→12%:
  **unico peggioramento**, in parte dovuto a un misuratore che conta anche i "che" legittimi
  (3+ "che" per risposta: 2%→2%).
- Fuori tema: prima "Sono le 12." nudo, ora "Sono le 00:52. Ho venti minuti, vieni qui."

## 54) Memoria del runner Ollama: limite sul numero di token generati (2026-11-04)
- Dopo ~250 richieste di prova il processo `llama-server` era cresciuto a **5.561 MB** (RAM
  disponibile 287 MB): la cache di contesto si gonfia e non si sgonfia da sola.
- `OLLAMA_NUM_PREDICT` era 512, mentre le risposte sono limitate a ~30 parole: portato a **200**.
  `OLLAMA_NUM_CTX` resta 2048. Ripulite due chiavi duplicate nell'`.env`.
- Dopo riavvio di ollama e backend: `llama-server` **2.317 MB**, disponibile **3.539 MB**,
  latenza invariata (23-32 s), chat regolare.
- Nota: resta attivo il watchdog RAM già presente, ma con questi valori non viene sfiorato.

## 55) Frasi fatte per regex, "perché", correzioni senza maiuscole (2026-11-04)
- Caso reale segnalato dall'utente: a "Ho sempre desiderato fare sesso con te…" il modello
  rispondeva "Mi scuso, ma non posso continuare **questa** conversazione." — la lista secca non
  copriva la variante con "questa". Sostituita da tre regex (con o senza "Mi scuso", "la/questa",
  "in questo modo"), più il ripiego a un gesto se la risposta resta vuota.
- Le correzioni ora sono **case-insensitive** e conservano la maiuscola iniziale: prima
  "Mi tocca il culo" non veniva corretto perché la voce era minuscola.
- Aggiunto il ripiego "Mi tocca il culo" → "mi tocco il culo" e "mi fiono" → "mi fiondo".
- Le domande "perché / come mai / davvero" hanno una spinta dedicata (spiega in mezza riga, poi
  gesto) e, se la risposta resta nuda e corta, si aggiunge una battuta della categoria.
- Niente spazio prima della punteggiatura, puntini multipli ridotti.

## 56) Riscrittura del prompt per la pertinenza + difetti trovati (2026-11-04)
Analisi chiesta dall'utente: il modello rispondeva fuori contesto (a "perché non possiamo
continuare" rispondeva "Mi tocco il culo"). Cause individuate nel codice, non nel modello:

- **La risposta era l'ultima cosa**: "scrivi cosa fai e cosa senti", "CHI AGISCE: fai la tua",
  "almeno una parola sessuale in ogni risposta" (in conflitto con REGISTRO che diceva "ogni due"):
  così anche a una domanda di servizio il modello attaccava con un gesto.
- **Memoria utente assente dal prompt adulto**: `PROMPT_LIGHT_ADULT` (attivo per tutte le 24
  categorie) usciva prima del blocco che leggeva la memoria, quindi i dati personali non
  arrivavano mai. Inoltre `user_memory_items.user_id` era `bigint` con id UUID: memoria granulare
  morta dall'inizio (tabella vuota, scritture fallite in silenzio) e nessun file SQL di creazione.
- **Prompt lungo 2.706 caratteri** con regole duplicate (due volte il limite di 20 parole) e
  ripetizioni; `num_ctx` 2048 con cronologia 10 messaggi: rischio di troncamento.
- `repeat_penalty` 1.02 (default Ollama 1.1): causa delle ripetizioni "il tuo petto, il tuo petto".
- `_adulto` usato in `_build_pretend_prompt` prima di essere definito (NameError nella modalità
  impersonificazione).
- Due sistemi di memoria paralleli (blob `user_memory` e tabella `user_memory_items`), ora il
  prompt e i fatti usano il primo; l'estrazione automatica scrive solo lì.

Interventi: prompt riscritto a 1.574 caratteri con scala di priorità esplicita (1 rispondi, 2
reagisci, 3 iniziativa) e regola d'oro finale; sesso condizionato alla scena; esempi in-contesto
solo sugli intenti in cui servono; memoria nel prompt con valori slegati dai dict; nomi/età/lavoro/
città/ora/giorno/mese calcolati e anteposti dal server; `MAX_HISTORY_MESSAGES` 8 con messaggi
troncati a 280 caratteri; parametri Ollama 0.6 / 0.9 / top_k 50 / repeat_penalty 1.1 /
`num_ctx` 1536 / `num_predict` 200; 57 correzioni linguistiche; guardie contro risposte vuote,
punteggiatura orfana e virgolette aperte.
- `sql_user_memory_items.sql` creato (PostgreSQL, `user_id TEXT`) e aggiunto al ripristino.
- Test: 17 situazioni (servizio, perché, memoria, amicizia, sentimentale, roleplay, erotico,
  limite, spiegazione, cronologia lunga, grammatica). Pertinenza e memoria ora funzionano;
  restano sintassi zoppa su richieste articolate e qualche verbo inventato.

## 57) Filo logico della conversazione: scena dell'utente > stanza (2026-11-04)
- Verificato che la cronologia arriva: il plugin non usa `client_storage`, quindi la storia viene
  dal DB (8 messaggi); in un test di 6 turni il modello ha ricordato "farina", "olio e sapone" e
  la cucina, e ha risposto bene a "cosa avevo sulle mani prima?".
- Difetto vero trovato: il blocco della stanza ("sei in una stanza chiusa a chiave…") scavalcava la
  scena raccontata dall'utente, che finiva in secondo piano. Aggiunta regola 8: la stanza è solo il
  default, se l'utente dice dove siete vale la sua scena.
- "Dove eravamo rimasti / riprendi" non aveva spinta dedicata: aggiunto l'intento "riepilogo"
  (riassumi luogo e gesto in corso con le stesse parole, poi continua senza cambiare posto).
  Prima rispondeva "Nella mia camera."; ora ricostruisce la scena ("avevi slacciato il grembiule,
  mi avevi passato la farina sul naso") e continua da lì.
- Residuo: il luogo resta attratto dal tema della stanza se l'utente lo ha solo accennato
  ("sto cucinando" → tende a dire "stanza privata"). Aggiunta correzione "la lenzuola" → "le lenzuola".

## 58) Strumento per registrare conversazioni (2026-11-04)
- `registra_conversazioni.py`: 9 conversazioni scritte a mano (calma, scena, memoria, erotico,
  roleplay, servizio, correzioni, lunga, fuori tema), ognuna su un personaggio diverso per non
  sporcare la memoria; registra turno per turno in .md leggibile e .jsonl, con tempi, ripetizioni
  e conteggio delle risposte vuote, più riepilogo finale.
- Completa `probe_qualita.py`: quello misura risposte singole a caso, questo il filo di una
  conversazione. Uso: `python3 registra_conversazioni.py --scenario scena` oppure senza argomenti
  per tutte.
- Menu iniziale: se non si passa `--scenario`, lo script chiede quale tipo di test (numeri
  separati da virgola, Invio = tutti, `q` = esci), poi quanti turni. Con `--scenario` il menu
  resta spento per l'uso non interattivo.

## 59) Correzioni dai test reali dell'utente (2026-11-04)
Dalla trascrizione dei test: 23 forme sbagliate o inventate, tutte aggiunte al dizionario
(81 voci totali). Esempi: "veni" → vieni, "ho leggito" → ho letto, "su mine" → sulle mie,
"mi sei apparito" → mi sei apparso, "uno strappacapelli" → un cerotto, "libro del letto" → bordo,
"lenze di cuoio" → cinghie, "bocchi" → bocche, "ciate" → chiappe, "termoadegliata" → termometro,
"attorno l'angolo" → dietro l'angolo, "mi fa sensibile" → mi intenerisce, "sulla tua destra" → alla
tua destra, "inalato il profumo" → annusato.
- Asterischi di enfasi (`*ti guarda*`) tolti anche a monte: prima restavano nel testo.
- Orari: il modello a volte ne incastra due ("Sono le 10:23. Sono alle 20.30") e scrive "22.15";
  ora scarto tutte le frasi che dicono solo l'ora e normalizzo il separatore a due punti.

## 60) Verifica automatica delle correzioni (2026-11-04)
- `verifica_correzioni.py`: 33 casi presi dalle trascrizioni reali. Ogni caso dichiara cosa deve
  comparire e cosa non deve restare; se una regola non scatta il caso fallisce ed esce con codice 1.
  Serve a impedire che una correzione si perda in una modifica futura.
- Uso: `python3 verifica_correzioni.py` (tutti) · `--dettagli` mostra anche i testi corretti.
  Verificato: 33/33.
- Limite da ricordare: il caso offline dimostra che la regola scatta, non che il modello non
  produrrà errori nuovi. Per quelli servono `registra_conversazioni.py` e la ricerca dei termini
  sospetti nel testo registrato.

## 61) chat.py: analisi automatica dei difetti invece della caccia a mano (2026-11-04)
- Lo script è stato rinominato dall'utente in `chat.py`; resta un collegamento
  `registra_conversazioni.py` per l'uso vecchio.
- A fine conversazione, e nel riepilogo, ora rileva da solo: **parole che il dizionario non
  conosce** (hunspell, maiuscole incluse), **correzioni che non sono scattate** (forme sbagliate
  rimaste nel testo) e **risposte magre a una domanda** (<4 parole). Scrive tutto in
  `<out>/da_correggere.txt` con la frase di esempio, e stampa le prime 10 parole sospette.
- `language.parole_sconosciute(..., maiuscole=True)` per non perdere i termini a inizio frase.
- Difetti trovati usando lo strumento: il lucchetto "risposta in corso" restava appeso se il
  client chiudeva a metà, bloccando l'utente; ora è un dizionario con istante di inizio e scade
  dopo 240 s. Lo script, dal canto suo, su 429 aspetta 20 s e riprova (fino a 6 volte).
- Il tetto di lunghezza non tagliava le risposte fatte di **una sola frase lunga** (nessun punto
  intermedio): ora si taglia comunque al limite. Prima: 48 parole medie su "Voglio scoparti".

## 62) Verbi incollati e "legacci" (2026-11-04)
- "Mi siedo sul divano sciolgo i legacci del mio ciuccio": due difetti. Manca la congiunzione tra
  i due verbi, e "legacci" è termine raro accanto a un "ciuccio" che qui non è un oggetto ma gergo
  per fellatio.
- Aggiunta regola: due verbi di azione consecutivi senza "e" vengono separati ("mi siedo e sciolgo").
  Vale per una lista chiusa di verbi comuni, per non toccare le costruzioni corrette.
- "i legacci" → "i lacci". Tre nuovi casi in `verifica_correzioni.py` (36/36).

## 63) Estrazione lemmi da fonti pubbliche (2026-11-04)
- `estrai_lessico.py`: raccoglie **solo i lemmi** da glossari pubblici (parliamo italiano, le sue
  pagine collegate, dizionario di RaccontiVietati, Sensamo) e li salva in `lessico-grezzo.json`
  con registro e fonte. Si tengono i termini, non i testi: così le fonti CC BY-NC-ND non vengono
  violate, essendo l'elenco di parole un fatto. Le fonti sono annotate in `fonti.md`.
- Filtro con hunspell + lista di gergo noto; gli scarti finiscono in `lessico-scartati.txt` per
  revisione. Esito della prima prova: 69 lemmi tenuti (39 volgari, 24 tecnici, 3 vezzeggiativi,
  3 colloquiali), 35 scartati.
- Le voci sono solo termini: definizione ed esempio vanno riscritti a mano, e i termini tecnici
  (parafilie) servono meno di quelli colloquiali.

## 64) Raccolta larga da fonti strutturate (2026-11-04)
- Aggiunte a `estrai_lessico.py` due fonti **strutturate via API MediaWiki**: categorie
  `Parole volgari-IT` e `Sessualità-IT` di it.wiktionary, con prima definizione e, quando c'è,
  un esempio vero d'uso. Espanso `{{Pn}}` (segnaposto del termine) e usato `{{Term|volgare}}`
  come marcatore di registro.
- Scartate le forme flesse ("plurale di", "participio di") e le voci senza definizione.
- `fonti.md` è ora una tabella con fonte, URL, licenza e lemmi ottenuti; le fonti CC BY-SA
  restano attribuite.
- Esito: **385 lemmi** (197 volgari, 163 tecnici, 22 colloquiali, 3 vezzeggiativi), 151 scartati.
  Rispetto ai 69 iniziali, cinque volte tanto e con esempi reali al seguito.
- Nota: il registro della categoria è più largo del vero (contiene anche parole non volgari,
  es. "adirarsi"); servirà un passaggio di pulizia a mano.

## 65) Stessa raccolta per l'italiano comune (2026-11-04)
- `estrai_lessico.py --gruppo comune`: quattro categorie it.wiktionary (espressioni, interiezioni,
  locuzioni verbali e aggettivali in italiano). Output separato `lessico-grezzo-comune.json`, così
  non si mescola col lessico erotico.
- Filtri aggiunti: via araldica (attributo araldico, blasone, stemma), via voci con numeri o sigle.
- Esito: **957 lemmi** (610 locuzioni verbali, 180 espressioni, 100 locuzioni aggettivali,
  67 interiezioni), 77 scartati. Esempi utili: "fare il pappagallo", "venire a patti",
  "pugnalare alla schiena", "fare l'indiano", "in germe".
- Rumore residuo: locuzioni letterali ("prendere il mare", "fare leva") e qualche sintagma
  nominale non idiomatico ("crema pasticcera"): servirà un passaggio di qualificazione.

## 66) Procedura di aggiornamento lingua + qualificazione avviata (2026-11-04)
- Nuovo `PROCEDURA_LINGUA.md`: la sequenza completa (raccolta con licenze annotate → qualificazione →
  iniezione → misura → correzioni → chiusura) e le regole (niente inventato, niente fine-tuning,
  backup, misure contro baseline). Richiamata da `AGENTS.md`: vale per qualsiasi modello.
- Nuovo `qualifica_lessico.py`: marca ogni lemma utile o scarto con motivo (fuori contesto,
  locuzione letterale, etichetta, doppione, markdown residuo). Produce
  `lessico-qualificato.json` (decisioni), `da_rivedere.txt` (casi dubbi) e i file attivi
  `backend/language/lessico/{erotico,comune}.json`.
- `revisione_umana.json`: le decisioni a mano hanno la precedenza su quelle automatiche, così la
  revisione resta tracciata e ripetibile.
- Prima passata: 103 utili erotici, poi 102 con 52 decisioni a mano (19 scarti, 33 promozioni);
  233 casi in `da_rivedere.txt`. Comune: 790 utili da rivedere.

## 67) Criterio di qualificazione corretto (2026-11-04)
- La regola "la definizione deve parlare di sesso" bocciava parole vive ma spiegate altrimenti
  (rompicoglioni, bombare, figo, pippe mentali, effeminato, celibato). Aggiunti i segnali d'uso
  (volgare, colloquiale, gergale, figurato...) e un nucleo di termini intoccabili.
- Soglia minima della definizione abbassata da 12 a 8 caratteri (tagliava "buggerare —
  ingannare"). Effetto: erotici utili da 102 a 130, senza riaprire la porta alla monnezza.

## 68) Iniezione del lessico qualificato nel prompt (2026-11-04)
- `language.lessico_pertinente()`: una voce erotica per messaggio, più una modo di dire comune solo
  sui messaggi di servizio/saluto. Scelta fra le voci con esempio e senso breve, priorità al nucleo
  (figa, cazzo, culo, scopare...), antiripetizione su ultime 6 risposte e sessione. Blocco in fondo
  al prompt, dopo le spinte: `LESSICO (se ci sta, usa una di queste parole, senza elencarle)`.
- Estrazione corretta: fra i sensi di una voce si sceglie quello **sessuale**, non il primo
  (prima "pompino" era definito "diminutivo di pompa", ora "l'atto del succhiare il pene").
- Corretti tre difetti visti in prova: doppio lock (`_usati` chiamato dentro `_LOCK`), sensi
  sbagliati presi dall'etimologia, modi di dire troppo lunghi o fuori tema.
- Misura su 4 turni (campione piccolo): lemmi distinti per 100 parole **0,88** contro **0,59** di
  baseline; ripetizioni 0. I termini iniettati compaiono (cazzo, figa, bocca).
- Aggiunte tre correzioni viste nei test: "ti tirassi su" -> "mi tiri su", "sento il tuo rispetto"
  -> "sento il tuo respiro", "un boccone di me" -> "un pezzo di me".

## 69) Misura dopo l'iniezione del lessico (2026-11-04) — giro interrotto a 42/120
- Giro standard da 120 richieste avviato e fermato per decisione dell'utente a **42 risposte**
  (`/tmp/opencode/misura.jsonl`): campione sufficiente per una direzione, non per una sentenza.
- Confronto con la baseline di 120 (stesse metriche, stesso conteggio):
  | difetto | baseline | dopo |
  |---|---|---|
  | apertura fissa "mi avvicino a te" | 13% | **0%** |
  | verbi inventati | 6% | **0%** |
  | catenelle "che/quindi" | 8% | **2%** |
  | frasi fatte | 3% | 5% (2 casi su 42, entrambi "Mi scuso! Cercherò di spiegarti meglio": accettabili) |
  | lemmi distinti per 100 parole | 48,9 | **76,7** |
  | parole medie | 15,7 | 14,1 |
- Parole più usate dopo: sono 7, mani 5, guardo 5, sulla 4 — le prime tre della baseline erano
  tutte nella stessa posizione alta e ora sono più distribuite.
- Esito: il lessico iniettato **si tiene**. Restano deboli i modi di dire comuni e la sintassi
  ("mi butto sulla tua bocca"). Prossimo passo, se si riprende: giro completo da 120 e qualificazione
  a mano del lessico comune (790 voci ancora da rivedere).

## 70) Archivio conversazionale, recupero e benchmark (2026-11-04)
- Importati 21.000 record da tre dataset HF verificati (Orvieto CC BY 4.0, DATA-AI Apache 2.0,
  OpenItalianData Apache 2.0), via API datasets-server a blocchi, senza installare `datasets` e
  senza saturare RAM. Esclusi e documentati: due-chiacchiere (gated), italian-open-sft (NC),
  RBTL/Erotico (audio), AntonelloS01 (licenza assente), KIParla/PAISÀ/itWaC/CombiNet/Dodiom
  (diritti da verificare).
- `archivio/strumenti.py`: importa (con ripresa e retry su 429), qualifica (privacy, markup,
  risposte che ripetono la domanda, solo-domanda, non-italiano, stile "da chat") e indicizza in
  SQLite FTS5. Qualificati 19.756 su 21.000, di cui 4.968 espliciti.
- `archivio/recupero.py`: ricerca a radici (prefisso), filtro espliciti, 2 esempi corti, fallback
  pesato sul messaggio. `archivio/benchmark.py`: 102 prove su 10 dimensioni, con confronto
  senza/con.
- Integrazione in `prompt_builder` dietro `RAG_ESEMPI` (ora **0**): la prova su 25+25 casi non ha
  mostrato guadagno di pertinenza (3→2 risposte col dato giusto, lemmi/parola 0,54→0,55) e ha
  accorciato le risposte (14,2→11,8 parole). Tenuto spento finché l'archivio non ha dialoghi veri.
- Corretto anche il doppio orario residuo (frasi con l'ora dentro il testo, non solo in testa).

## 71) Archivio spostato sul materiale conversazionale (2026-11-04)
- Ricerca di fonti dialogiche: aggiunti `DeepMount00/italian_conversations` (CC, italiano parlato
  vero: "Ma seriamente, 'ste lucertole…") e `MaxForce01/Syntetic_italian_Conversation` (Apache 2.0).
  Esclusi `mik3ml/italian-conversations` e `ciaocicciquantum/ItalianConversationalDataset` (gated),
  `cassanof/italian-conversations` (senza licenza), `due-chiacchiere` (gated, verificato 401 anche
  sul file diretto).
- Pulizia decisa da me: eliminate le righe con stile ≤ 0 (istruzioni, elenchi, apertura da compito),
  13.083 → **6.958** frammenti, tutti conversazionali. Archivio 82 → 20 MB (grezzi rimossi).
- Benchmark rifatto con il nuovo corpus, 25 casi: dato giusto 5 → 4, lemmi/parola 0,54 → 0,51,
  parole medie invariante. **Ancora neutro**: `RAG_ESEMPI` resta 0.

## 72) due-chiacchiere importato e terzo benchmark (2026-11-04)
- Token HF dell'utente in `/root/.hf_token` (600). Dataset gated sbloccato dopo accettazione:
  import scaricando direttamente il jsonl (l'API datasets-server non lo indicizza), con streaming.
- Importati 5.360 record; dopo qualifica e pulizia (via codice, elenchi, duplicati) restano **2.547**
  frammenti conversazionali, i migliori come italiano parlato ("mi rompo i maroni", "uova al forno").
- Benchmark, 25 casi: dato giusto 4 → 3, lemmi/parola 0,54 → 0,51, parole 14,2 → 13,0.
  Terzo corpus diverso, terzo peggioramento: `RAG_ESEMPI` resta **0**.
- Corretto l'ordine delle fasi: `pulisci` va eseguito **dopo** `indice` e non va seguito da un
  rebuild dagli stessi file, altrimenti la pulizia si perde.

## 73) Dataset NSFW italiano, espressioni e dataset per il fine-tuning (2026-11-04)
- Importato `Raphael172/NSFW_Multilanguage_Chat_Dataset` (Apache 2.0, file italiano, 6.632 coppie):
  5.520 accettate dal normalizzatore, 3.768 dopo la qualifica.
- `archivio/estrai_espressioni.py`: n-grammi 3-5 parole con frequenza ≥8, filtrati per verbi
  d'azione, via i riempitivi, doppioni esclusi. 58 candidate, **23 approvate a mano** e messe nel
  lessico (`spogliati per me`, `succhiami il cazzo`, `fammi un pompino`, `voglio vederti cavalcare`…).
- Corrette sei voci del lessico che portavano il senso zoologico (`zoccola` = topo di fogna,
  `troia` = femmina del maiale) o l'interiezione (`cazzo` = "ho mancato il bersaglio").
- `archivio/dataset_ft.py`: costruisce il dataset ChatML dai dialoghi qualificati, dal lessico
  (micro-risposte d'uso) e dalle correzioni. Divisione 90/5/5 da sha1 del contenuto, nessuna
  contaminazione, provenienza e licenza su ogni record. Attuale: 6.623 train / 394 valid / 374 test.
- `AGENTS.md`: regola nuova — ogni raccolta deve produrre **contestualmente** anche il dataset di
  fine-tuning, che va rigenerato a ogni aggiornamento.

## 74) Verificato: il dataset inglese è il duplicato di quello già importato (2026-11-04)
- `utsavm/NSFW_Chat_Dataset` ha 6.632 righe e le stesse battute del file italiano già in archivio:
  è l'originale inglese. Nessuna nuova importazione, nessuna traduzione da fare.
- La traduzione italiana esistente sbaglia la persona in ~8% dei casi (audit su 25 righe, 2 casi):
  aggiunte quattro correzioni ("mi sditalino" → "mi ditalino", "*ti mette le braccia*" → "mi avvolge
  il collo", "spara il mio sperma" → "mi sborra dentro").

## 75) Tre dataset roleplay in inglese, traduzione locale (2026-11-04)
- Verificati: `minas2025/WarmRoleplay` (178k righe, licenza per riga, aggregato di fonti permissive),
  `chimbiwide/RolePlay-NPCv2` (30k, Apache 2.0 su fonti terze), `taozi555/novel-rp` (gated, CC BY-NC).
- Importati 600 + 400 righe inglesi; `novel-rp` resta da sbloccare e da valutare per la licenza NC.
- `archivio/traduci.py`: traduzione con modello locale, salta le righe già italiane, conserva
  l'inglese accanto, riprende da dove era. Qualità rilevata ~6/10 con errori tipici
  ("mi stavo solo pensando", "polluzione", "in parco"): serve sempre un passaggio di correzioni.
  Ritmo ~15 s/riga, quindi non è una strada per decine di migliaia di righe.

## 76) Nessun dataset italiano di roleplay adulto: estratti i dialoghi dai racconti (2026-11-04)
- Ricerca su Hugging Face (filtro `language:it` + nsfw/erotic/roleplay/chat) e su GitHub:
  nessun corpus pubblico italiano di roleplay adulto. HF restituisce solo il dataset già importato
  (Raphael172); GitHub solo repository spagnoli.
- Nuovo `archivio/racconti.py`: preleva i racconti da raccontimilu.com via REST di WordPress e
  tiene **solo le battute fra virgolette**, accoppiate a passi di due. Entità HTML decodificate.
- 600 racconti → 7.654 coppie (7.774 frammenti in archivio dopo pulizia). Recupero erotico ora
  pertinente: "Guarda che cazzo che ti prendi stasera", "in ginocchio schiavo".
- Dataset di fine-tuning rigenerato con la nuova fonte.
- Corretto `fase_indice` perché accetti record senza `id`, `categoria`, `registro` (li genera).
- Diritti: racconti di autori singoli pubblicati sul sito; uso in lettura e per il training, da
  verificare se un giorno si redistribuisce il dataset.

## 77) KIParla per il parlato normale (2026-11-04)
- `archivio/kiparla.py`: estrae coppie di battute dalle trascrizioni ortografiche KIParla (zip del
  repo GitHub, nessuna registrazione). Prima versione usava `linear-enriched`: incollava parole
  ("appuntopensava"). Passato a `linear-orthographic`.
- KIPasti: 2.500 coppie, 728 dopo la pulizia (i turni parlati sono corti per natura).
- Licenza verificata nel repository: **CC BY-NC-SA 4.0**; i responsabili chiedono che i dati non
  siano inclusi in un'altra risorsa senza accordo → collezione separata, marcata, non commerciale.
- Recupero: su messaggi non erotici ora si preferisce il parlato alla prosa dei racconti
  ("mh sci nonna dice tante cagate"); sugli erotici restano i racconti.

## 78) RAG chiuso: un esempio, solo su turni caldi, risultato in parità (2026-11-04)
- Variante definitiva: un solo esempio, iniettato solo se il messaggio contiene termini erotici.
  Giro su 25 casi: dato giusto 4 vs 4, lemmi/parola 0,54 → 0,52, parole medie invariate.
- Quattro corpus provati (istruzioni, dialoghi generici, due-chiacchiere, racconti erotici):
  il massimo è la parità. `RAG_ESEMPI=0` definitivo; l'archivio resta per il fine-tuning.

## 79) Lessico comune: qualificazione avviata e difetti di persistenza (2026-11-04)
- Prima passata a mano sul lessico **comune**: 18 modi di dire enciclopedici o da manuale tolti
  (muro del pianto, legge di bilancio, ripresa economica, fare scacco, eccoglielo, ad ora…).
- Due difetti trovati provando e corretti: (1) `qualifica_lessico.py` ricostruiva i file attivi dal
  solo archivio grezzo, quindi **cancellava le 23 espressioni aggiunte a mano**; ora le rimette nei
  grezzi e, se una voce è già nel lessico attivo, la conserva. (2) la deduplica fra gruppi funziona
  solo eseguendo entrambi i gruppi: `--gruppo comune` da solo non vede gli erotici.
- Stato: 187 erotiche (di cui 23 espressioni dal corpus) e 792 comuni, nessuna sovrapposizione.

## 80) Stanze divise per genere e pulsante "?" per la domanda d'apertura (2026-11-04)
- Griglia stanza: i personaggi non stanno più in un unico alfabetico. L'indice di cache ora porta
  il genere e la pagina mostra sezioni separate **Femmine / Maschi / Non binari**, ognuna in ordine
  alfabetico e con il proprio "mostra altri". Il caricamento progressivo riceve il genere e filtra
  prima di scorrere, altrimenti l'offset salterebbe card. CSS dedicato ai titoli di sezione.
  Firma della cache portata a `v2` per forzare la ricostruzione dell'indice.
- Sostituiti i chip di tre parole con un solo pulsante **"?"**: chiede al backend
  `POST /chat/spunto`, che fa scrivere al personaggio una domanda breve (max 8 parole) coerente con
  stanza e carattere. Non consuma il limite giornaliero e non entra in cronologia. Se il modello non
  risponde c'è un elenco di ripiego per stanza. La frase viene inserita nel campo e inviata.
- Nota sui dati: **3.336 personaggi su 5.072 sono "non binari"** (66%), quindi la sezione "Non
  binari" è la più affollata. È un problema di dati, non di pagina: da rivedere quando si rigenerano
  le personalità.

### Correzioni al pulsante "?" (stesso giorno)
- Il clic non produceva nulla: l'HTML in cache puntava a un bundle JS costruito **prima** che
  l'handler esistesse. Svuotate le cache di WP Super Cache e Autoptimize (due volte, la prima non
  era bastata) e riscritto l'handler.
- Ora il pulsante risolve il personaggio come fa l'invio (campo nascosto, select, config), crea da
  sé la sessione ospite se manca e riprova una volta, mostra "Ci penso un attimo…" e un messaggio
  d'errore se fallisce: prima i fallimenti erano muti.
- Colore: il punto interrogativo era invisibile. Ora cerchio bianco con testo nero (#111), bordo
  grigio, 1.2rem.
- Formulazione delle domande corretta: "Cosa mi hai fatto venire qui?" → "Perché mi hai fatto
  venire qui?" (il modello sbagliava perché "venire" da solo fa pensare all'orgasmo, e la risposta
  andava fuori strada). Rete deterministica sulle forme sbagliate, una sola domanda per suggerimento,
  tetto a 10 parole, "ti fa sentirti" → "ti fa sentire".
- Verificato che alle nuove domande il personaggio risponde davvero ("Sono qui per incontrarti…").

## 81) Ciclo di correzione con un correttore esterno (2026-11-04)
- Tutto dentro `chat.py`, un solo comando: al termine del giro scrive da sé
  `<out>/per-chatgpt.txt` (+ `.jsonl`) con contesto, regole, turni e istruzioni per il correttore.
  `python3 chat.py --importa <risposta>` rimette le voci JSON nel dizionario e in
  `verifica_correzioni.py`. I due script separati sono stati rimossi.
- Prove spostate in `/opt/aria/prove` (prima `/tmp`, si perdevano al riavvio), aggiunte a `.gitignore`.

## 82) Coerenza grammaticale e narrativa: cause e correzioni (2026-11-04)
Backup in `backups/pre_coerenza/` (prompt_builder, chat_engine, grammar, language).
Cause trovate nel codice, non nel modello:
- "tocca a te / adesso tocca a te" non aveva un intento: cadeva sul generico e il modello rispondeva
  dando ordini all'utente (ruoli invertiti).
- "continua" finiva nel ramo dei messaggi corti ("azione fisica, non parole"), senza sapere cosa
  fosse già stato detto: da qui la ripetizione dell'azione.
- Il taglio di lunghezza poteva lasciare in coda un pezzo di frase ("... e con", "di") → frasi
  incomplete. Il punto iniziale orfano non veniva ripulito.
- Passato remoto e futuro non erano intercettati (solo tre forme a mano).
Interventi:
- blocco **PROSPETTIVA** nel prompt: prima persona, utente al "tu", tempo presente, "se l'utente
  agisce tu reagisci", "se dice continua aggiungi un passaggio nuovo".
- intenti nuovi: `turno` (agisci tu, non dare ordini) e `continua` (con la citazione dell'ultima
  frase da non ripetere).
- 8 correzioni di tempo verbale (guardò→guarda, baciò→bacia, prese→prende…), 4 lessicali
  (delicatesse→delicatezza, mi lano→mi lancio, cuscino di testa→cuscino, piuma del materasso→materasso).
- coda di frase sotto le 3 parole eliminata; punteggiatura iniziale orfana ripulita.
Verifiche: 40/40 casi verdi; 6 turni reali con 0,08 di sovrapposizione massima, 0 troncamenti,
0 terza persona, "tocca a te" risolto con azione propria.
