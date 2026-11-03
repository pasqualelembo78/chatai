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

function aria_chat_get_backend_url() {
    $url = get_option('aria_chat_backend_url', 'http://82.165.218.56:5000');
    if (empty($url)) {
        $url = 'http://82.165.218.56:5000';
    }
    return $url;
}

/**
 * Registra il Custom Post Type "stanza" per le stanze chat dedicate
 */
function aria_chat_register_stanza_cpt() {
    $labels = array(
        'name'                  => _x('Stanze', 'post type general name', 'aria-chat'),
        'singular_name'         => _x('Stanza', 'post type singular name', 'aria-chat'),
        'add_new'               => _x('Aggiungi Stanza', 'aria-chat'),
        'add_new_item'          => __('Aggiungi Nuova Stanza', 'aria-chat'),
        'edit_item'             => __('Modifica Stanza', 'aria-chat'),
        'new_item'              => __('Nuova Stanza', 'aria-chat'),
        'view_item'             => __('Visualizza Stanza', 'aria-chat'),
        'search_items'          => __('Cerca Stanze', 'aria-chat'),
        'not_found'             => __('Nessuna stanza trovata', 'aria-chat'),
        'not_found_in_trash'    => __('Nessuna stanza trovata nel cestino', 'aria-chat'),
        'menu_name'             => __('Stanze Chat', 'aria-chat'),
    );
    $args = array(
        'labels'                => $labels,
        'public'                => true,
        'publicly_queryable'    => true,
        'show_ui'               => true,
        'show_in_menu'          => true,
        'query_var'             => true,
        'rewrite'               => array('slug' => 'stanza'),
        'capability_type'       => 'post',
        'has_archive'           => true,
        'hierarchical'          => false,
        'menu_position'         => 25,
        'menu_icon'             => 'dashicons-format-chat',
        'supports'              => array('title', 'editor', 'thumbnail', 'custom-fields'),
    );
    register_post_type('stanza', $args);
}
add_action('init', 'aria_chat_register_stanza_cpt');

require_once ARIA_CHAT_PLUGIN_DIR . 'includes/API_Client.php';
require_once ARIA_CHAT_PLUGIN_DIR . 'includes/Auth_Manager.php';
require_once ARIA_CHAT_PLUGIN_DIR . 'includes/Chat_Engine.php';

function aria_chat_init() {
    add_action('wp_enqueue_scripts', 'aria_chat_enqueue_assets');
    add_shortcode('aria_chat', 'aria_chat_shortcode');
add_shortcode('aria_grid', 'aria_chat_shortcode_grid');
    add_action('admin_menu', 'aria_chat_admin_menu');
    add_action('admin_init', 'aria_chat_register_settings');
    
    // Init AJAX handlers
    if (class_exists('Aria_Chat_Engine')) {
        $aria_chat_engine = new Aria_Chat_Engine();
        $aria_chat_engine->init_ajax();
    }
}
add_action('plugins_loaded', 'aria_chat_init');

function aria_chat_asset_version($rel_path) {
    $file = ARIA_CHAT_PLUGIN_DIR . $rel_path;
    return file_exists($file) ? filemtime($file) : ARIA_CHAT_VERSION;
}

