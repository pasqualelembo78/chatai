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
require_once ARIA_CHAT_PLUGIN_DIR . 'includes/room_seo.php';

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
        add_action('wp_login', array($aria_chat_engine, 'merge_guest_on_wp_login'), 10, 2);
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

/**
 * INDICE DELLA GRIGLIA.
 * I JSON dei personaggi pesano ~44 MB: rileggerli a ogni richiesta di una stanza
 * costerebbe ~400 ms e 62 MB di RAM. Costruiamo una sola volta un indice leggero
 * (id, nome, emoji, descrizione breve) diviso per categoria e lo validiamo con una
 * "firma" dei file: dopo una plasmatura o un nuovo file-categoria la cache si rinnova
 * da sola, senza interventi manuali.
 */
define('ARIA_GRID_CACHE_GROUP', 'aria_grid');

function aria_grid_data_dir() {
    return apply_filters('aria_chat_characters_dir', '/opt/aria/backend/characters/data');
}

function aria_grid_signature() {
    $sig = array();
    foreach ((array) glob(aria_grid_data_dir() . '/*.json') as $f) {
        $sig[] = basename($f) . ':' . filesize($f) . ':' . filemtime($f);
    }
    sort($sig);
    return implode('|', $sig);
}

function aria_grid_cache_file() {
    $u = wp_upload_dir();
    return trailingslashit($u['basedir']) . 'aria-grid/index.json';
}

function aria_grid_build_index() {
    $index = array('signature' => '', 'categories' => array(), 'characters' => array(), 'built_at' => 0);
    foreach ((array) glob(aria_grid_data_dir() . '/*.json') as $f) {
        $rows = json_decode((string) file_get_contents($f), true);
        if (!is_array($rows)) continue;
        if (basename($f) === 'categories.json') {
            foreach ($rows as $c) {
                if (empty($c['id'])) continue;
                $index['categories'][$c['id']] = array(
                    'name' => $c['name'] ?? $c['id'],
                    'icon' => $c['icon'] ?? 'F',
                    'description' => $c['description'] ?? ''
                );
            }
            continue;
        }
        foreach ($rows as $c) {
            if (!is_array($c) || empty($c['id'])) continue;
            $cat = !empty($c['category']) ? $c['category'] : 'altro';
            $desc = preg_replace('/\s+/u', ' ', strval(isset($c['description']) ? $c['description'] : (isset($c['essence']) ? $c['essence'] : '')));
            $desc = trim((string) $desc);
            $index['characters'][$cat][] = array(
                'id' => $c['id'],
                'slug' => $c['slug'] ?? '',
                'name' => isset($c['name']) ? $c['name'] : 'Personaggio',
                'avatar' => isset($c['avatar']) ? $c['avatar'] : '💬',
                'desc' => mb_substr($desc, 0, 90)
            );
        }
    }
    foreach ($index['characters'] as $cat => $list) {
        usort($index['characters'][$cat], function ($a, $b) { return strcmp($a['name'], $b['name']); });
    }
    $index['signature'] = aria_grid_signature();
    $index['built_at'] = time();
    return $index;
}

function aria_grid_index($force = false) {
    $sig = aria_grid_signature();
    if (!$force) {
        $cached = wp_cache_get('index', ARIA_GRID_CACHE_GROUP);
        if (is_array($cached) && ($cached['signature'] ?? '') === $sig) return $cached;
        $file = aria_grid_cache_file();
        if (is_readable($file)) {
            $data = json_decode((string) file_get_contents($file), true);
            if (is_array($data) && ($data['signature'] ?? '') === $sig) {
                wp_cache_set('index', $data, ARIA_GRID_CACHE_GROUP, HOUR_IN_SECONDS);
                return $data;
            }
        }
    }
    $index = aria_grid_build_index();
    $file = aria_grid_cache_file();
    if (wp_mkdir_p(dirname($file))) {
        @file_put_contents($file, json_encode($index, JSON_UNESCAPED_UNICODE));
    }
    wp_cache_set('index', $index, ARIA_GRID_CACHE_GROUP, HOUR_IN_SECONDS);
    return $index;
}

