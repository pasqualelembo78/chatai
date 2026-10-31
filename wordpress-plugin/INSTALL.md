# Aria Chat AI - Istruzioni di Installazione

## Plugin WordPress creato con successo!

Il plugin è pronto in: `/opt/aria/wordpress-plugin/aria-chat/`

## Test API completati

✅ Health Check: OK  
✅ Categorie: 27 categorie, 1000+ personaggi  
✅ Provider AI: 20 provider (Ollama, Groq, Gemini, etc.)  
✅ Modelli: 72 modelli totali nella chain  
✅ Login/Register: OK  
✅ Chat: OK (risposta da Ollama stheno-abliterated:8b)

## Installazione su WordPress

### Metodo 1: Upload manuale (ZIP)

```bash
cd /opt/aria/wordpress-plugin
zip -r aria-chat.zip aria-chat/
```

1. Vai su WordPress Admin → Plugin → Aggiungi nuovo
2. Carica `aria-chat.zip`
3. Attiva il plugin

### Metodo 2: Upload FTP/SFTP

```bash
# Copia il plugin nella directory WordPress
cp -r /opt/aria/wordpress-plugin/aria-chat /var/www/html/wp-content/plugins/
```

Poi attiva da WordPress Admin.

## Configurazione

1. Vai su **Impostazioni → Aria Chat**
2. Imposta URL Backend: `http://82.165.218.56:5000`
3. Salva

## Utilizzo

### In una pagina/post WordPress

```
[aria_chat]
```

Opzioni:
```
[aria_chat character="marco_amicizia"]           // Personaggio pre-selezionato
[aria_chat width="100%" height="600px"]          // Dimensioni custom
[aria_chat character="elena_ginecologa" width="800px"]
```

### Per gli utenti

1. Cliccare "Login" nel chat box
2. Inserire username/password ARIA (creati sul backend)
3. Selezionare personaggio dal dropdown
4. Inviare messaggi!

## CORS (se necessario)

Se WordPress è su dominio diverso dal backend, aggiorna `.env` del backend:

```bash
# /opt/aria/backend/.env
CORS_ALLOWED_ORIGINS=https://tuosito.it,https://www.mevacoin.com,https://mail.mevacoin.com
```

Poi riavvia il backend:
```bash
sudo systemctl restart chatai
```

## Personaggi disponibili (esempi)

- `marco_amicizia` - Marco (migliore amico)
- `anna_amicizia` - Anna (ragazza solare)
- `confidente` - Alice (confidente empatica)
- `lorenzo_amicizia` - Lorenzo (amico spiritoso)
- `emma_amicizia` - Emma (conversatrice)

Per vedere tutti i personaggi: `GET http://82.165.218.56:5000/characters`

## Struttura del plugin

```
aria-chat/
├── aria-chat.php          # Entry point (shortcode, admin menu)
├── includes/
│   ├── API_Client.php     # HTTP client per backend ARIA
│   ├── Auth_Manager.php   # JWT token management
│   └── Chat_Engine.php    # AJAX handlers
├── assets/
│   ├── css/aria-chat.css  # Stile responsive
│   └── js/aria-chat.js    # Frontend (jQuery)
├── templates/
│   └── chat-box.php       # UI chat box
└── README.md
```

## Test API standalone

```bash
php /opt/aria/wordpress-plugin/test_api.php
```

## Troubleshooting

### "Token mancante"
- Verifica che l'URL backend sia corretto in Impostazioni
- Controlla CORS_ALLOWED_ORIGINS in .env

### "Character not found"
- Usa ID corretti (es. `marco_amicizia` non `marco_migliore_amico`)
- Lista personaggi: `/characters` endpoint

### Chat lenta
- Il backend usa Ollama locale (5-15 secondi per risposta)
- Puoi cambiare provider in Impostazioni utente (backend)

### Errore connessione
- Verifica che il backend sia attivo: `systemctl status chatai`
- Test: `curl http://82.165.218.56:5000/`

## Prossimi step (opzionali)

1. **Streaming**: Aggiungere SSE al backend per risposte in tempo reale
2. **Integrazione WP Users**: Mappare utenti WordPress → utenti ARIA automaticamente
3. **Persistenza**: Salvare conversazioni in `wp_postmeta`
4. **Media**: Upload immagini (`/upload-image`), voice-to-text (`/transcribe`)
5. **Premium**: Sistema MevaCoins integrato

## License

GPL v2 or later
