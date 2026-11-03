<?php
/**
 * API Client per backend ARIA
 */

if (!defined('ABSPATH')) exit;

class Aria_API_Client {
    
    private $base_url;
    private $access_token;
    
    /** URL base del backend (serve a Chat_Engine per lo streaming SSE). */
    public function get_base_url() {
        return $this->base_url;
    }

    public function __construct($base_url = null) {
        $this->base_url = $base_url ? $base_url : get_option('aria_chat_backend_url', 'http://82.165.218.56:5000');
        $this->access_token = null;
    }
    
    /** Token impostato (serve ai proxy SSE che costruiscono l'header a mano). */
    public function get_access_token() {
        return $this->access_token;
    }

    public function set_access_token($token) {
        $this->access_token = $token;
    }
    
    private function get_headers($needs_auth = true) {
        $headers = array(
            'Content-Type' => 'application/json',
            'Accept' => 'application/json'
        );
        if ($needs_auth && $this->access_token) {
            $headers['Authorization'] = 'Bearer ' . $this->access_token;
        }
        return $headers;
    }
    
    private function request($endpoint, $method = 'GET', $body = null, $needs_auth = true) {
        $url = rtrim($this->base_url, '/') . $endpoint;
        $args = array(
            'method' => $method,
            'headers' => $this->get_headers($needs_auth),
            'timeout' => 240,
            'sslverify' => false
        );
        
        if ($body) {
            $args['body'] = is_string($body) ? $body : json_encode($body);
        }
        
        $response = wp_remote_request($url, $args);
        
        if (is_wp_error($response)) {
            return array('success' => false, 'error' => $response->get_error_message());
        }
        
        $code = wp_remote_retrieve_response_code($response);
        $body_response = wp_remote_retrieve_body($response);
        
        if ($code >= 200 && $code < 300) {
            $decoded = json_decode($body_response, true);
            return array('success' => true, 'data' => $decoded !== null ? $decoded : $body_response);
        } else {
            return array('success' => false, 'error' => $body_response, 'code' => $code);
        }
    }
    
    public function health_check() {
        return $this->request('/');
    }
    
    public function get_categories($adult = false) {
        $endpoint = '/categories?' . http_build_query(array('adult' => $adult ? 'true' : 'false'));
        return $this->request($endpoint);
    }
    
    public function get_characters($category = null, $limit = 50, $offset = 0) {
        $params = array('limit' => $limit, 'offset' => $offset);
        if ($category) {
            $params['category'] = $category;
        }
        $endpoint = '/characters?' . http_build_query($params);
        return $this->request($endpoint);
    }
    
    public function search_characters($query, $category = null) {
        $params = array('q' => $query);
        if ($category) {
            $params['category'] = $category;
        }
        $endpoint = '/characters/search?' . http_build_query($params);
        return $this->request($endpoint);
    }
    
    public function get_character($character_id) {
        return $this->request('/characters/' . urlencode($character_id));
    }
    
    public function verify_age($birth_year) {
        return $this->request('/me/verify-age', 'POST', array('birth_year' => intval($birth_year)));
    }
    
    public function get_providers() {
        return $this->request('/providers');
    }
    
    public function get_available_models() {
        return $this->request('/available-models');
    }
    
    public function register($username, $email, $password, $birth_date, $referral_code = '') {
        return $this->request('/auth/register', 'POST', array(
            'username' => $username,
            'email' => $email,
            'password' => $password,
            'birth_date' => $birth_date,
            'referral_code' => $referral_code
        ), false);
    }
    
    /** Unisce la cronologia della prova all'account vero. */
    public function merge_guest($guest_user_id) {
        return $this->request('/auth/me/merge-guest', 'POST', array('guest_user_id' => $guest_user_id));
    }

    public function login($username, $password) {
        return $this->request('/auth/login', 'POST', array(
            'username' => $username,
            'password' => $password
        ), false);
    }
    
    public function refresh_token($refresh_token) {
        return $this->request('/auth/refresh', 'POST', array('refresh_token' => $refresh_token), false);
    }
    
    /**
     * Scambia il token persistente (ptk_..., senza scadenza) con una coppia JWT fresca.
     * Usato per ri-autenticare in modo trasparente quando il JWT scade.
     */
    public function reauth($persistent_token) {
        return $this->request('/auth/reauth', 'POST', array('persistent_token' => $persistent_token), false);
    }
    
    public function logout($refresh_token) {
        return $this->request('/auth/logout', 'POST', array('refresh_token' => $refresh_token));
    }
    
    public function chat($character_id, $text, $username, $memory_context = array()) {
        return $this->request('/chat', 'POST', array(
            'character' => $character_id,
            'text' => $text,
            'username' => $username,
            'memory_context' => $memory_context
        ));
    }
    
    public function get_config() {
        return $this->request('/config');
    }
    
    public function set_config($provider, $model) {
        return $this->request('/config', 'POST', array('provider' => $provider, 'model' => $model));
    }
    
    public function get_memory() {
        return $this->request('/memory');
    }
    
    public function update_memory($memory_data) {
        return $this->request('/memory', 'POST', $memory_data);
    }
}
