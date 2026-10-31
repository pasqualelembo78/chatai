<?php
/**
 * Auth Manager - Gestione JWT e sessioni utente
 */

if (!defined('ABSPATH')) exit;

class Aria_Auth_Manager {
    
    private $api_client;
    private $user_id;
    
    public function __construct($user_id = null) {
        $this->user_id = $user_id ?: get_current_user_id();
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
    
    public function clear_tokens() {
        delete_option($this->get_option_key('access_token'));
        delete_option($this->get_option_key('refresh_token'));
    }
    
    public function is_logged_in() {
        $access_token = $this->get_access_token();
        $refresh_token = $this->get_refresh_token();
        return !empty($access_token) && !empty($refresh_token);
    }
    
    public function login($username, $password) {
        $result = $this->api_client->login($username, $password);
        if ($result['success'] && isset($result['data']['access_token'])) {
            $this->save_tokens($result['data']['access_token'], $result['data']['refresh_token']);
            return array('success' => true, 'user' => $result['data']);
        }
        return array('success' => false, 'error' => $result['error'] ?? 'Login fallito');
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
        if ($result['success'] && isset($result['data']['access_token'])) {
            $this->save_tokens($result['data']['access_token'], $refresh_token);
            return array('success' => true);
        }
        return array('success' => false, 'error' => $result['error'] ?? 'Refresh fallito');
    }
    
    public function ensure_valid_token() {
        if (!$this->is_logged_in()) {
            return false;
        }
        
        $result = $this->api_client->health_check();
        if (!$result['success']) {
            $refresh = $this->refresh_access_token();
            return $refresh['success'];
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
