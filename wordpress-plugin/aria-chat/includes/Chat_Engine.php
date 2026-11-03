<?php
/**
 * Chat Engine - Orchestrazione chat e AJAX handlers
 */

if (!defined('ABSPATH')) exit;

class Aria_Chat_Engine {
    
    private $auth_manager;
    private $api_client;
    
    public function __construct() {
        $this->auth_manager = new Aria_Auth_Manager();
        $this->api_client = $this->auth_manager->get_api_client();
    }
    
    public function init_ajax() {
        add_action('wp_ajax_aria_chat_login', array($this, 'ajax_login'));
        add_action('wp_ajax_nopriv_aria_chat_login', array($this, 'ajax_login'));
        add_action('wp_ajax_aria_chat_register', array($this, 'ajax_register'));
        add_action('wp_ajax_nopriv_aria_chat_register', array($this, 'ajax_register'));
        add_action('wp_ajax_aria_chat_logout', array($this, 'ajax_logout'));
        add_action('wp_ajax_nopriv_aria_chat_logout', array($this, 'ajax_logout'));
        add_action('wp_ajax_aria_chat_send', array($this, 'ajax_send_message'));
        add_action('wp_ajax_aria_chat_stream', array($this, 'ajax_send_stream'));
        add_action('wp_ajax_aria_chat_opening', array($this, 'ajax_chat_opening'));
        add_action('wp_ajax_aria_chat_regenerate', array($this, 'ajax_regenerate'));
        add_action('wp_ajax_aria_chat_export', array($this, 'ajax_export'));
        add_action('wp_ajax_nopriv_aria_chat_guest', array($this, 'ajax_chat_guest'));
        add_action('wp_ajax_nopriv_aria_chat_grid_more', array($this, 'ajax_grid_more'));
        add_action('wp_ajax_aria_chat_grid_more', array($this, 'ajax_grid_more'));
        add_action('wp_ajax_aria_chat_guest', array($this, 'ajax_chat_guest'));
        add_action('wp_ajax_nopriv_aria_chat_send', array($this, 'ajax_send_message'));
        add_action('wp_ajax_nopriv_aria_chat_stream', array($this, 'ajax_send_stream'));
        add_action('wp_ajax_nopriv_aria_chat_regenerate', array($this, 'ajax_regenerate'));
        add_action('wp_ajax_nopriv_aria_chat_send', array($this, 'ajax_send_message'));
        add_action('wp_ajax_aria_chat_characters', array($this, 'ajax_get_characters'));
        add_action('wp_ajax_nopriv_aria_chat_characters', array($this, 'ajax_get_characters'));
        add_action('wp_ajax_aria_chat_categories', array($this, 'ajax_get_categories'));
        add_action('wp_ajax_nopriv_aria_chat_categories', array($this, 'ajax_get_categories'));
        add_action('wp_ajax_aria_chat_auth_status', array($this, 'ajax_auth_status'));
        add_action('wp_ajax_nopriv_aria_chat_auth_status', array($this, 'ajax_auth_status'));
        add_action('wp_ajax_aria_chat_get_config', array($this, 'ajax_get_config'));
        add_action('wp_ajax_nopriv_aria_chat_get_config', array($this, 'ajax_get_config'));
        add_action('wp_ajax_aria_chat_set_config', array($this, 'ajax_set_config'));
        add_action('wp_ajax_aria_chat_refresh_token', array($this, 'ajax_refresh_token'));
        add_action('wp_ajax_nopriv_aria_chat_refresh_token', array($this, 'ajax_refresh_token'));
        add_action('wp_ajax_aria_chat_get_memory', array($this, 'ajax_get_memory'));
        add_action('wp_ajax_nopriv_aria_chat_get_memory', array($this, 'ajax_get_memory'));
        add_action('wp_ajax_aria_chat_save_memory', array($this, 'ajax_save_memory'));
        add_action('wp_ajax_nopriv_aria_chat_save_memory', array($this, 'ajax_save_memory'));
        add_action('wp_ajax_aria_chat_delete_memory', array($this, 'ajax_delete_memory'));
        add_action('wp_ajax_nopriv_aria_chat_delete_memory', array($this, 'ajax_delete_memory'));
        add_action('wp_ajax_aria_chat_save_response_time', array($this, 'ajax_save_response_time'));
        add_action('wp_ajax_nopriv_aria_chat_save_response_time', array($this, 'ajax_save_response_time'));
        add_action('wp_ajax_aria_chat_get_avg_response_time', array($this, 'ajax_get_avg_response_time'));
        add_action('wp_ajax_nopriv_aria_chat_get_avg_response_time', array($this, 'ajax_get_avg_response_time'));
        add_action('wp_ajax_aria_chat_verify_age', array($this, 'ajax_verify_age'));
        add_action('wp_ajax_nopriv_aria_chat_verify_age', array($this, 'ajax_verify_age'));
    }
    
    private function send_json($data) {
        wp_send_json($data);
    }
    