function aria_chat_enqueue_assets() {
    wp_enqueue_style(
        'aria-chat-css',
        ARIA_CHAT_PLUGIN_URL . 'assets/css/aria-chat.css',
        array(),
        aria_chat_asset_version('assets/css/aria-chat.css')
    );
    wp_enqueue_script(
        'aria-chat-js',
        ARIA_CHAT_PLUGIN_URL . 'assets/js/aria-chat.js',
        array('jquery'),
        aria_chat_asset_version('assets/js/aria-chat.js'),
        true
    );
    
    $current_user = wp_get_current_user();
    $username = ($current_user && $current_user->exists()) ? ($current_user->user_login ? $current_user->user_login : $current_user->display_name) : 'Ospite';
    $nickname = ($current_user && $current_user->exists()) ? ($current_user->nickname ? $current_user->nickname : ($current_user->display_name ? $current_user->display_name : $current_user->user_login)) : 'Ospite';
    
    // Parametri shortcode/URL per stanze dedicate
    $preset_char = isset($_GET['char']) ? sanitize_text_field(wp_unslash($_GET['char'])) : '';
    if (!$preset_char && isset($_GET['character'])) {
        $preset_char = sanitize_text_field(wp_unslash($_GET['character']));
    }
    $shortcode_character = $preset_char;
    $shortcode_category = isset($_GET['category']) ? sanitize_text_field(wp_unslash($_GET['category'])) : '';
    $shortcode_mode = '';
    
    // Anno di nascita salvato (per la verifica eta' lato backend, necessaria con personaggi 18+)
    $uid = get_current_user_id();
    $stored_birth = get_option('aria_chat_' . $uid . '_birth_date', '');
    $birth_year = 0;
    if (preg_match('/^(\d{4})/', (string) $stored_birth, $m)) {
        $birth_year = intval($m[1]);
    }
    
    wp_localize_script('aria-chat-js', 'ariaChatConfig', array(
        'backendUrl' => aria_chat_get_backend_url(),
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce' => wp_create_nonce('aria_chat_nonce'),
        'userId' => get_current_user_id(),
        'username' => $username,
        'nickname' => $nickname,
        'birthYear' => $birth_year,
        'userLoggedIn' => is_user_logged_in() ? 1 : 0,
        'character' => $shortcode_character,
        'category' => $shortcode_category,
        'mode' => $shortcode_mode
    ));
}

function aria_chat_shortcode($atts) {
    // Leggi carattere preimpostato da URL (?char=... o ?character=...)
    $preset = sanitize_text_field($_GET['char'] ?? ($_GET['character'] ?? ''));
    $atts = shortcode_atts(array(
        'character' => $preset,
        'category' => '',
        'width' => '100%',
        'height' => '500px'
    ), $atts);
    
    ob_start();
    include ARIA_CHAT_PLUGIN_DIR . 'templates/chat-box.php';
    return ob_get_clean();
}

function aria_chat_shortcode_grid($atts) {
    $atts = shortcode_atts(array(
        'category' => '',
        'width' => '100%',
        'height' => 'auto'
    ), $atts);
    ob_start();
    include ARIA_CHAT_PLUGIN_DIR . 'templates/character-grid.php';
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
    register_setting('aria_chat_settings', 'aria_chat_admin_persistent_token', array(
        'type' => 'string',
        'sanitize_callback' => 'sanitize_text_field',
        'default' => ''
    ));
    add_settings_section('aria_chat_main', 'Configurazione Backend', null, 'aria-chat');
    add_settings_field('backend_url', 'URL Backend ARIA', 'aria_chat_backend_url_field', 'aria-chat', 'aria_chat_main');
    add_settings_field('admin_ptoken', 'Token persistente ARIA (admin)', 'aria_chat_admin_token_field', 'aria-chat', 'aria_chat_main');
}

/**
 * Token ptk_... (senza scadenza) usato SOLO per l'amministratore quando la sessione
 * ARIA scade e il refresh non basta piu': evita il messaggio "Sessione scaduta".
 * Gli altri utenti continuano a usare il proprio token, salvato al loro login.
 */
function aria_chat_admin_token_field() {
    $token = trim((string) get_option('aria_chat_admin_persistent_token', ''));
    $masked = $token ? (substr($token, 0, 8) . '...' . '(salvato)') : 'nessuno';
    echo '<input type="text" name="aria_chat_admin_persistent_token" value="' . esc_attr($token) . '" class="regular-text" placeholder="ptk_..." />';
    echo '<p class="description">Il backend firma JWT da 15 minuti: con questo token il plugin rinnova la sessione da solo. Attuale: ' . esc_html($masked) . '</p>';
}

function aria_chat_backend_url_field() {
    $url = aria_chat_get_backend_url();
    echo '<input type="url" name="aria_chat_backend_url" value="' . esc_attr($url) . '" class="regular-text" />';
    echo '<p class="description">URL del backend ARIA (es. http://82.165.218.56:5000)</p>';
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
