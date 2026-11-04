<?php
/**
 * Griglia card dei personaggi di una stanza (categoria).
 * I dati arrivano da aria_grid_characters(): indice in cache (Redis/file), non
 * una rilettura dei 44 MB di JSON del personaggio a ogni pagina.
 * Il clic su una card apre la chat dedicata di quel personaggio (?char=id).
 */
$atts = shortcode_atts(array('category' => ''), $atts);
$cat_slug = sanitize_text_field($atts['category']);

// Personaggio selezionato via URL (?char=... oppure ?character=...)
$selected_char = isset($_GET['char']) ? sanitize_text_field(wp_unslash($_GET['char'])) : '';
if ($selected_char === '' && isset($_GET['character'])) {
    $selected_char = sanitize_text_field(wp_unslash($_GET['character']));
}

$cat_meta = aria_grid_category_meta($cat_slug);
$chars = aria_grid_characters($cat_slug);
$total_chars = count($chars);
$room_url = get_permalink();
?>

<?php $seo_stanza = aria_room_seo($cat_slug); ?>
<?php if (!empty($seo_stanza['intro'])): ?>
<div class="aria-room-intro">
    <?php
    foreach (preg_split('/\n\n/', $seo_stanza['intro']) as $paragrafo) {
        echo '<p>' . esc_html($paragrafo) . '</p>';
    }
    ?>
</div>
<?php endif; ?>

<?php if (!is_user_logged_in()): ?>
<div class="aria-grid-gate aria-grid-gate--prova">
    <h3>Provala gratis, senza registrarti</h3>
    <p>Hai <strong>4 messaggi gratis</strong> in ogni stanza: apri un personaggio e scrivi. Poi, se ti piace, accedi per continuare.</p>
    <p>
        <a class="button button-primary" href="<?php echo esc_url(wp_login_url(get_permalink())); ?>">Accedi</a>
        <a class="button" href="<?php echo esc_url(wp_registration_url()); ?>">Registrati</a>
    </p>
    <p class="aria-grid-gate-note">Bastano un nome utente e una password. La prova resta legata al browser.</p>
</div>
<?php endif; ?>

<div class="aria-grid-wrapper" id="aria-grid-wrapper">
    <header class="aria-grid-header">
        <span class="aria-grid-icon"><?php echo esc_html($cat_meta['icon']); ?></span>
        <h2><?php echo esc_html($cat_meta['name']); ?></h2>
        <?php if (!empty($cat_meta['description'])): ?>
            <p class="aria-grid-subtitle"><?php echo esc_html($cat_meta['description']); ?></p>
        <?php endif; ?>
        <p class="aria-grid-count"><?php echo esc_html(number_format_i18n($total_chars)); ?> personaggi in questa stanza</p>
    </header>

    <?php
    // Con 200+ personaggi per stanza il DOM completo e' pesante su mobile: si mostrano
    // 60 card per volta e il resto si svela a blocchi con il pulsante.
    $per_blocco = 60;
    ?>
    <?php if ($total_chars === 0): ?>
        <p class="aria-grid-empty">Nessun personaggio trovato per questa categoria<?php echo $cat_slug ? ': ' . esc_html($cat_slug) : ' (shortcode senza category)'; ?>.</p>
    <?php else: ?>
        <div class="aria-character-grid">
            <?php foreach (array_slice($chars, 0, $per_blocco) as $i => $c):
                // La descrizione inizia con il nome: nella card il nome è già sopra
                $card_desc = trim(preg_replace('/^' . preg_quote($c['name'], '/') . '\s*[—–-]\s*/u', '', $c['desc']));
                $link_card = !empty($c['slug'])
                    ? trailingslashit($room_url) . $c['slug'] . '/'
                    : add_query_arg('char', rawurlencode($c['id']), $room_url);
            ?>
            <a class="aria-character-card" href="<?php echo esc_url($link_card); ?>" title="Chatta con <?php echo esc_attr($c['name']); ?>">
                <div class="aria-character-avatar"><?php echo esc_html($c['avatar']); ?></div>
                <h3><?php echo esc_html($c['name']); ?></h3>
                <p><?php echo esc_html($card_desc); ?></p>
            </a>
            <?php endforeach; ?>
        </div>
        <?php if ($total_chars > $per_blocco): ?>
            <div class="aria-grid-more">
                <button type="button" id="aria-show-more" class="aria-show-more" data-step="<?php echo (int) $per_blocco; ?>" data-total="<?php echo (int) $total_chars; ?>" data-categoria="<?php echo esc_attr($cat_slug); ?>">
                    Mostra altri <?php echo (int) $per_blocco; ?>
                </button>
                <span class="aria-grid-shown" id="aria-grid-shown"><?php echo (int) $per_blocco; ?> di <?php echo (int) $total_chars; ?></span>
            </div>
        <?php endif; ?>
    <?php endif; ?>
