# ChatAI — Penetration Test Manual Checklist
# Fase 7.3 — Eseguire dopo deploy su staging/production

## Preparazione
- [ ] Environment: server staging o production, app Android compilata in release
- [ ] Strumenti: Burp Suite / OWASP ZAP, curl, pytest, Postman
- [ ] Account test: user_normal, user_admin, user_banned
- [ ] Endpoint base: `https://tuodominio.it` (sostituire in ogni test)

---

## A01 — Broken Access Control (IDOR)

### Conversations
- [ ] user_a tenta GET /conversations/<user_b_conversation_id> → 401/403/404
- [ ] user_a tenta DELETE /conversations/<user_b_conversation_id> → 401/403/404
- [ ] user_a tenta POST /conversations/<user_b_conversation_id>/pin → 401/403/404

### Characters
- [ ] user_a tenta GET /characters/<user_b_character_id> → 401/403/404
- [ ] user_a tenta PUT /characters/<user_b_character_id> → 401/403/404
- [ ] user_a tenta DELETE /characters/<user_b_character_id> → 401/403/404

### Premium / Evoluzione
- [ ] user_a tenta GET /evolution/<user_b_evolution_id> → 401/403/404
- [ ] user_a tenta POST /premium/activate con carta altro utente → 401/403/404

### User data
- [ ] user_a tenta GET /user/export con user_b's token → 401
- [ ] user_a tenta POST /user/delete con user_b's token → 401

### Admin endpoints
- [ ] user_normal tenta GET /admin/users → 401/403
- [ ] user_normal tenta POST /admin/ban → 401/403
- [ ] user_normal tenta POST /admin/prune → 401/403
- [ ] user_normal tenta GET /admin/logs → 401/403
- [ ] user_normal tenta GET /admin/flags → 401/403
- [ ] user_normal tenta POST /admin/flags/1/resolve → 401/403

---

## A02 — Cryptographic Failures

### JWT
- [ ] JWT con alg=none → testare header `{"alg":"none","typ":"JWT"}` + payload vuoto → 401
- [ ] JWT con alg=HS256 ma chiave pubblica come secret → 401
- [ ] JWT con payload manomesso (user_id cambiato) → 401
- [ ] JWT scaduto → 401
- [ ] Refresh token usato come access token → 401
- [ ] Access token usato dopo logout (blacklist) → 401
- [ ] Doppio refresh dello stesso token → 401 (rotation)

### Dati in transito
- [ ] Curl con --insecure su HTTPS → certificato valido
- [ ] Wireshark/tcpdump: nessuna password/JWT in chiaro (solo HTTPS)

### Dati in storage
- [ ] purchase_token nel DB leggibile? → deve essere cifrato (Fernet)
- [ ] Password nel DB leggibile? → deve essere hash scrypt

---

## A03 — Injection

### SQL Injection
- [ ] `/auth/login` con payload: `' OR '1'='1` → 401
- [ ] `/auth/login` con payload: `'; DROP TABLE users; --` → 401
- [ ] `/auth/register` con payload: `admin'--` → 400/422
- [ ] `/chat` con payload SQL nel messaggio → risposta normale (no error SQL)
- [ ] `/transcribe` filename con `../../etc/passwd` → 400

### Path Traversal
- [ ] `/../etc/passwd` → 404 (non 200 con file content)
- [ ] `/..%2F..%2Fetc/passwd` → 404
- [ ] `/static/../../../etc/passwd` → 404
- [ ] Upload con filename `../../../etc/passwd` → 400

---

## A04 — Insecure Design (Rate Limiting)

- [ ] `/auth/login`: 11 richieste in 10 secondi → ultima deve essere 429
- [ ] `/auth/register`: 6 richieste in 10 secondi → ultima deve essere 429
- [ ] `/transcribe`: 11 richieste in 10 secondi → ultima deve essere 429
- [ ] `/upload-image`: 11 richieste in 10 secondi → ultima deve essere 429
- [ ] `/chat`: 31 richieste in 60 secondi → ultima deve essere 429
- [ ] Bypass tentato via X-Forwarded-For spoofing → deve fallire

---

## A05 — Security Misconfiguration