    public function ajax_login() {
        $username = sanitize_text_field($_POST['username'] ?? '');
        $password = isset($_POST['password']) ? $_POST['password'] : '';
        if (!$username || !$password) {
            $this->send_json(array('success' => false, 'error' => 'Username e password richiesti'));
            return;
        }
        $prova = $this->guest_session();
        $result = $this->auth_manager->login($username, $password);

        // se ARIA non conosce l'utente, provo le credenziali WordPress: è l'account
        // vero del sito, l'ARIA viene creato/collegato qui
        if (empty($result['success'])) {
            $wp = wp_authenticate($username, $password);
            if (!is_wp_error($wp)) {
                wp_set_current_user($wp->ID);
                wp_set_auth_cookie($wp->ID, true, is_ssl());
                $this->auth_manager->set_user_id($wp->ID);
                if ($this->assicura_account() && $this->auth_manager->ensure_authenticated()) {
                    $result = array('success' => true, 'auto_login' => true);
                }
            }
        }

        if (isset($result['success']) && $result['success']) {
            $this->ensure_age_verified();
            if ($prova && !empty($prova['uid'])) {
                $this->api_client->set_access_token($this->auth_manager->get_access_token());
                $this->api_client->merge_guest($prova['uid']);
                delete_transient('aria_guest_' . $this->guest_token());
                setcookie('aria_guest', '', array('expires' => time() - 3600, 'path' => '/'));
            }
            $stored_birth_date = get_option('aria_chat_' . get_current_user_id() . '_birth_date', '');
            if ($stored_birth_date) {
                if (preg_match('/^(\d{4})/', $stored_birth_date, $m)) {
                    $birth_year = intval($m[1]);
                    if ($birth_year > 0) {
                        $token = $this->auth_manager->get_access_token();
                        if ($token) {
                            $this->api_client->set_access_token($token);
                            $this->api_client->verify_age($birth_year);
                        }
                    }
                }
            }
        }
        $this->send_json($result);
    }
    
    public function ajax_register() {
        $username = sanitize_text_field($_POST['username'] ?? '');
        $email = sanitize_email($_POST['email'] ?? '');
        $password = isset($_POST['password']) ? $_POST['password'] : '';
        $birth_date = sanitize_text_field($_POST['birth_date'] ?? '');
        if (!$username || !$email || !$password || !$birth_date) {
            $this->send_json(array('success' => false, 'error' => 'Tutti i campi sono obbligatori'));
            return;
        }
        if (strlen($password) < 6) {
            $this->send_json(array('success' => false, 'error' => 'Password almeno 6 caratteri'));
            return;
        }
        $result = $this->api_client->register($username, $email, $password, $birth_date);
        if (isset($result['success']) && $result['success']) {
            $login_result = $this->auth_manager->login($username, $password);
            if (isset($login_result['success']) && $login_result['success']) {
                $birth_year = 0;
                if (preg_match('/^(\d{4})/', $birth_date, $m)) {
                    $birth_year = intval($m[1]);
                }
                // crea anche l'utente WordPress e lo autentica: senza, dopo la
                // registrazione si resterebbe comunque fuori dal sito
                $wp_user_id = username_exists($username);
                if (!$wp_user_id) {
                    $wp_user_id = wp_create_user($username, $password, $email);
                }
                if (!is_wp_error($wp_user_id)) {
                    $u = new WP_User($wp_user_id);
                    $u->set_role('subscriber');
                    wp_set_current_user($wp_user_id);
                    wp_set_auth_cookie($wp_user_id, true, is_ssl());
                    $prova_reg = $this->guest_session();
                    if ($prova_reg && !empty($prova_reg['uid'])) {
                        $this->auth_manager->set_user_id($wp_user_id);
                        $this->api_client->set_access_token($this->auth_manager->get_access_token());
                        $this->api_client->merge_guest($prova_reg['uid']);
                        delete_transient('aria_guest_' . $this->guest_token());
                    }
                }
                update_option('aria_chat_' . get_current_user_id() . '_birth_date', $birth_date, false);
                if ($birth_year > 0) {
                    $token = $this->auth_manager->get_access_token();
                    if ($token) {
                        $this->api_client->set_access_token($token);
                        $this->api_client->verify_age($birth_year);
                    }
                }
                $this->send_json(array('success' => true, 'message' => 'Registrazione completata!', 'auto_login' => true));
                return;
            }
        }
        $error_msg = 'Registrazione fallita';
        if (isset($result['error'])) {
            if (is_array($result['error'])) {
                $error_msg = isset($result['error']['detail']) ? $result['error']['detail'] : json_encode($result['error']);
            } else {
                $error_msg = $result['error'];
            }
        }
        $this->send_json(array('success' => false, 'error' => $error_msg));
    }
    
    public function ajax_logout() {
        $token_from_js = sanitize_text_field($_POST['token'] ?? '');
        if ($token_from_js) {
            $this->api_client->set_access_token($token_from_js);
        }
        $this->auth_manager->logout();
        $this->send_json(array('success' => true));
        wp_die();
    }
    

