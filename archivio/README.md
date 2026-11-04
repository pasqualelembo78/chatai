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

## Dataset per il fine-tuning
`python3 archivio/dataset_ft.py` costruisce `archivio/dataset_ft/` in ChatML con divisione 90/5/5
decisa dall'impronta del contenuto (nessuna contaminazione). **Va rilanciato a ogni nuova raccolta**,
come da regola in `AGENTS.md`. Attuale: 6.623 train / 394 valid / 374 test.

## Cosa c'è
| fonte | licenza | record |
|---|---|---|
| DeepMount00/due-chiacchiere | gated, condizioni accettate | 2.588 |
| Raphael172/NSFW_Multilanguage_Chat_Dataset | Apache 2.0 | 3.768 |

Il dataset NSFW è la prima fonte erotica utile: battute adulte in italiano, Apache 2.0. Da lì sono
state estratte (con frequenza) 23 espressioni messe nel lessico, verificandole a mano; gli esempi con
asterischi e versi si sono rivelati meno adatti al prompt rispetto al lessico.

Totale indicizzato: **2.547** frammenti conversazionali, senza codice, senza elenchi, senza
risposte duplicate. Le espressioni stanno a parte: **164** erotiche e **790** modi di dire
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

## Esito dei tre benchmark (25 casi ciascuno, stesse prove)
| corpus acceso | dato giusto | lemmi/parola | parole medie |
|---|---|---|---|
| istruzionale (Orvieto/OpenItalian/WildChat) | 3 → **2** | 0,54 → 0,55 | 14,2 → 11,8 |
| conversazionale piccolo (italian_conversations) | 5 → **4** | 0,54 → 0,51 | 14,2 → 14,2 |
| due-chiacchiere | 4 → **3** | 0,54 → 0,51 | 14,2 → 13,0 |

Tre corpus diversi, tre volte peggio. **Il recupero non aiuta questo modello.** L'ipotesi più
semplice è che il 3B non riesca a usare due esempi in più senza perdere il filo di quello che sta
scrivendo: il prompt passa da ~1.500 a ~2.200 caratteri e la qualità scende.

## Prossimi passi
1. provare con 1 solo esempio invece di 2 (il prompt resta più corto).
2. Aggiungere una sorgente di dialoghi erotici reali (racconti o chat), che oggi manca.
3. Solo dopo, riaccendere `RAG_ESEMPI` e rigirare il benchmark: se non migliora, resta spento.

## Nota: NSFW_Chat_Dataset inglese è il duplicato del nostro
`utsavm/NSFW_Chat_Dataset` (Apache 2.0, 6.632 righe, in inglese) è **la versione originale** di
`Raphael172/NSFW_Multilanguage_Chat_Dataset`, di cui abbiamo già importato la traduzione italiana:
stesso numero di righe, stesse battute. Non va importato di nuovo.
La traduzione esistente è discreta ma sbaglia la persona in circa l'8% dei casi ("fa schifo mentre mi
sditalino", "*ti mette le braccia al collo*" per "wraps my arms"): si corregge con le regole, non
ritraducendo.

## Fonti inglesi e traduzione
- `minas2025/WarmRoleplay` (aggregato roleplay, licenza **per riga** nel campo `license`): importate
  600 righe, le migliori come struttura (personaggi, scene).
- `chimbiwide/RolePlay-NPCv2` (Apache 2.0, ma è una combinazione di fonti terze): importate 400.
- `taozi555/novel-rp`: gated **e** CC BY-NC 4.0, da accettare e valutare.
- Traduzione: `archivio/traduci.py` con il modello locale. Qualità ~6/10 ("mi stavo solo pensando",
  "polluzione ambientale", "in parco") e ritmo di ~15 s/riga: va sempre accompagnata da correzioni.
  Output in `*-it.jsonl` con il testo inglese accanto, così si può rifare.

## Racconti erotici italiani: dialoghi estratti
Non esiste un dataset pubblico di roleplay adulto in italiano (verificato: su Hugging Face, con
filtro `language:it` + `nsfw`, esce solo il dataset già importato; su GitHub solo roba spagnola).
La fonte migliore sono i racconti: `archivio/racconti.py` preleva dalle storie di
`raccontimilu.com` (25.851 disponibili) solo le battute fra virgolette e le accoppia.

- 600 racconti → 7.654 coppie, ridotte a **7.774 frammenti** in archivio dopo la pulizia
- italiano nativo, registro adulto, attacchi secchi: *"Guarda che cazzo che ti prendi stasera"*
- diritti: racconti pubblicati, autori singoli. Uso in lettura e per il fine-tuning; per una
  redistribuzione commerciale del dataset va chiesto il permesso.

## KIParla (parlato spontaneo) — licenza NC-SA
`archivio/kiparla.py` estrae scambi dalle trascrizioni **ortografiche** di KIParla (350 ore, 994
parlanti). Prova su KIPasti (conversazioni al bar): 2.500 coppie, 728 dopo la pulizia, perché i
turni parlati sono corti.
- registro vero, non costruito: "mh sci nonna dice tante cagate", "c'hai il matrimonio"
- **licenza CC BY-NC-SA 4.0**, consultazione senza fini di lucro, e i responsabili chiedono che i
  dati non entrino in un'altra risorsa senza accordo: va tenuta come collezione separata e marcata
- adatta al lessico e alla chat normale, rumorosa da iniettare in un 3B (troncamenti, dialetto)

## Esito finale del RAG, con un esempio e solo sui turni caldi
Quarto giro, 25 casi: dato giusto 4 = 4, lemmi/parola 0,54 → 0,52, parole medie 14,2 → 14,3.
**Parità, non miglioramento.** `RAG_ESEMPI` resta spento: a parità di resa meglio non pagare
300 caratteri di prompt. Esperimento chiuso: quattro corpus diversi (istruzioni, dialoghi
generici, due-chiacchiere, racconti erotici) e il massimo raggiunto è l'indifferenza.
