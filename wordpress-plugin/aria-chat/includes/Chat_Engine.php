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
        add_action('wp_ajax_aria_chat_logout', array($this, 'ajax_logout'));
        add_action('wp_ajax_aria_chat_send', array($this, 'ajax_send_message'));
        add_action('wp_ajax_aria_chat_characters', array($this, 'ajax_get_characters'));
        add_action('wp_ajax_aria_chat_categories', array($this, 'ajax_get_categories'));
        add_action('wp_ajax_aria_chat_auth_status', array($this, 'ajax_auth_status'));
        add_action('wp_ajax_aria_chat_get_config', array($this, 'ajax_get_config'));
        add_action('wp_ajax_aria_chat_set_config', array($this, 'ajax_set_config'));
    }
    
    private function send_json($data) {
        wp_send_json($data);
    }
    
    public function ajax_login() {
        $username = sanitize_text_field($_POST['username'] ?? '');
        $password = $_POST['password'] ?? '';
        
        if (!$username || !$password) {
            $this->send_json(array('success' => false, 'error' => 'Username e password richiesti'));
        }
        
        $result = $this->auth_manager->login($username, $password);
        $this->send_json($result);
    }
    
    public function ajax_logout() {
        $this->auth_manager->logout();
        $this->send_json(array('success' => true));
    }
    
    public function ajax_send_message() {
        check_ajax_referer('aria_chat_nonce', 'nonce');
        
        $character_id = sanitize_text_field($_POST['character'] ?? '');
        $text = sanitize_textarea_field($_POST['text'] ?? '');
        $username = sanitize_text_field($_POST['username'] ?? wp_get_current_user().user_login);
        
        if (!$character_id || !$text) {
            $this->send_json(array('success' => false, 'error' => 'Personaggio e messaggio richiesti'));
        }
        
        if (!$this->auth_manager->ensure_valid_token()) {
            $this->send_json(array('success' => false, 'error' => 'Non autenticato. Effettua il login.'));
        }
        
        $result = $this->api_client->chat($character_id, $text, $username);
        $this->send_json($result);
    }
    
    public function ajax_get_characters() {
        $category = sanitize_text_field($_POST['category'] ?? null);
        $limit = intval($_POST['limit'] ?? 50);
        $offset = intval($_POST['offset'] ?? 0);
        
        $result = $this->api_client->get_characters($category, $limit, $offset);
        $this->send_json($result);
    }
    
    public function ajax_get_categories() {
        $adult = isset($_POST['adult']) && $_POST['adult'] === 'true';
        $result = $this->api_client->get_categories($adult);
        $this->send_json($result);
    }
    
    public function ajax_auth_status() {
        $this->send_json(array(
            'isLoggedIn' => $this->auth_manager->is_logged_in(),
            'userId' => get_current_user_id(),
            'username' => wp_get_current_user().user_login
        ));
    }
    
    public function ajax_get_config() {
        if (!$this->auth_manager->ensure_valid_token()) {
            $this->send_json(array('success' => false, 'error' => 'Non autenticato'));
        }
        $result = $this->api_client->get_config();
        $this->send_json($result);
    }
    
    public function ajax_set_config() {
        check_ajax_referer('aria_chat_nonce', 'nonce');
        
        if (!$this->auth_manager->ensure_valid_token()) {
            $this->send_json(array('success' => false, 'error' => 'Non autenticato'));
        }
        
        $provider = sanitize_text_field($_POST['provider'] ?? '');
        $model = sanitize_text_field($_POST['model'] ?? '');
        
        $result = $this->api_client->set_config($provider, $model);
        $this->send_json($result);
    }
}

$aria_chat_engine = new Aria_Chat_Engine();
$aria_chat_engine->init_ajax();
