<?php
/**
 * Pagina di un singolo personaggio: /stanza/<categoria>/<slug>/
 *
 * Struttura pensata per la ricerca: gerarchia H1/H2, testo unico, chat aperta,
 * FAQ e maglia di link interni (compagni di stanza, stanze vicine, archivio).
 */

if (!defined('ABSPATH')) {
    exit;
}

$stanza = get_queried_object();
$slug_personaggio = sanitize_title(get_query_var('personaggio'));
$categoria = $stanza ? get_post_field('post_name', $stanza->ID) : '';
$personaggio = aria_char_by_slug($categoria, $slug_personaggio);

if (!$personaggio) {
    wp_safe_redirect(get_permalink($stanza));
    exit;
}

$nome = $personaggio['name'] ?? '';
$eta = (int) ($personaggio['age'] ?? 0);
$mestiere = trim((string) ($personaggio['job'] ?? ''));
$essenza = trim((string) ($personaggio['essence'] ?? ''));
$carattere = trim((string) ($personaggio['personality'] ?? ''));
$comportamento = trim((string) ($personaggio['role'] ?? ''));
$tag = array_slice((array) ($personaggio['tags'] ?? array()), 0, 5);
$seo = aria_room_seo($categoria);
$stadio = aria_grid_category_meta($categoria);
$room_url = get_permalink($stanza);
$base_url = rtrim($room_url, '/') . '/';

// stanze vicine come link orizzontali
$vicine = array();
foreach (aria_room_seo_data() as $altro_slug => $altro) {
    if ($altro_slug === $categoria) {
        continue;
    }
    $vicine[] = $altro_slug;
}
$vicine = array_slice($vicine, 0, 4);

get_header();
?>

<section class="pv-page-head">
    <div class="container">
        <nav class="pv-breadcrumb">
            <a href="<?php echo esc_url(home_url('/')); ?>">Home</a> /
            <a href="<?php echo esc_url(get_post_type_archive_link('stanza')); ?>">Stanze</a> /
            <a href="<?php echo esc_url($room_url); ?>"><?php echo esc_html($stadio['name']); ?></a> /
            <?php echo esc_html($nome); ?>
        </nav>
        <h1 class="pv-page-title">Chat con <?php echo esc_html($nome); ?><?php echo $mestiere ? ', ' . esc_html(strtolower($mestiere)) : ''; ?></h1>
        <div class="pv-entry-meta">
            <?php if ($eta) : ?>
                <span><?php echo esc_html($eta); ?> <?php esc_html_e('anni', 'pornovirtuale'); ?></span> &middot;
            <?php endif; ?>
            <a href="<?php echo esc_url($room_url); ?>">Stanza <?php echo esc_html($stadio['name']); ?></a> &middot;
            <span class="rta-label"><strong>18+</strong></span>
        </div>
    </div>
</section>

<section class="section" style="padding-top:16px;">
    <div class="container">

        <div class="aria-char-page">
            <div class="aria-char-page__testo">
                <h2>Chi è <?php echo esc_html($nome); ?></h2>
                <p>
                    <?php echo esc_html($nome); ?> ha <?php echo (int) $eta; ?> anni<?php echo $mestiere ? ' e di mestiere fa ' . esc_html(strtolower($mestiere)) : ''; ?>.
                    <?php if ($essenza) : ?>
                        <?php echo esc_html($essenza); ?>
                    <?php endif; ?>
                </p>

                <h2>Come si comporta in chat</h2>
                <p>
                    <?php echo esc_html($comportamento ?: 'Personaggio della stanza ' . $stadio['name']); ?>.
                    <?php if ($carattere) : ?>
                        <?php echo esc_html($carattere); ?>
                    <?php endif; ?>
                </p>
                <p>
                    Si muove dentro il tema della stanza: <?php echo esc_html(strtolower($stadio['description'])); ?>.
                    La chat è già aperta qui sotto: scrivi e risponde in pochi secondi, restando nel personaggio.
                    Hai <strong>quattro messaggi gratis</strong>, poi serve l'accesso.
                </p>

                <?php if ($tag) : ?>
                    <h2>Parole chiave</h2>
                    <ul class="aria-char-page__tag">
                        <?php foreach ($tag as $t) : ?>
                            <li><?php echo esc_html($t); ?></li>
                        <?php endforeach; ?>
                    </ul>
                <?php endif; ?>
            </div>
        </div>

        <h2 class="aria-char-page__h2-chat">Scrivi a <?php echo esc_html($nome); ?></h2>
        <?php
        $chat_atts = array(
            'character' => $personaggio['id'],
            'category'  => $categoria,
            'width'     => '100%',
            'height'    => '500px',
        );
        $atts = $chat_atts;
        include ARIA_CHAT_PLUGIN_DIR . 'templates/chat-box.php';
        ?>

        <?php if (!empty($seo['faq'])) : ?>
            <section class="aria-room-faq" style="padding:0;max-width:none;">
                <h2>Domande su <?php echo esc_html($nome); ?></h2>
                <?php foreach ($seo['faq'] as $coppia) : ?>
                    <details>
                        <summary><?php echo esc_html($coppia[0]); ?></summary>
                        <p><?php echo esc_html($coppia[1]); ?></p>
                    </details>
                <?php endforeach; ?>
            </section>
        <?php endif; ?>

        <?php
        $compagni = aria_characters_with_slug($categoria, $personaggio['id'], 12);
        if ($compagni) :
            ?>
            <div class="aria-char-page__link">
                <h2>Altri personaggi in <?php echo esc_html($stadio['name']); ?></h2>
                <div class="page-links">
                    <?php foreach ($compagni as $altro) : ?>
                        <a class="internal-links" style="margin:0;" href="<?php echo esc_url($base_url . $altro['slug'] . '/'); ?>"><?php echo esc_html($altro['name']); ?></a>
                    <?php endforeach; ?>
                    <a class="internal-links" style="margin:0;" href="<?php echo esc_url($room_url); ?>">Tutti: <?php echo esc_html($stadio['name']); ?></a>
                </div>
            </div>
        <?php endif; ?>

        <?php if ($vicine) : ?>
            <div class="aria-char-page__link">
                <h2>Altre stanze di chat</h2>
                <div class="page-links">
                    <?php foreach ($vicine as $altro_slug) : ?>
                        <?php $meta = aria_grid_category_meta($altro_slug); ?>
                        <a class="internal-links" style="margin:0;" href="<?php echo esc_url(home_url('/stanza/' . $altro_slug . '/')); ?>"><?php echo esc_html($meta['name']); ?></a>
                    <?php endforeach; ?>
                    <a class="internal-links" style="margin:0;" href="<?php echo esc_url(get_post_type_archive_link('stanza')); ?>">Tutte le stanze</a>
                </div>
            </div>
        <?php endif; ?>

    </div>
</section>

<?php get_footer(); ?>
