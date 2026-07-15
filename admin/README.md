# AI Roleplay Immersive Adventure

Chatta con personaggi virtuali realistici dotati di personalità, memoria e capacità di evoluzione. Supporta molteplici provider AI: locali (Ollama) e cloud (OpenAI, Anthropic, Google Gemini, Groq, OpenRouter).

## Caratteristiche

- **4 personaggi** con personalità distinte: Elena (ginecologa), Marco (insegnante matematica), Prof. Rossi (italiano), Luna (istruttrice nuoto)
- **Personaggi non-robot**: parlano in modo naturale, danno risposte organicamente contestuali, non usano frasi fatte
- **Evoluzione della personalità**: i personaggi cambiano gradualmente in base alle interazioni, sotto pressione narrativa possono fare concessioni credibili
- **Memoria a lungo termine**: ricordano conversazioni passate e le riassumono per mantenere coerenza
- **Sistema di intimità**: le relazioni si sviluppano gradualmente, contenuti intimi sbloccabili solo con confidenza alta
- **Multi-provider AI**: scegli tra Ollama (locale gratuito), OpenAI, Anthropic, Google Gemini, Groq, OpenRouter
- **App Android nativa**: interfaccia pulita, selezione personaggio/providers/modello all'avvio

## Requisiti

- Python 3.10+
- Android SDK (per build APK)
- 4-8 GB RAM (per modelli locali)
- Opzionale: GPU NVIDIA per modelli locali più grandi

## Installazione Rapida

```bash
# Build completo (backend + modelli + APK)
./build_app.sh

# Solo backend e modelli (senza APK)
./build_app.sh --skip-apk

# Solo backend Python (saltando Ollama e APK)
./build_app.sh --skip-ollama --skip-apk

# Con modelli specifici
./build_app.sh --models "llama3.1:8b mistral:7b qwen2.5:7b"
```

## Avvio Manuale

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Il server parte su `http://0.0.0.0:5000`.

## Provider AI Supportati

| Provider | Tipo | API Key | Costo |
|----------|------|---------|-------|
| Ollama | Locale | No | Gratuito |
| OpenAI | Cloud | Sì | A pagamento |
| Anthropic | Cloud | Sì | A pagamento |
| Google Gemini | Cloud | Sì | Free tier + a pagamento |
| Groq | Cloud | Sì (gratuita) | Gratuito |
| OpenRouter | Cloud | Sì | A pagamento (gateway) |

### Configurazione API Key

Crea `backend/.env` (usa `backend/.env.example` come template):

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
```

Oppure usa `./build_app.sh` che guida nella configurazione interattiva.

## Endpoints API

### REST

- `GET /` - Stato del server
- `GET /characters` - Lista personaggi disponibili
- `GET /providers` - Lista provider AI con modelli e stato
- `GET /config` - Configurazione attuale (provider + modello)
- `POST /config` - Imposta provider/modello
- `POST /chat` - Invia messaggio (formato JSON)

### WebSocket (Socket.IO)

- `add user` - Login con nickname, personaggio, provider, modello
- `new message` - Invia messaggio e riceve risposta AI
- `typing` / `stop typing` - Indicatori di digitazione

## Struttura del Progetto

```
backend/
├── ai_engine.py       # Provider AI (Ollama, OpenAI, Anthropic, Gemini, Groq, OpenRouter)
├── characters.py      # Definizioni personaggi con essenza, personalità, evoluzione
├── emotion_engine.py  # Rilevamento emozioni, pressione, intimità
├── prompt_builder.py  # Costruzione prompt di sistema
├── server.py          # Server Flask-SocketIO
├── storage.py         # Database SQLite (memoria, relazioni, personalità)
├── requirements.txt   # Dipendenze Python
└── .env.example       # Template configurazione API key

app/                   # App Android nativa
├── src/main/java/.../LoginActivity.java   # Login + selezione provider/modello/personaggio
├── src/main/java/.../MainFragment.java    # Chat principale
└── src/main/res/       # Layout e risorse Android

build_app.sh           # Script build unificato
```

## Personaggi

| ID | Nome | Ruolo | Stile |
|----|------|-------|-------|
| ginecologa | Elena | Ginecologa | Professionale, empatica, riservata |
| insegnante_matematica | Marco | Insegnante | Logico, paziente, ironico |
| prof_italiano | Prof. Rossi | Ex-professore | Colto, bonario, nostalgico |
| insegnante_nuoto | Luna | Istruttrice | Energica, allegra, diretta |

## Licenza

MIT
