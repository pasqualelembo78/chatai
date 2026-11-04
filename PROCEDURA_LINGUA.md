# Procedura di aggiornamento della lingua

Vale per **qualsiasi modello**, non solo per quello attuale. Quando l'utente chiede un
"aggiornamento del modello" (o "del vocabolario", o "della lingua"), si intende questa sequenza e
non un `ollama pull` a caso.

Vincolo di fondo: **niente fine-tuning** (lento, serve macchina dedicata). L'apprendimento è
in-contesto: si allarga il materiale che il modello legge a ogni messaggio e si misura l'effetto.

## 0. Regole generali
- **Niente inventato**: termini, esempi e modi di dire vengono da fonti scaricate. Se una cosa non
  ha fonte, non entra (le correzioni grammaticali sono l'eccezione: nascono dagli errori osservati).
- **Fonti e licenze sempre annotate** in `fonti.md` (URL, licenza, data, quanti lemmi). Le fonti
  CC BY-SA richiedono attribuzione; quelle CC BY-NC-ND si usano come elenco di parole e il testo si
  riscrive.
- **Backup prima di toccare**: `backend/language/` e gli script di raccolta vanno salvati in
  `backups/` e messi nello zip insieme alle modifiche.
- Ogni passo deve essere ripetibile: script, non comandi a mano.

## 1. Raccolta
Due archivi separati, mai mescolati:
- `lessico-grezzo.json` — erotico/pornografico: volgarità, atti, parti del corpo, parafilie.
- `lessico-grezzo-comune.json` — italiano normale: modi di dire, espressioni, interiezioni.

Fonti ammesse: dizionari e categorie di it.wiktionary (via API), glossari pubblici, raccolte di modi
di dire, testi erotici di pubblico dominio per gli esempi d'uso. Script: `estrai_lessico.py`
(`--gruppo erotico|comune`).

## 2. Qualificazione
`qualifica_lessico.py`. Ogni voce viene marcata:
- **utile** — entra nel lessico attivo
- **scarto** — via, con motivo (letterale, doppione, fuori tema, senso sbagliato, troppo generica)

Criteri: la definizione deve riguardare l'uso in chat; si scartano le locuzioni letterali
("prendere il mare" di un natante), i doppioni, i sensi estranei (araldica, edilizia), le voci senza
definizione. La revisione umana ha l'ultima parola sulle voci dubbie: `da_rivedere.txt`.

Le voci utili passano in `backend/language/lessico/<categoria>.json` con: termine, registro, senso
breve, eventuale esempio **preso dalla fonte**.

## 3. Iniezione
Nel prompt, al massimo 2-3 voci per categoria pertinente al messaggio, con antiripetizione sulle
ultime risposte (la memoria esiste già in `language._usati`). Mai elenchi: solo la voce e, se c'è,
l'esempio. Il blocco resta sotto ~250 caratteri.

## 4. Misura
Prima di dichiarare migliorato qualcosa, quattro numeri da `chat.py` e `registra`:
- lemmi distinti per 100 parole (deve salire)
- ripetizioni a 3 turni (deve scendere)
- errori per 100 risposte, dal report automatico e da `verifica_correzioni.py`
- copertura: percentuale di risposte con almeno un termine della categoria

Confronto sempre contro una misura precedente registrata. Se i numeri non si muovono, la modifica
si toglie: si tiene solo ciò che sposta qualcosa.

## 5. Correzione linguistica
Le forme sbagliate prodotte dal modello si aggiungono a `backend/language/italian-grammar.json` e
**prima** a `verifica_correzioni.py` (il caso deve fallire, poi si corregge, poi torna verde).

## 6. Chiusura
`bash -n` sugli script toccati, `verifica_correzioni.py` verde, `probe_qualita.py` o `chat.py` con i
numeri, zip aggiornato, `REPRODUCIBILITY.md` con la voce del giorno, commit e push.

## Errori da non ripetere
- aggiungere termini senza fonte o senza senso verificato
- iniettare 5-6 voci per messaggio: allunga il prompt e confonde il 3B
- mescolare erotico e comune nello stesso archivio
- dichiarare "migliorato" senza il confronto numerico