    /**
     * Traduce l'errore del backend in un messaggio leggibile.
     * Il limite giornaliero arriva come oggetto annidato (`detail.message`): senza questa
     * mappatura l'utente vedeva "[object Object]" o il token "premium_required".
     */
    private function human_error($result) {
        $code = isset($result['code']) ? intval($result['code']) : 0;
        $detail = isset($result['error']) ? $result['error'] : '';
        if (is_string($detail) && strpos(ltrim($detail), '{') === 0) {
            $decoded = json_decode($detail, true);
            if (is_array($decoded) && isset($decoded['detail'])) {
                $detail = $decoded['detail'];
            }
        }
        if (is_array($detail)) {
            if (!empty($detail['message'])) {
                return strval($detail['message']);
            }
            if (!empty($detail['error'])) {
                $detail = $detail['error'];
            }
        }
        $detail = trim(strval($detail));

        if ($detail === 'premium_required' || $code === 403) {
            return "Per questa chat serve la verifica dell'eta': conferma il gate 18+ e riprova.";
        }
        if ($detail === 'risposta_in_corso') {
            return "Hai già una risposta in corso: aspetta che finisca e riprova.";
        }
        if ($detail === 'daily_limit_reached' || $code === 429) {
            return "Limite giornaliero di messaggi raggiunto. Torna domani oppure sblocca i messaggi illimitati.";
        }
        if ($detail === 'character not found') {
            return "Personaggio non disponibile: ricarica la pagina e riprova.";
        }
        if ($code >= 500) {
            return "Il servizio chat non risponde (" . $code . "): riprova tra qualche secondo.";
        }
        if ($detail === '') {
            return "Errore del servizio chat (" . ($code ?: "sconosciuto") . ").";
        }
        return $detail;
    }


    /**
     * Invio in streaming (Server-Sent Events).
     * Fa da ponte tra il browser e il backend: legge l'SSE di `/chat/stream` e lo
     * riverbera, svuotando i buffer a ogni pezzo. Se qualcosa non va, il client
     * ricade da solo sull'invio normale (`aria_chat_send`).
     */