/** Card di una categoria: [['id','name','avatar','desc'], ...] */
function aria_grid_characters($cat_slug, $force = false) {
    if ($cat_slug === '') return array();
    $index = aria_grid_index($force);
    return isset($index['characters'][$cat_slug]) ? $index['characters'][$cat_slug] : array();
}

/** Nome/emoji/descrizione di una categoria (da categories.json). */
function aria_grid_category_meta($cat_slug) {
    $index = aria_grid_index();
    if (isset($index['categories'][$cat_slug])) return $index['categories'][$cat_slug];
    return array('name' => ucwords(str_replace('-', ' ', $cat_slug)), 'icon' => '💬', 'description' => '');
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


/* ───────── Pagine personaggio: /stanza/<categoria>/<slug>/ ───────── */

function aria_char_data_file($categoria) {
    $f = aria_grid_data_dir() . '/' . sanitize_title($categoria) . '.json';
    return is_readable($f) ? $f : '';
}

/** Personaggio dal suo slug dentro la categoria. */
function aria_char_list($categoria) {
    static $cache = array();
    $categoria = sanitize_title($categoria);
    if (isset($cache[$categoria])) {
        return $cache[$categoria];
    }
    $file = aria_char_data_file($categoria);
    $righe = array();
    if ($file) {
        $lette = json_decode((string) file_get_contents($file), true);
        if (is_array($lette)) {
            $righe = $lette;
        }
    }
    $cache[$categoria] = $righe;
    return $righe;
}

function aria_char_by_slug($categoria, $slug) {
    foreach (aria_char_list($categoria) as $c) {
        if (!empty($c['slug']) && $c['slug'] === $slug) {
            return $c;
        }
    }
    return null;
}

/** Personaggio dal suo id dentro la categoria (per i vecchi link ?char=). */
function aria_char_by_id($categoria, $id) {
    foreach (aria_char_list($categoria) as $c) {
        if (!empty($c['id']) && $c['id'] === $id) {
            return $c;
        }
    }
    return null;
}

/** Altri personaggi della stanza che hanno una pagina propria. */
function aria_characters_with_slug($categoria, $escludi = '', $quanti = 6) {
    $out = array();
    foreach (aria_char_list($categoria) as $c) {
        if (empty($c['slug']) || $c['id'] === $escludi) {
            continue;
        }
        $out[] = array('slug' => $c['slug'], 'name' => $c['name'] ?? '');
        if (count($out) >= $quanti) {
            break;
        }
    }
    return $out;
}

function aria_rewrite_personaggi() {
    add_rewrite_rule('^stanza/([^/]+)/([^/]+)/?$', 'index.php?stanza=$matches[1]&personaggio=$matches[2]', 'top');
}
add_action('init', 'aria_rewrite_personaggi', 5);

function aria_query_vars_personaggi($vars) {
    $vars[] = 'personaggio';
    return $vars;
}
add_filter('query_vars', 'aria_query_vars_personaggi');

/** Le regole vanno rigenerate una volta dopo l'introduzione degli slug. */
function aria_maybe_flush_rules() {
    if (get_option('aria_char_routes') !== ARIA_CHAT_VERSION) {
        flush_rewrite_rules(false);
        update_option('aria_char_routes', ARIA_CHAT_VERSION, false);
    }
}
add_action('wp_loaded', 'aria_maybe_flush_rules');

/** ?char= senza slug resta com'è; con slug si va alla pagina dedicata (301). */
function aria_redirect_char_to_page() {
    if (!is_singular('stanza') || get_query_var('personaggio') || empty($_GET['char'])) {
        return;
    }
    $categoria = get_post_field('post_name', get_queried_object_id());
    $c = aria_char_by_id($categoria, sanitize_text_field(wp_unslash($_GET['char'])));
    if ($c && !empty($c['slug'])) {
        wp_safe_redirect(trailingslashit(get_permalink()) . $c['slug'] . '/', 301);
        exit;
    }
}
add_action('template_redirect', 'aria_redirect_char_to_page');

/** Titolo, description, canonical e OG della pagina personaggio. */
function aria_char_seo_attivo() {
    return (bool) get_query_var('personaggio');
}

function aria_char_current() {
    static $c = null;
    if ($c !== null) {
        return $c;
    }
    $c = false;
    $slug = get_query_var('personaggio');
    if ($slug && is_singular('stanza')) {
        $cat = get_post_field('post_name', get_queried_object_id());
        $c = aria_char_by_slug($cat, sanitize_title($slug)) ?: false;
    }
    return $c;
}

function aria_char_title($titolo) {
    $c = aria_char_current();
    if (!$c || !is_singular('stanza')) {
        return $titolo;
    }
    $stanza = get_queried_object();
    $cat = aria_grid_category_meta(get_post_field('post_name', $stanza->ID));
    $mestiere = !empty($c['job']) ? ' (' . $c['job'] . ')' : '';
    return 'Chat con ' . $c['name'] . $mestiere . ' — ' . $cat['name'] . ' | Pornovirtuale';
}
add_filter('pre_get_document_title', 'aria_char_title', 20);
add_filter('wpseo_title', 'aria_char_title', 20);

function aria_char_desc($desc) {
    $c = aria_char_current();
    if (!$c) {
        return $desc;
    }
    $cat = aria_grid_category_meta(get_post_field('post_name', get_queried_object_id()));
    $pezzo = trim(wp_strip_all_tags((string) ($c['essence'] ?? '')));
    if (!$pezzo) {
        $pezzo = $c['name'] . ' ti aspetta nella stanza ' . $cat['name'] . '.';
    }
    return mb_substr($pezzo, 0, 150) . ' Chatta gratis: 4 messaggi senza registrarti.';
}
add_filter('wpseo_metadesc', 'aria_char_desc', 20);

function aria_char_canonical($url) {
    $c = aria_char_current();
    if (!$c) {
        return $url;
    }
    return trailingslashit(get_permalink()) . $c['slug'] . '/';
}
add_filter('wpseo_canonical', 'aria_char_canonical', 20);

function aria_char_og($titolo) {
    $c = aria_char_current();
    if (!$c) {
        return $titolo;
    }
    return 'Chat con ' . $c['name'];
}
add_filter('wpseo_opengraph_title', 'aria_char_og', 20);

/** Sitemap delle pagine personaggio, una per categoria. */
function aria_char_sitemap() {
    if (!isset($_GET['aria_char_sitemap'])) {
        return;
    }
    $solo = sanitize_title((string) $_GET['aria_char_sitemap']);
    header('Content-Type: application/xml; charset=utf-8');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n" . '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach (aria_grid_character_slugs($solo) as $voce) {
        echo '  <url><loc>' . esc_url($voce['url']) . '</loc><lastmod>' . esc_html($voce['data']) . '</lastmod></url>' . "\n";
    }
    echo '</urlset>';
    exit;
}
add_action('template_redirect', 'aria_char_sitemap', 1);

