<?php
/**
 * Auth Manager - Gestione JWT e sessioni utente
 */

if (!defined('ABSPATH')) exit;

class Aria_Auth_Manager {
    
    private $api_client;
    private $user_id;
    
    public function __construct($user_id = null) {
        $this->user_id = $user_id ? $user_id : get_current_user_id();
        $this->api_client = new Aria_API_Client();
    }
    
    private function get_option_key($key) {
        return 'aria_chat_' . $this->user_id . '_' . $key;
    }
    
    public function get_access_token() {
        return get_option($this->get_option_key('access_token'), '');
    }
    
    public function get_refresh_token() {
        return get_option($this->get_option_key('refresh_token'), '');
    }
    
    public function save_tokens($access_token, $refresh_token) {
        update_option($this->get_option_key('access_token'), $access_token, false);
        update_option($this->get_option_key('refresh_token'), $refresh_token, false);
        $this->api_client->set_access_token($access_token);
    }
    
    public function get_persistent_token() {
        $token = get_option($this->get_option_key('persistent_token'), '');
        // Solo per un amministratore e' ammesso il token di riserva impostato dalle opzioni plugin:
        // gli utenti normali usano esclusivamente il proprio, cosi le memorie restano separate.
        if (!$token && user_can($this->user_id, 'manage_options')) {
            $token = trim((string) get_option('aria_chat_admin_persistent_token', ''));
        }
        return $token;
    }
    
    public function save_persistent_token($persistent_token) {
        if (!empty($persistent_token)) {
            update_option($this->get_option_key('persistent_token'), $persistent_token, false);
        }
    }
    
    public function clear_tokens() {
        delete_option($this->get_option_key('access_token'));
        delete_option($this->get_option_key('refresh_token'));
    }
    
    public function is_logged_in() {
        $access_token = $this->get_access_token();
        // Un JWT ha senso solo se non scaduto (15 minuti): cosi' la chat sa che deve rinnovarlo
        return !empty($access_token) && $this->jwt_not_expired($access_token);
    }
    
    public function login($username, $password) {
        $result = $this->api_client->login($username, $password);
        if (isset($result['success']) && $result['success'] && isset($result['data']['access_token'])) {
            $refresh = isset($result['data']['refresh_token']) ? $result['data']['refresh_token'] : '';
            $this->save_tokens($result['data']['access_token'], $refresh);
            // Il token persistente (ptk_) non scade: lo salviamo per ri-autenticarci in automatico
            if (isset($result['data']['persistent_token'])) {
                $this->save_persistent_token($result['data']['persistent_token']);
            }
            return array('success' => true, 'user' => $result['data']);
        }
        $error_msg = 'Login fallito';
        if (isset($result['error'])) {
            if (is_array($result['error'])) {
                $error_msg = isset($result['error']['detail']) ? $result['error']['detail'] : json_encode($result['error']);
            } else {
                $error_msg = $result['error'];
            }
        }
        return array('success' => false, 'error' => $error_msg);
    }
    
    public function logout() {
        $refresh_token = $this->get_refresh_token();
        if ($refresh_token) {
            $this->api_client->logout($refresh_token);
        }
        $this->clear_tokens();
    }
    
    public function refresh_access_token() {
        $refresh_token = $this->get_refresh_token();
        if (!$refresh_token) {
            return array('success' => false, 'error' => 'No refresh token');
        }
        
        $result = $this->api_client->refresh_token($refresh_token);
        if (isset($result['success']) && $result['success'] && isset($result['data']['access_token'])) {
            $this->save_tokens($result['data']['access_token'], $refresh_token);
            return array('success' => true);
        }
        
        // Fallback: il token persistente (ptk_) non scade, cosi la chat non muore dopo 15 minuti
        $persistent = $this->get_persistent_token();
        if ($persistent) {
            $reauth = $this->api_client->reauth($persistent);
            if (isset($reauth['success']) && $reauth['success'] && isset($reauth['data']['access_token'])) {
                $new_refresh = isset($reauth['data']['refresh_token']) ? $reauth['data']['refresh_token'] : $refresh_token;
                $this->save_tokens($reauth['data']['access_token'], $new_refresh);
                return array('success' => true);
            }
        }
        
        $error_msg = 'Refresh fallito';
        if (isset($result['error'])) {
            $error_msg = is_string($result['error']) ? $result['error'] : json_encode($result['error']);
        }
        return array('success' => false, 'error' => $error_msg);
    }
    
    /**
     * Ottiene (o rigenera) una coppia JWT valida usando il token persistente.
     * Ritorna true se adesso c'e un access token utilizzabile.
     */
    public function ensure_authenticated() {
        $access = $this->get_access_token();
        if ($access && $this->jwt_not_expired($access)) {
            $this->api_client->set_access_token($access);
            return true;
        }
        $refresh = $this->refresh_access_token();
        if (isset($refresh['success']) && $refresh['success']) {
            return true;
        }
        return false;
    }
    
    /** Un JWT scade dopo 15 minuti: controlliamo la sua clip exp senza chiamare il backend. */
    public function jwt_not_expired($token) {
        $parts = explode('.', (string) $token);
        if (count($parts) < 2) {
            return false;
        }
        $seg = $parts[1];
        $json = '';
        // Il backend ARIA codifica i segmenti in hex (non base64url): gestiamo entrambi i formati
        if (strlen($seg) % 2 === 0 && ctype_xdigit($seg)) {
            $json = (string) @hex2bin($seg);
        }
        if ($json === '') {
            $b64 = strtr($seg, '-_', '+/');
            $b64 .= str_repeat('=', (4 - strlen($b64) % 4) % 4);
            $decoded = base64_decode($b64, true);
            $json = $decoded === false ? '' : $decoded;
        }
        $payload = json_decode($json, true);
        if (!is_array($payload) || empty($payload['exp'])) {
            return false;
        }
        return intval($payload['exp']) > time() + 5;
    }
    
    public function ensure_valid_token() {
        if (!$this->is_logged_in()) {
            return false;
        }
        
        $result = $this->api_client->health_check();
        if (!isset($result['success']) || !$result['success']) {
            $refresh = $this->refresh_access_token();
            return isset($refresh['success']) && $refresh['success'];
        }
        return true;
    }
    
    public function get_api_client() {
        $access_token = $this->get_access_token();
        if ($access_token) {
            $this->api_client->set_access_token($access_token);
        }
        return $this->api_client;
    }
}
