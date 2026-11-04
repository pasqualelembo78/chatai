# Archivio conversazionale

Raccolta di esempi italiani per il recupero in chat. **Non modifica il modello**: i pesi GGUF
restano quelli, il recupero agisce solo sul prompt.

## Cosa c'è
| fonte | licenza | record |
|---|---|---|
| OysterCoreAI/Orvieto-42k | CC BY 4.0 | 6.875 |
| Mattimax/DATA-AI_Conversation_ITA | Apache 2.0 | 5.660 |
| DeepMount00/OpenItalianData | Apache 2.0 (da WildChat) | 7.221 |

Totale indicizzato: **19.756** frammenti, di cui **4.968** classificati espliciti (378 censiti
come "da chat", stile ≥ 2). Le espressioni stanno a parte: **164** erotiche e **790** modi di dire
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