</div>


<script>
(function () {
    // Le card arrivano a blocchi dal server: la stanza non porta 200 link in una volta
    var piu = document.getElementById('aria-show-more');
    var mostrate = document.getElementById('aria-grid-shown');
    if (!piu) return;
    piu.addEventListener('click', function () {
        var passo = parseInt(piu.getAttribute('data-step'), 10) || 60;
        var totale = parseInt(piu.getAttribute('data-total'), 10) || 0;
        var categoria = piu.getAttribute('data-categoria') || '';
        var viste = document.querySelectorAll('.aria-character-card').length;
        piu.disabled = true;
        var corpo = new FormData();
        corpo.append('action', 'aria_chat_grid_more');
        corpo.append('category', categoria);
        corpo.append('offset', viste);
        corpo.append('step', passo);
        fetch((window.ariaChatConfig && ariaChatConfig.ajaxUrl) || '/wp-admin/admin-ajax.php', {
            method: 'POST', credentials: 'same-origin', body: corpo
        })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var griglia = document.querySelector('.aria-character-grid');
                if (griglia) griglia.insertAdjacentHTML('beforeend', html);
                var ora = document.querySelectorAll('.aria-character-card').length;
                if (mostrate) mostrate.textContent = ora + ' di ' + totale;
                piu.disabled = false;
                if (ora >= totale && piu.parentNode) piu.parentNode.removeChild(piu);
            })
            .catch(function () { piu.disabled = false; });
    });
})();
</script>

<?php if (!empty($seo_stanza['faq'])): ?>
<section class="aria-room-faq">
    <h2>Domande frequenti su <?php echo esc_html($cat_meta['name']); ?></h2>
    <?php foreach ($seo_stanza['faq'] as $coppia): ?>
        <details>
            <summary><?php echo esc_html($coppia[0]); ?></summary>
            <p><?php echo esc_html($coppia[1]); ?></p>
        </details>
    <?php endforeach; ?>
</section>
<?php
// Dati strutturati: la pagina è una collezione di personaggi + FAQ
$schema = array(
    '@context' => 'https://schema.org',
    '@graph' => array(
        array(
            '@type' => 'CollectionPage',
            'name' => $cat_meta['name'],
            'description' => wp_strip_all_tags($seo_stanza['desc'] ?? ''),
            'url' => get_permalink(),
            'isPartOf' => array('@type' => 'WebSite', 'name' => get_bloginfo('name'), 'url' => home_url('/')),
            'about' => array('@type' => 'Thing', 'name' => 'Chat erotica ' . $cat_meta['name']),
        ),
        array(
            '@type' => 'FAQPage',
            'mainEntity' => array_map(function ($c) {
                return array('@type' => 'Question', 'name' => $c[0],
                    'acceptedAnswer' => array('@type' => 'Answer', 'text' => $c[1]));
            }, $seo_stanza['faq']),
        ),
    ),
);
echo '<script type="application/ld+json">' . wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . '</script>';
?>
<?php endif; ?>



