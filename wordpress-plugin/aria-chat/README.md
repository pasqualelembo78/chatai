# Aria Chat AI - Plugin WordPress

Chat AI con personaggi virtuali per WordPress. Si collega al backend ARIA per conversazioni intelligenti.

## Installazione

1. Copiare la cartella `aria-chat` in `/wp-content/plugins/`
2. Attivare dal pannello di amministrazione WordPress
3. Configurare l'URL del backend in **Impostazioni → Aria Chat**
4. Usare il shortcode `[aria_chat]` in qualsiasi pagina o post

## Shortcode

```
[aria_chat]                    // Chat box di base
[aria_chat character="elena"]  // Chat con personaggio pre-selezionato
[aria_chat width="100%" height="600px"]  // Dimensioni personalizzate
```

## Configurazione Backend

Nel pannello di amministrazione WordPress:
- **Impostazioni → Aria Chat**
- URL Backend ARIA: `http://82.165.218.56:5000` (o il tuo server)

## API Endpoints Utilizzati

- `GET /` - Health check
- `GET /characters` - Lista personaggi
- `GET /categories` - Categorie personaggi
- `POST /auth/login` - Login utente
- `POST /auth/logout` - Logout
- `POST /chat` - Invia messaggio e ricevi risposta AI

## Autenticazione

Il plugin supporta due modalità:
1. **Login ARIA**: Utenti registrati sul backend ARIA (username/password)
2. **Anonimo**: Chat senza login (user_id generato automaticamente dal backend)

## Struttura File

```
aria-chat/
├── aria-chat.php          # Entry point plugin
├── includes/
│   ├── API_Client.php     # HTTP client per backend
│   ├── Auth_Manager.php   # Gestione JWT
│   └── Chat_Engine.php    # AJAX handlers
├── assets/
│   ├── css/aria-chat.css  # Stile chat box
│   └── js/aria-chat.js    # Logica frontend
├── templates/
│   └── chat-box.php       # Template shortcode
└── README.md
```

## Requisiti

- WordPress 5.0+
- PHP 7.4+
- Backend ARIA in esecuzione (port 5000)
- Connessione internet per API calls

## Sviluppo

### Debug mode
Aggiungi nel file `aria-chat.php`:
```php
error_log('Aria Chat: ' . $message);
```

### CORS
Se il backend è su dominio diverso, aggiungi l'URL WordPress a `CORS_ALLOWED_ORIGINS` nel `.env` del backend:
```
CORS_ALLOWED_ORIGINS=https://tuosito.it,https://www.mevacoin.com
```

## License

GPL v2 or later
