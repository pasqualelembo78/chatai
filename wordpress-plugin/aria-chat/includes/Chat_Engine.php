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
        $result = $this->auth_manager->login($username, $password);
        if (isset($result['success']) && $result['success']) {
            $this->ensure_age_verified();
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