/** Elenco URL delle pagine personaggio (per la sitemap). */
function aria_grid_character_slugs($solo = '') {
    $urls = array();
    foreach ((array) glob(aria_grid_data_dir() . '/*.json') as $f) {
        if (basename($f) === 'categories.json') {
            continue;
        }
        $cat = basename($f, '.json');
        if ($solo && $solo !== '1' && $solo !== $cat) {
            continue;
        }
        $righe = json_decode((string) file_get_contents($f), true) ?: array();
        foreach ($righe as $c) {
            if (empty($c['slug'])) {
                continue;
            }
            $urls[] = array(
                'url'  => home_url('/stanza/' . $cat . '/' . $c['slug'] . '/'),
                'data' => gmdate('Y-m-d', filemtime($f)),
            );
        }
    }
    return $urls;
}

function aria_char_sitemap_index($index) {
    foreach (aria_room_seo_data() as $cat => $null) {
        if (!file_exists(aria_char_data_file($cat))) {
            continue;
        }
        $index .= '<sitemap><loc>' . esc_url(home_url('/?aria_char_sitemap=' . $cat)) . '</loc><lastmod>' . gmdate('c') . '</lastmod></sitemap>' . "\n";
    }
    return $index;
}
add_filter('wpseo_sitemap_index', 'aria_char_sitemap_index', 20);

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