    /** Rigenera (o corregge e rigenera) l'ultima risposta: ponte SSE. */
    public function ajax_regenerate() {
        while (ob_get_level() > 0) {
            @ob_end_flush();
        }
        header('Content-Type: text/event-stream; charset=utf-8');
        header('Cache-Control: no-cache, no-transform');
        header('X-Accel-Buffering: no');

        $character_id = sanitize_text_field($_POST['character'] ?? '');
        $testo = isset($_POST['text']) ? sanitize_textarea_field($_POST['text']) : null;
        $current_user = wp_get_current_user();
        $username = sanitize_text_field($_POST['username'] ?? (($current_user && $current_user->exists()) ? $current_user->user_login : 'Ospite'));

        if (!$character_id) {
            echo "event: error\ndata: {\"error\":\"Personaggio mancante\"}\n\n";
            exit;
        }
        if (!$this->autorizza(true)) {
            exit;
        }

        $corpo = array('character' => $character_id, 'username' => $username);
        if ($testo !== null) {
            $corpo['text'] = $testo;
        }
        $resto = '';
        $ch = curl_init(rtrim($this->api_client->get_base_url(), '/') . '/chat/regenerate');
        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => wp_json_encode($corpo),
            CURLOPT_HTTPHEADER => array('Content-Type: application/json', 'Authorization: Bearer ' . $this->api_client->get_access_token(), 'Accept: text/event-stream'),
            CURLOPT_TIMEOUT => 400,
            CURLOPT_WRITEFUNCTION => function ($curl, $pezzo) use (&$resto) {
                $resto .= $pezzo;
                while (($pos = strpos($resto, "\n\n")) !== false) {
                    echo substr($resto, 0, $pos + 2);
                    $resto = substr($resto, $pos + 2);
                    @flush();
                }
                return strlen($pezzo);
            },
        ));
        curl_exec($ch);
        curl_close($ch);
        if ($resto !== '') {
            echo $resto;
        }
        exit;
    }

    /** Esporta la conversazione in .txt (download). */
    public function ajax_export() {
        $character_id = sanitize_text_field($_GET['character'] ?? '');
        if (!$character_id || !$this->auth_manager->ensure_authenticated()) {
            status_header(400);
            exit('Personaggio mancante o sessione non valida');
        }
        $this->api_client->set_access_token($this->auth_manager->get_access_token());
        $url = rtrim($this->api_client->get_base_url(), '/') . '/chat/export?character=' . rawurlencode($character_id);
        $risposta = wp_remote_get($url, array(
            'timeout' => 60,
            'headers' => array('Authorization' => 'Bearer ' . $this->auth_manager->get_access_token()),
        ));
        if (is_wp_error($risposta)) {
            status_header(502);
            exit('Export non riuscito');
        }
        $corpo = wp_remote_retrieve_body($risposta);
        nocache_headers();
        header('Content-Type: text/plain; charset=utf-8');
        header('Content-Disposition: attachment; filename="' . $character_id . '.txt"');
        header('Content-Length: ' . strlen($corpo));
        echo $corpo;
        exit;
    }

    /** Apertura automatica della chat da parte del personaggio (ponte SSE). */
    public function ajax_chat_opening() {
        while (ob_get_level() > 0) {
            @ob_end_flush();
        }
        header('Content-Type: text/event-stream; charset=utf-8');
        header('Cache-Control: no-cache, no-transform');
        header('X-Accel-Buffering: no');

        $character_id = sanitize_text_field($_POST['character'] ?? '');
        $current_user = wp_get_current_user();
        $username = sanitize_text_field($_POST['username'] ?? (($current_user && $current_user->exists()) ? $current_user->user_login : 'Ospite'));

        if (!$character_id) {
            echo "event: skip\ndata: {}\n\n";
            exit;
        }
        if (!$this->auth_manager->ensure_authenticated()) {
            echo "event: skip\ndata: {}\n\n";
            exit;
        }
        $token = $this->auth_manager->get_access_token();
        if (!$token) {
            echo "event: skip\ndata: {}\n\n";
            exit;
        }
        $this->api_client->set_access_token($token);

        $payload = wp_json_encode(array('character' => $character_id, 'username' => $username));
        $resto = '';
        $ch = curl_init(rtrim($this->api_client->get_base_url(), '/') . '/chat/opening');
        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => array('Content-Type: application/json', 'Authorization: Bearer ' . $this->api_client->get_access_token(), 'Accept: text/event-stream'),
            CURLOPT_TIMEOUT => 240,
            CURLOPT_WRITEFUNCTION => function ($curl, $pezzo) use (&$resto) {
                $resto .= $pezzo;
                while (($pos = strpos($resto, "\n\n")) !== false) {
                    echo substr($resto, 0, $pos + 2);
                    $resto = substr($resto, $pos + 2);
                    @flush();
                }
                return strlen($pezzo);
            },
        ));
        curl_exec($ch);
        curl_close($ch);
        if ($resto !== '') {
            echo $resto;
        }
        exit;
    }



    /**
     * Login WordPress: se c'è una prova in corso la unisce all'account dell'utente,
     * così i messaggi scritti da ospite non si perdono.
     */
    public function merge_guest_on_wp_login($user_login, $user) {
        $sess = $this->guest_session();
        if (!$sess || empty($sess['uid']) || !($user instanceof WP_User)) {
            return;
        }
        wp_set_current_user($user->ID); // al wp_login il cookie non è ancora attivo
        $this->auth_manager->set_user_id($user->ID);
        if (!$this->assicura_account() || !$this->auth_manager->ensure_authenticated()) {
            return; // utente senza account ARIA: niente da unire
        }
        $this->api_client->set_access_token($this->auth_manager->get_access_token());
        $this->api_client->merge_guest($sess['uid']);
        delete_transient('aria_guest_' . $this->guest_token());
        setcookie('aria_guest', '', array('expires' => time() - 3600, 'path' => '/'));
    }


    /**
     * Ogni utente WordPress ottiene un account ARIA trasparente: senza, il login
     * WordPress non basterebbe per chattare e la prova da ospite non avrebbe dove
     * essere unita. Il token persistente viene salvato sull'utente.
     */
    private function assicura_account() {
        if ($this->auth_manager->get_persistent_token()) {
            return true;
        }
        if (!is_user_logged_in()) {
            return false;
        }
        $username = 'wp_' . get_current_user_id() . '_' . bin2hex(random_bytes(4));
        $password = bin2hex(random_bytes(12));
        $reg = $this->api_client->register($username, '', $password, '1990-01-01');
        if (empty($reg['success'])) {
            return false;
        }
        $dati = $reg['data'];
        $this->auth_manager->save_tokens($dati['access_token'] ?? '', $dati['refresh_token'] ?? '');
        $this->auth_manager->save_persistent_token($dati['persistent_token'] ?? '');
        return !empty($dati['persistent_token']);
    }


    /** Blocco successivo di card della griglia (paginazione dal server). */
    public function ajax_grid_more() {
        $cat = sanitize_title($_POST['category'] ?? '');
        $offset = max(0, (int) ($_POST['offset'] ?? 0));
        $passo = min(120, max(12, (int) ($_POST['step'] ?? 60)));
        if (!$cat) {
            wp_die('');
        }
        $personaggi = array_slice(aria_grid_characters($cat), $offset, $passo);
        $base = trailingslashit(get_post_type_archive_link('stanza'));
        $stanza = get_page_by_path($cat, OBJECT, 'stanza');
        $room_url = $stanza ? get_permalink($stanza) : $base;
        ob_start();
        foreach ($personaggi as $c) {
            $link = !empty($c['slug'])
                ? trailingslashit($room_url) . $c['slug'] . '/'
                : add_query_arg('char', rawurlencode($c['id']), $room_url);
            $desc = trim(preg_replace('/^' . preg_quote($c['name'], '/') . '\s*[—–-]\s*/u', '', $c['desc']));
            printf(
                '<a class="aria-character-card" href="%s" title="Chatta con %s"><div class="aria-character-avatar">%s</div><h3>%s</h3><p>%s</p></a>',
                esc_url($link),
                esc_attr($c['name']),
                esc_html($c['avatar']),
                esc_html($c['name']),
                esc_html($desc)
            );
        }
        echo ob_get_clean();
        wp_die();
    }

    /** Quanti messaggi può scrivere chi non è registrato. */
    const GUEST_LIMIT = 4;

    private function guest_token() {
        $t = isset($_COOKIE['aria_guest']) ? preg_replace('/[^a-f0-9]/', '', (string) $_COOKIE['aria_guest']) : '';
        return $t;
    }

    private function guest_session() {
        $t = $this->guest_token();
        if (!$t) {
            return null;
        }
        $sess = get_transient('aria_guest_' . $t);
        return is_array($sess) && !empty($sess['uid']) ? $sess : null;
    }

    private function guest_save($t, $sess) {
        set_transient('aria_guest_' . $t, $sess, 7 * DAY_IN_SECONDS);
    }

    /**
     * Apre una sessione di prova: crea un utente ARIA usa e getta e lascia
     * scrivere pochi messaggi. Serve a far provare la chat prima del login.
     */
    public function ajax_chat_guest() {
        $sess = $this->guest_session();
        if ($sess) {
            $this->send_json(array('success' => true, 'usati' => (int) $sess['n'], 'limite' => self::GUEST_LIMIT));
            return;
        }
        $username = 'ospite_' . bin2hex(random_bytes(6));
        $password = bin2hex(random_bytes(12));
        $reg = $this->api_client->register($username, '', $password, '1990-01-01');
        if (empty($reg['success'])) {
            $this->send_json(array('success' => false, 'error' => 'Prova non disponibile'));
            return;
        }
        $dati = $reg['data'];
        $ptk = $dati['persistent_token'] ?? '';
        if (empty($ptk)) {
            $this->send_json(array('success' => false, 'error' => 'Prova non disponibile'));
            return;
        }
        $this->api_client->set_access_token($dati['access_token'] ?? '');
        $this->api_client->verify_age(1990);

        $t = bin2hex(random_bytes(16));
        $this->guest_save($t, array('uid' => $dati['user']['id'] ?? '', 'ptk' => $ptk, 'n' => 0));
        setcookie('aria_guest', $t, array(
            'expires' => time() + 7 * DAY_IN_SECONDS,
            'path' => '/',
            'httponly' => true,
            'samesite' => 'Lax',
            'secure' => is_ssl(),
        ));
        $this->send_json(array('success' => true, 'usati' => 0, 'limite' => self::GUEST_LIMIT));
    }

    /**
     * Autentica la richiesta: utente WordPress normale oppure sessione di prova.
     * Restituisce true se si può proseguire, altrimenti emette l'errore.
     */
    private function autorizza($stream = false) {
        $errore = function ($msg, $codice = '') use ($stream) {
            if ($stream) {
                echo "event: error\ndata: " . wp_json_encode(array('error' => $msg, 'code' => $codice)) . "\n\n";
                exit;
            }
            $this->send_json(array('success' => false, 'error' => $msg, 'code' => $codice));
        };

        $sess = $this->guest_session();
        if (!$sess) {
            $this->assicura_account();
            if (!$this->auth_manager->ensure_authenticated()) {
                $errore('Sessione scaduta: esegui di nuovo il login nella chat');
                return false;
            }
            $this->api_client->set_access_token($this->auth_manager->get_access_token());
            return true;
        }

        $t = $this->guest_token();
        if ((int) $sess['n'] >= self::GUEST_LIMIT) {
            $errore('Prova terminata: accedi o registrati per continuare a chattare.', 'guest_limit');
            return false;
        }
        $reauth = $this->api_client->reauth($sess['ptk']);
        if (empty($reauth['success']) || empty($reauth['data']['access_token'])) {
            delete_transient('aria_guest_' . $t);
            $errore('Prova scaduta: accedi per continuare.', 'guest_limit');
            return false;
        }
        $this->api_client->set_access_token($reauth['data']['access_token']);
        $sess['n'] = (int) $sess['n'] + 1;
        $this->guest_save($t, $sess);
        return true;
    }

    public function ajax_send_stream() {
        while (ob_get_level() > 0) {
            @ob_end_flush();
        }
        header('Content-Type: text/event-stream; charset=utf-8');
        header('Cache-Control: no-cache, no-transform');
        header('X-Accel-Buffering: no');
        header('Connection: keep-alive');

        $esci = function ($evento, $dati) {
            echo "event: " . $evento . "\ndata: " . wp_json_encode($dati) . "\n\n";
            @flush();
        };

        $character_id = sanitize_text_field($_POST['character'] ?? '');
        $text = sanitize_textarea_field($_POST['text'] ?? '');
        $current_user = wp_get_current_user();
        $username = sanitize_text_field($_POST['username'] ?? (($current_user && $current_user->exists()) ? $current_user->user_login : 'Ospite'));

        if (!$character_id || !$text) {
            $esci('error', array('error' => 'Personaggio e messaggio richiesti'));
            exit;
        }
        if (!$this->autorizza(true)) {
            exit;
        }
        if (!$this->guest_session()) {
            $this->ensure_age_verified();
        }

        $payload = wp_json_encode(array(
            'character' => $character_id,
            'text' => $text,
            'username' => $username,
        ));

        $buffer_parziale = '';
        $ch = curl_init(rtrim($this->api_client->get_base_url(), '/') . '/chat/stream');
        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => array(
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->api_client->get_access_token(),
                'Accept: text/event-stream',
            ),
            CURLOPT_TIMEOUT => 300,
            CURLOPT_WRITEFUNCTION => function ($curl, $pezzo) use ($esci, &$buffer_parziale) {
                $buffer_parziale .= $pezzo;
                // Riverbera i frame completi senza reinterpretarli
                while (($pos = strpos($buffer_parziale, "\n\n")) !== false) {
                    $frame = substr($buffer_parziale, 0, $pos + 2);
                    $buffer_parziale = substr($buffer_parziale, $pos + 2);
                    echo $frame;
                    @flush();
                }
                return strlen($pezzo);
            },
        ));
        curl_exec($ch);
        $errore = curl_error($ch);
        $stato = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);

        if ($buffer_parziale !== '') {
            echo $buffer_parziale;
        }
        if ($errore) {
            $esci('error', array('error' => 'Connessione al servizio chat interrotta: ' . $errore));
        } elseif ($stato >= 400) {
            $esci('error', array('error' => $this->human_error(array('code' => $stato, 'error' => ''))));
        }
        exit;
    }

    public function ajax_send_message() {
        $character_id = sanitize_text_field($_POST['character'] ?? '');
        $text = sanitize_textarea_field($_POST['text'] ?? '');
        $current_user = wp_get_current_user();
        $username = sanitize_text_field($_POST['username'] ?? (($current_user && $current_user->exists()) ? $current_user->user_login : 'Ospite'));
        
        if (!$character_id || !$text) {
            $this->send_json(array('success' => false, 'error' => 'Personaggio e messaggio richiesti'));
            return;
        }
        
        // Sessione ARIA: JWT scaduto (15 min) -> refresh -> fallback token persistente
        if (!$this->auth_manager->ensure_authenticated()) {
            $this->send_json(array('success' => false, 'error' => 'Sessione scaduta: esegui di nuovo il login nella chat'));
            wp_die();
            return;
        }
        $token = $this->auth_manager->get_access_token();
        if (!$token) {
            $this->send_json(array('success' => false, 'error' => 'Token mancante: riprova il login'));
            wp_die();
            return;
        }
        $this->api_client->set_access_token($token);
        $this->ensure_age_verified();
        
        $result = $this->api_client->chat($character_id, $text, $username);
        
        if (!isset($result['success']) || !$result['success']) {
            // 401: forza una ri-autenticazione e riprova una sola volta (niente logout automatico)
            $is_auth_error = isset($result['code']) && (int) $result['code'] === 401;
            if ($is_auth_error) {
                $this->auth_manager->clear_tokens();
                if ($this->auth_manager->ensure_authenticated()) {
                    $this->api_client->set_access_token($this->auth_manager->get_access_token());
                    $result = $this->api_client->chat($character_id, $text, $username);
                }
            }
            if (!isset($result['success']) || !$result['success']) {
                $err_detail = $this->human_error($result);
                $this->send_json(array('success' => false, 'error' => $err_detail));
                wp_die();
                return;
            }
        }
        
        $this->send_json($result);
        wp_die();
    }
    

    public function ajax_refresh_token() {
        $refresh_from_js = sanitize_text_field($_POST['refresh_token'] ?? '');
        if ($refresh_from_js) {
            $this->auth_manager->save_tokens('', $refresh_from_js);
        }
        $token = $this->auth_manager->get_access_token();
        if (!$token) {
            $refresh = $this->auth_manager->get_refresh_token();
            if ($refresh) {
                $this->auth_manager->api_client->set_access_token('');
                $result = $this->auth_manager->refresh_access_token();
                if (isset($result['success']) && $result['success']) {
                    $new_access = $this->auth_manager->get_access_token();
                    $this->send_json(array('success' => true, 'message' => 'Token ripristinato', 'access_token' => $new_access, 'refresh_token' => $refresh_from_js));
                    wp_die();
                }
            } else {
                $this->send_json(array('success' => false, 'error' => 'Nessun refresh token'));
            }
            wp_die();
            return;
        }
        $this->send_json(array('success' => true, 'message' => 'Token valido'));
        wp_die();
    }



    public function ajax_get_memory() {
        global $wpdb;
        $uid = intval($_POST['user_id'] ?? get_current_user_id());
        $char = sanitize_text_field($_POST['character_id'] ?? '');
        $table = 'user_memory_items';
        if ($wpdb->get_var("SHOW TABLES LIKE 'user_memory_items'") != 'user_memory_items') {
            $this->send_json(array('success'=>true,'data'=>array()));
            wp_die();
        }
        $mem = array();
        if ($uid <= 0) {
            $uid = get_current_user_id();
        }
        if ($char) {
            $rows = $wpdb->get_results($wpdb->prepare("SELECT memory_key, memory_value FROM $table WHERE user_id=%d AND character_id=%s", $uid, $char));
        } else {
            $rows = $wpdb->get_results($wpdb->prepare("SELECT memory_key, memory_value FROM $table WHERE user_id=%d", $uid));
        }
        if ($rows) {
            foreach ($rows as $row) {
                $mem[$row->memory_key] = $row->memory_value;
            }
        }
        $this->send_json(array('success'=>true,'data'=>$mem));
        wp_die();
    }
    public function ajax_save_memory() {
        global $wpdb;
        $uid = intval($_POST['user_id'] ?? get_current_user_id());
        $char = sanitize_text_field($_POST['character_id'] ?? '');
        $k = sanitize_text_field($_POST['key'] ?? '');
        $v = sanitize_textarea_field($_POST['value'] ?? '');
        $token = sanitize_text_field($_POST['token'] ?? '');
        if ($k === '') {
            $this->send_json(array('success'=>false,'error'=>'key required'));
            wp_die();
        }
        // Se user_id non è passato o è 0, prova a risalire dall'utente WP loggato
        if ($uid <= 0) {
            $uid = get_current_user_id();
        }
        if ($uid <= 0) {
            $this->send_json(array('success'=>false,'error'=>'user not logged in'));
            wp_die();
        }
        $table = 'user_memory_items';
        if ($wpdb->get_var("SHOW TABLES LIKE 'user_memory_items'") != 'user_memory_items') {
            $this->send_json(array('success'=>false,'error'=>'table not found'));
            wp_die();
        }
        $wpdb->query($wpdb->prepare("INSERT INTO $table (user_id, character_id, memory_key, memory_value, updated_at) VALUES (%d,%s,%s,%s,NOW()) ON CONFLICT (user_id, character_id, memory_key) DO UPDATE SET memory_value=EXCLUDED.memory_value, updated_at=NOW()", $uid, $char, $k, $v));
        $this->send_json(array('success'=>true));
        wp_die();
    }
    public function ajax_delete_memory() {
        global $wpdb;
        $uid = intval($_POST['user_id'] ?? get_current_user_id());
        $char = sanitize_text_field($_POST['character_id'] ?? '');
        $table = 'user_memory_items';
        if ($wpdb->get_var("SHOW TABLES LIKE '$table'") == $table) {
            if ($uid <= 0) {
                $uid = get_current_user_id();
            }
            if ($char) {
                $wpdb->delete($table, array('user_id' => $uid, 'character_id' => $char));
            } else {
                $wpdb->delete($table, array('user_id' => $uid));
            }
        }
        $this->send_json(array('success'=>true));
        wp_die();
    }

    public function ajax_get_characters() {
        $category = isset($_POST['category']) ? sanitize_text_field($_POST['category']) : null;
        $search = isset($_POST['search']) ? sanitize_text_field($_POST['search']) : '';
        if ($this->auth_manager->is_logged_in()) {
            $token = $this->auth_manager->get_access_token();
            if ($token) {
                $this->api_client->set_access_token($token);
            }
        }
        if ($search !== '') {
            $result = $this->api_client->search_characters($search, $category);
            $this->send_json($result);
            return;
        }
        $limit = isset($_POST['limit']) ? intval($_POST['limit']) : 100;
        $offset = isset($_POST['offset']) ? intval($_POST['offset']) : 0;
        $result = $this->api_client->get_characters($category, $limit, $offset);
        $this->send_json($result);
    }
    
    public function ajax_get_categories() {
        $adult = isset($_POST['adult']) && $_POST['adult'] === 'true';
        $result = $this->api_client->get_categories($adult);
        $this->send_json($result);
    }
    
    public function ajax_auth_status() {
        $current_user = wp_get_current_user();
        // Prova a riattivare la sessione ARIA in modo trasparente (token persistente)
        $this->auth_manager->ensure_authenticated();
        $this->send_json(array(
            'isLoggedIn' => $this->auth_manager->is_logged_in(),
            'wpLoggedIn' => is_user_logged_in() ? true : false,
            'userId' => get_current_user_id(),
            'username' => ($current_user && $current_user->exists()) ? $current_user->user_login : 'Ospite'
        ));
    }
    
    public function ajax_get_config() {
        if (!$this->auth_manager->is_logged_in()) {
            $this->send_json(array('success' => false, 'error' => 'Non autenticato'));
            return;
        }
        $token = $this->auth_manager->get_access_token();
        $this->api_client->set_access_token($token);
        $result = $this->api_client->get_config();
        $this->send_json($result);
    }
    
    public function ajax_set_config() {
        if (!$this->auth_manager->is_logged_in()) {
            $this->send_json(array('success' => false, 'error' => 'Non autenticato'));
            return;
        }
        $provider = sanitize_text_field($_POST['provider'] ?? '');
        $model = sanitize_text_field($_POST['model'] ?? '');
        $token = $this->auth_manager->get_access_token();
        $this->api_client->set_access_token($token);
        $result = $this->api_client->set_config($provider, $model);
        $this->send_json($result);
    }

    /**
     * Tabella dei tempi di risposta (creata on demand).
     *
     * La barra di caricamento deve essere proporzionale al tempo REALE di QUELLA
     * chat: quindi i tempi si registrano per utente + personaggio e non si usa
     * una media globale unica. Indici per le due letture (coppia e personaggio).
     */
    private function ensure_stats_table() {
        global $wpdb;
        static $done = false;
        if ($done) return;
        $done = true;
        $wpdb->query(
            "CREATE TABLE IF NOT EXISTS chat_response_stats (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                user_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
                character_id VARCHAR(64) NOT NULL DEFAULT '',
                response_time_ms INT UNSIGNED NOT NULL DEFAULT 0,
                message_text TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY user_char_created (user_id, character_id, created_at),
                KEY char_created (character_id, created_at),
                KEY created (created_at)
            )"
        );
    }

    /** Limiti di plausibilita': sotto 300 ms e sopra 3 minuti il campione e' rumore. */
    private function ms_is_plausible($ms) {
        return ($ms >= 300 && $ms <= 180000);
    }

    /**
     * Media del tempo di risposta per una chat (utente+personaggio), sulle ultime
     * misurazioni. Se la coppia ha pochi campioni si allarga al personaggio, poi a
     * tutta la chat del sito, infine a un default prudente.
     */
    private function avg_response_ms($character_id, $uid, $min_samples = 3) {
        global $wpdb;
        $character_id = (string) $character_id;

        // 1) La chat esatta (utente + personaggio): si usano TUTTI i suoi campioni.
        if ($uid > 0 && $character_id !== '') {
            $row = $wpdb->get_row($wpdb->prepare(
                "SELECT COUNT(*) AS n, ROUND(AVG(response_time_ms)) AS avg
                 FROM chat_response_stats
                 WHERE user_id = %d AND character_id = %s AND response_time_ms BETWEEN 300 AND 180000",
                $uid, $character_id
            ));
            if ($row && (int) $row->n >= $min_samples && $row->avg) {
                return array(intval($row->avg), (int) $row->n, 'chat');
            }
        }
        // 2) Tutti gli utenti su quel personaggio (il carattere risponde con tempi suoi).
        if ($character_id !== '') {
            $row = $wpdb->get_row($wpdb->prepare(
                "SELECT COUNT(*) AS n, ROUND(AVG(response_time_ms)) AS avg
                 FROM chat_response_stats
                 WHERE character_id = %s AND response_time_ms BETWEEN 300 AND 180000",
                $character_id
            ));
            if ($row && (int) $row->n >= $min_samples && $row->avg) {
                return array(intval($row->avg), (int) $row->n, 'personaggio');
            }
        }
        // 3) Tutta la chat del sito.
        $row = $wpdb->get_row(
            "SELECT COUNT(*) AS n, ROUND(AVG(response_time_ms)) AS avg
             FROM chat_response_stats
             WHERE response_time_ms BETWEEN 300 AND 180000"
        );
        if ($row && $row->avg) {
            return array(intval($row->avg), (int) $row->n, 'globale');
        }
        return array(5000, 0, 'default');
    }

    public function ajax_save_response_time() {
        global $wpdb;
        $this->ensure_stats_table();
        $uid = get_current_user_id();
        $ms = intval($_POST['ms'] ?? 0);
        $char = substr(sanitize_text_field($_POST['character_id'] ?? ''), 0, 64);
        $text = sanitize_text_field($_POST['text'] ?? '');
        if (!$this->ms_is_plausible($ms)) {
            $this->send_json(array('success' => false, 'error' => 'ms non plausibile'));
            wp_die();
        }
        // Tetto ai campioni per utente+personaggio: la media segue i tempi attuali,
        // non resta trascinata da misurazioni vecchie di settimane.
        $wpdb->query($wpdb->prepare(
            "INSERT INTO chat_response_stats (user_id, character_id, response_time_ms, message_text, created_at) VALUES (%d,%s,%d,%s,NOW())",
            $uid, $char, $ms, mb_substr($text, 0, 200)
        ));
        list($avg, $samples, $scope) = $this->avg_response_ms($char, $uid);
        $this->send_json(array('success' => true, 'avg_ms' => $avg, 'samples' => $samples, 'scope' => $scope));
        wp_die();
    }

    public function ajax_get_avg_response_time() {
        $this->ensure_stats_table();
        $char = substr(sanitize_text_field($_POST['character_id'] ?? ($_POST['character'] ?? '')), 0, 64);
        list($avg, $samples, $scope) = $this->avg_response_ms($char, get_current_user_id());
        $this->send_json(array(
            'success' => true,
            'avg_ms' => $avg,
            'samples' => $samples,
            'scope' => $scope,
            'character_id' => $char
        ));
        wp_die();
    }

    public function ajax_verify_age() {
        if (!is_user_logged_in()) {
            $this->send_json(array('success' => false, 'error' => 'Login WordPress richiesto'));
            wp_die();
        }
        $uid = get_current_user_id();
        $birth_year = intval($_POST['birth_year'] ?? 0);
        if (!$birth_year) {
            $stored = get_option('aria_chat_' . $uid . '_birth_date', '');
            if (preg_match('/^(\d{4})/', (string) $stored, $m)) {
                $birth_year = intval($m[1]);
            }
        }
        if (!$birth_year) {
            $birth_year = 2000; // confermato 18+ dal gate del sito
        }
        // Ricorda la conferma: serve per riallineare il backend dopo un nuovo login
        update_option('aria_chat_' . $uid . '_age_confirmed', 1, false);

        if (!$this->auth_manager->ensure_authenticated()) {
            $this->send_json(array('success' => false, 'error' => 'Serve il login nella chat (sessione ARIA)'));
            wp_die();
        }
        $this->api_client->set_access_token($this->auth_manager->get_access_token());
        $result = $this->api_client->verify_age($birth_year);
        if (isset($result['success']) && $result['success']) {
            update_option('aria_chat_' . $uid . '_age_pushed', 1, false);
            $this->send_json(array('success' => true, 'age_verified' => true));
        } else {
            $err = isset($result['error']) ? strval($result['error']) : 'Verifica fallita';
            if (preg_match('/\"detail\"\s*:\s*\"([^\"]+)\"/', $err, $m)) {
                $err = $m[1];
            }
            $this->send_json(array('success' => false, 'error' => $err));
        }
        wp_die();
    }

    /**
     * I personaggi 18+ sono bloccati dal backend se l'eta' non e' verificata LATO SERVER:
     * allineiamo il flag una sola volta per utente, usando la conferma gia' data nel gate.
     */
    private function ensure_age_verified() {
        $uid = get_current_user_id();
        if (!$uid || get_option('aria_chat_' . $uid . '_age_pushed', '') === '1') {
            return;
        }
        if (get_option('aria_chat_' . $uid . '_age_confirmed', '') !== '1') {
            return;
        }
        $birth_year = 2000;
        $stored = get_option('aria_chat_' . $uid . '_birth_date', '');
        if (preg_match('/^(\d{4})/', (string) $stored, $m)) {
            $birth_year = intval($m[1]);
        }
        $this->api_client->set_access_token($this->auth_manager->get_access_token());
        $result = $this->api_client->verify_age($birth_year);
        if (isset($result['success']) && $result['success']) {
            update_option('aria_chat_' . $uid . '_age_pushed', 1, false);
        }
    }

}
