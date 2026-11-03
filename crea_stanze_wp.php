<?php
/**
 * Script per creare automaticamente le 24 stanze WordPress (CPT "stanza")
 * del plugin Aria Chat, una per categoria tematica.
 *
 * Ogni stanza contiene lo shortcode [aria_chat category="slug-categoria"]
 * così che gli utenti vedano esclusivamente i personaggi assegnati a quella categoria.
 *
 * Modalità d'uso:
 * 1. Carica questo file nella cartella mu-plugin di WordPress:
 *    /var/www/pornovirtuale/wp-content/mu-plugins/aria-stanze-setup.php
 *  Oppure includilo nel functions.php del tema attivo.
 * 2. Visita qualsiasi pagina del sito: le stanze vengono create automaticamente (una tantum).
 * 3. Rimuovi il file dopo l'esecuzione (o lascia il controllo $already_done per evitare duplicati).
 */

if (!defined('ABSPATH')) {
    die('Accesso diretto non consentito.');
}

// ─── Le 24 categorie con slug e titolo ────────────────────────────────────────
$stanze = array(
    array('slug' => 'amanti-segreti',      'title' => 'Amanti Segreti'),
    array('slug' => 'bdsm',                'title' => 'BDSM'),
    array('slug' => 'bisex',               'title' => 'Bisex'),
    array('slug' => 'camera-privata',      'title' => 'Camera Privata'),
    array('slug' => 'chat-romantica',      'title' => 'Chat Romantica'),
    array('slug' => 'dirty-talk',          'title' => 'Dirty Talk'),
    array('slug' => 'dominazione',         'title' => 'Dominazione'),
    array('slug' => 'fantasie-erotiche',   'title' => 'Fantasie Erotiche'),
    array('slug' => 'fantasie-proibite',   'title' => 'Fantasie Proibite'),
    array('slug' => 'feticismi',           'title' => 'Feticismi'),
    array('slug' => 'gay',                 'title' => 'Gay'),
    array('slug' => 'incontri-bollenti',   'title' => 'Incontri Bollenti'),
    array('slug' => 'lesbo',               'title' => 'Lesbo'),
    array('slug' => 'masturbazione',       'title' => 'Masturbazione'),
    array('slug' => 'mature',              'title' => 'Mature'),
    array('slug' => 'milf',                'title' => 'MILF'),
    array('slug' => 'roleplay-erotico',    'title' => 'Roleplay Erotico'),
    array('slug' => 'scambio-di-coppia',   'title' => 'Scambio di Coppia'),
    array('slug' => 'senza-tabu',          'title' => 'Senza Tabù'),
    array('slug' => 'sesso-orale',         'title' => 'Sesso Orale'),
    array('slug' => 'sesso-virtuale',      'title' => 'Sesso Virtuale'),
    array('slug' => 'sottomissione',       'title' => 'Sottomissione'),
    array('slug' => 'threesome',           'title' => 'Threesome'),
    array('slug' => 'voyeurismo',          'title' => 'Voyeurismo'),
);

function aria_stanze_create_if_missing($title, $slug_cat) {
    global $wpdb;

    // Controlla se esiste già una stanza con questo titolo
    $existing = get_page_by_title($title, OBJECT, 'stanza');
    if ($existing) {
        return false; // già esistente
    }

    $shortcode = sprintf('[aria_chat category="%s"]', $slug_cat);

    $post_id = wp_insert_post(array(
        'post_title'   => $title,
        'post_content' => $shortcode,
        'post_status'  => 'publish',
        'post_type'    => 'stanza',
        'post_author'  => 1, // admin
        'post_excerpt' => 'Stanza chat dedicata alla categoria: ' . $title,
    ));

    if ($post_id && !is_wp_error($post_id)) {
        return true;
    }
    return false;
}

// Hook: esegue all'init di WordPress (solo se l'utente è admin, per sicurezza)
add_action('admin_init', function () use ($stanze) {
    if (!current_user_can('manage_options')) {
        return;
    }

    static $already_done = false;
    if ($already_done) {
        return;
    }
    $already_done = true;

    $creates = 0;
    $skips = 0;

    foreach ($stanze as $stanza) {
        $created = aria_stanze_create_if_missing($stanza['title'], $stanza['slug']);
        if ($created) {
            $creates++;
        } else {
            $skips++;
        }
    }

    // Messaggio di conferma visibile nell'admin (una tantum)
    add_action('admin_notices', function () use ($creates, $skips) {
        echo '<div class="notice notice-success is-dismissible"><p>';
        echo sprintf(
            'Aria Chat Stanze: %d stanze create, %d già esistenti (saltate).',
            intval($creates),
            intval($skips)
        );
        echo '</p></div>';
    });
});

echo 'Script aria-stanze-setup.php caricato. Le 24 stanze verranno create al prossimo caricamento admin.' . "\n";
