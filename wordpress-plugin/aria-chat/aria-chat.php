<?php
/**
 * Plugin Name: Aria Chat AI
 * Plugin URI: https://www.mevacoin.com
 * Description: Chat AI con personaggi virtuali. Si collega al backend ARIA per conversazioni intelligenti.
 * Version: 1.0.0
 * Author: IntelliGame
 * Author URI: https://www.mevacoin.com
 * License: GPL v2 or later
 * Text Domain: aria-chat
 */

if (!defined('ABSPATH')) exit;

define('ARIA_CHAT_VERSION', '1.0.0');
define('ARIA_CHAT_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ARIA_CHAT_PLUGIN_URL', plugin_dir_url(__FILE__));
define('ARIA_CHAT_BACKEND_URL', get_option('aria_chat_backend_url', 'http://82.165.218.56:5000'));

require_once ARIA_CHAT_PLUGIN_DIR . 'includes/API_Client.php';
require_once ARIA_CHAT_PLUGIN_DIR . 'includes/Auth_Manager.php';
require_once ARIA_CHAT_PLUGIN_DIR . 'includes/Chat_Engine.php';

function aria_chat_init() {
    add_action('wp_enqueue_scripts', 'aria_chat_enqueue_assets');
    add_shortcode('aria_chat', 'aria_chat_shortcode');
    add_action('admin_menu', 'aria_chat_admin_menu');
    add_action('admin_init', 'aria_chat_register_settings');
}
add_action('plugins_loaded', 'aria_chat_init');

function aria_chat_enqueue_assets() {
    wp_enqueue_style(
        'aria-chat-css',
        ARIA_CHAT_PLUGIN_URL . 'assets/css/aria-chat.css',
        array(),
        ARIA_CHAT_VERSION
    );
    wp_enqueue_script(
        'aria-chat-js',
        ARIA_CHAT_PLUGIN_URL . 'assets/js/aria-chat.js',
        array('jquery'),
        ARIA_CHAT_VERSION,
        true
    );
    wp_localize_script('aria-chat-js', 'ariaChatConfig', array(
        'backendUrl' => ARIA_CHAT_BACKEND_URL,
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce' => wp_create_nonce('aria_chat_nonce'),
        'userId' => get_current_user_id(),
        'username' => wp_get_current_user().user_login
    ));
}

function aria_chat_shortcode($atts) {
    $atts = shortcode_atts(array(
        'character' => '',
        'width' => '100%',
        'height' => '500px'
    ), $atts);
    
    ob_start();
    include ARIA_CHAT_PLUGIN_DIR . 'templates/chat-box.php';
    return ob_get_clean();
}

function aria_chat_admin_menu() {
    add_options_page(
        'Aria Chat Settings',
        'Aria Chat',
        'manage_options',
        'aria-chat',
        'aria_chat_settings_page'
    );
}

function aria_chat_register_settings() {
    register_setting('aria_chat_settings', 'aria_chat_backend_url');
    add_settings_section('aria_chat_main', 'Configurazione Backend', null, 'aria-chat');
    add_settings_field('backend_url', 'URL Backend ARIA', 'aria_chat_backend_url_field', 'aria-chat', 'aria_chat_main');
}

function aria_chat_backend_url_field() {
    $url = get_option('aria_chat_backend_url', 'http://82.165.218.56:5000');
    echo '<input type="url" name="aria_chat_backend_url" value="' . esc_attr($url) . '" class="regular-text" />';
    echo '<p class="description">URL del backend ARIA (es. http://localhost:5000 o http://82.165.218.56:5000)</p>';
}

function aria_chat_settings_page() {
    ?>
    <div class="wrap">
        <h1>Impostazioni Aria Chat</h1>
        <form method="post" action="options.php">
            <?php settings_fields('aria_chat_settings'); ?>
            <?php do_settings_sections('aria-chat'); ?>
            <?php submit_button(); ?>
        </form>
    </div>
    <?php
}