### Security Headers (test via curl -I)
- [ ] `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY`
- [ ] `Content-Security-Policy: default-src 'self'` (con nonce per script)
- [ ] `Referrer-Policy: no-referrer` o `strict-origin-when-cross-origin`
- [ ] `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- [ ] Server header non rivela versione (Apache/2.4.41 → bastano "Apache")

### TLS (test via testssl.sh o ssllabs.com)
- [ ] TLS 1.2 e 1.3 attivi
- [ ] TLS 1.0 e 1.1 disabilitati
- [ ] Cipher suites sicure (no RC4, 3DES, EXPORT)
- [ ] Certificato non scaduto
- [ ] HSTS preload ready

---

## A06 — Vulnerable Components

- [ ] `pip-audit` su backend/ → 0 vulnerabilità note
- [ ] Versioni Python packages in requirements.txt aggiornate
- [ ] Dependabot/GitHub advisories: nessuna CVE critica
- [ ] Gradle dependencies aggiornate

---

## A07 — Identification and Authentication Failures

### Login
- [ ] Password errata → messaggio generico (non "password sbagliata" vs "utente non esiste")
- [ ] Username enumeration: tempi di risposta uguali per utente esistente e non
- [ ] Rate limiting bypass via IP rotation testato
- [ ] Refresh token rotation: refresh token usato 2 volte → entrambi invalidati

### Google Sign-In
- [ ] Token Google firmato da Google? → sì, verificato con google-auth
- [ ] Token Google riutilizzato con client ID diverso? → rifiutato
- [ ] Android: Google Sign-In su emulatore senza Google Play Services? → fallisce

### JWT Security
- [ ] JWT secret abbastanza lungo (>256 bit, random) → verificare .env
- [ ] JWT non contiene informazioni sensibili (password, API key)

---

## A08 — Software and Data Integrity Failures

### Upload
- [ ] File PHP (`shell.php`) come immagine → 400
- [ ] File HTML con JavaScript → 400
- [ ] File SVG con script onclick/onload → 400
- [ ] File APK ridenominato `.jpg` → 400 (MIME check)
- [ ] File con estensione doppia (`image.php.jpg`) → 400
- [ ] File senza estensione → salvato senza estensione (non si può eseguire)
- [ ] Zip bomb → 400 (dimensione > 10MB)
- [ ] Symlink → 400 (non supportato dal form upload)
- [ ] File con null byte (`image.php%00.jpg`) → 400
- [ ] File EXE/.bat/.cmd → 400
- [ ] File con EXIF contenente GPS coordinates → EXIF stripped

### Audio Upload
- [ ] File MP3 con header falsificato → MIME check deve rilevare
- [ ] Audio > 60 secondi → 400
- [ ] Audio sample rate < 8kHz o > 48kHz → 400
- [ ] Audio > 10MB → 400
- [ ] Audio con metadati dannosi → sanitizzato

---

## A09 — Security Logging and Monitoring Failures

### Audit Log
- [ ] Ogni login/register → riga in audit_log
- [ ] Ogni upload (transcribe, image) → riga in audit_log
- [ ] Ogni azione admin (ban, prune, resolve flag) → riga in audit_log
- [ ] Ogni registrazione utente → riga in audit_log
- [ ] POST /user/delete → riga in audit_log PRIMA della cancellazione
- [ ] Tentativo accesso a endpoint admin senza ruolo → riga in audit_log

### Alert Telegram
- [ ] File infetto → messaggio Telegram
- [ ] NSFW detection → messaggio Telegram
- [ ] Telegram configurato in .env? (opzionale)

---

## A10 — Server-Side Request Forgery (SSRF)

- [ ] /chat con URL in messaggio → deve essere gestito via API provider, non server
- [ ] /transcribe con URL remoto → non implementato (solo multipart upload)
- [ ] /upload-image con URL remoto → non implementato (solo multipart upload)

---

## Android-Specific

### Root Detection
- [ ] Device rooted → dialog bloccante → app termina
- [ ] Root detection bypass tramite Frida → testare
- [ ] Root detection bypass tramite Magisk Hide → testare

### Token Extraction
- [ ] Backup Android (adb backup) → token non estraibile (EncryptedSharedPreferences)
- [ ] Debug su device non rooted → token non estraibile
- [ ] Device rooted → token in /data/data/... encrypted → non leggibile

### Network Security Config
- [ ] HTTPS su dominio reale → connessione OK
- [ ] HTTP su dominio reale → connessione BLOCCATA
- [ ] HTTP su 10.0.2.2 (development) → connessione OK (cleartext exception)
- [ ] Proxy impostato (Burp) → richiede installazione CA su device

---

## GDPR Compliance Check

- [ ] GET /privacy → ritorna policy aggiornata con 8 punti
- [ ] GET /user/export → JSON con TUTTI i dati utente
- [ ] POST /user/delete → utente cancellato da TUTTE le tabelle
- [ ] Dopo delete: tentare login con stesse credenziali → 401
- [ ] Dopo delete: re-registrare stesso username → OK (nuovo utente)
- [ ] Privacy policy: prima di registrazione → dialog su Android, endpoint GET

---

## Report

- [ ] Tutti i test passati? (__/__)
- [ ] Vulnerabilità critiche trovate: __
- [ ] Vulnerabilità medie trovate: __
- [ ] Vulnerabilità basse trovate: __
- [ ] Raccomandazioni: ________________________________
- [ ] Data test: _______________
- [ ] Tester: __________________
