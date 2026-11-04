# Archivio conversazionale

Raccolta di esempi italiani per il recupero in chat. **Non modifica il modello**: i pesi GGUF
restano quelli, il recupero agisce solo sul prompt.

## Scelta delle fonti (2026-11-04)
La prima importazione era tutta istruzionale ("Genera un testo su…") e il recupero peggiorava le
risposte. Sono state cercate fonti **conversazionali** e aggiunte:
- `DeepMount00/italian_conversations` (CC) — 21.117 righe, italiano parlato, il materiale migliore
- `MaxForce01/Syntetic_italian_Conversation` (Apache 2.0) — 1.000 dialoghi sintetici su temi comuni
- scartate per ora: `mik3ml/italian-conversations` e `ciaocicciquantum/ItalianConversationalDataset`
  (gated), `cassanof/italian-conversations` (licenza assente)
Le righe istruzionali con stile basso sono state eliminate: l'archivio è ora **conversazionale**.

## Cosa c'è
| fonte | licenza | record |
|---|---|---|
| DeepMount00/italian_conversations | CC | 2.916 |
| Mattimax/DATA-AI_Conversation_ITA | Apache 2.0 | 2.089 |
| DeepMount00/OpenItalianData | Apache 2.0 (da WildChat) | 1.439 |
| MaxForce01/Syntetic_italian_Conversation | Apache 2.0 | 514 |

Totale indicizzato: **6.958** frammenti, tutti con struttura da chat (stile ≥ 1), di cui 2.793
classificati espliciti. Le espressioni stanno a parte: **164** erotiche e **790** modi di dire
in `backend/language/lessico/`, già iniettate nel prompt.

## Fonti escluse, e perché
- `DeepMount00/due-chiacchiere` — gated: serve token HF e accettazione delle condizioni; senza token
  l'API risponde 401. È la più ricca (300k), vale la pena sbloccarla a mano.
- `SerFabio89/italian-open-sft-chat-dataset` — CC BY-NC 4.0: non commerciale, tenuta fuori.
- `RBTL/Erotico` — solo audio.
- `AntonelloS01/Conversazioni` — licenza non dichiarata.
- KIParla, PAISÀ, itWaC, CombiNet, Dodiom — diritti per contenuto/corpus da verificare singolarmente.
- Wikizionario: già usato (CC BY-SA) per il lessico, non per i dialoghi.

## Come si usa
```
python3 archivio/strumenti.py importa     # riscarica (riprende da dove era)
python3 archivio/strumenti.py qualifica
python3 archivio/strumenti.py indice
python3 archivio/strumenti.py stato
python3 archivio/benchmark.py --condizione senza --quante 25
python3 archivio/benchmark.py --confronta
```

Recupero: `archivio/recupero.py`, FTS5 con radici delle parole (prefisso) e filtro sugli espliciti.
Non c'è ricerca vettoriale: nessun modello di embedding installato, e aggiungerlo costerebbe RAM.

## Interruttore
`RAG_ESEMPI=1` in `backend/.env` accende gli esempi nel prompt (2 per messaggio, solo sui turni di
servizio). **Ora è spento**: nella prova di 25 casi il recupero non ha migliorato la pertinenza
(3 → 2 risposte corrette sui dati, lemmi/parola 0,54 → 0,55) e ha accorciato le risposte
(14,2 → 11,8 parole). Il motivo è che i tre dataset sono di tipo istruzionale: gli esempi pescati
parlano di pasta e di animali invece che di una persona che chatta.

## Limiti noti
- Poca conversazione naturale: quasi tutti gli esempi sono "compito → risposta".
- Il materiale erotico è scarso e spesso didascalico (definizioni, non battute).
- La pertinenza misurata a parole chiave penalizza le risposte meno letterali: il numero va letto
  insieme al testo.

## Prossimi passi
1. sbloccare `due-chiacchiere` (300k esempi, i più conversazionali).
2. Aggiungere una sorgente di dialoghi erotici reali (racconti o chat), che oggi manca.
3. Solo dopo, riaccendere `RAG_ESEMPI` e rigirare il benchmark: se non migliora, resta spento.
