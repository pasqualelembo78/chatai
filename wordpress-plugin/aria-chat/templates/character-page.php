<?php
/**
 * Pagina di un singolo personaggio: /stanza/<categoria>/<slug>/
 * Testo di presentazione, chat già aperta, FAQ e link alla stanza.
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
$mestiere = $personaggio['job'] ?? '';
$essenza = trim((string) ($personaggio['essence'] ?? ''));
$carattere = trim((string) ($personaggio['personality'] ?? ''));
$seo = aria_room_seo($categoria);
$stadio = aria_grid_category_meta($categoria);
$room_url = get_permalink($stanza);
$base_url = rtrim($room_url, '/') . '/';

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
        <h1 class="pv-page-title">Chat con <?php echo esc_html($nome); ?></h1>
        <div class="pv-entry-meta">
            <?php if ($mestiere) : ?>
                <span><?php echo esc_html($mestiere); ?></span> &middot;
            <?php endif; ?>
            <?php if ($eta) : ?>
                <span><?php echo esc_html($eta); ?> <?php esc_html_e('anni', 'pornovirtuale'); ?></span> &middot;
            <?php endif; ?>
            <a href="<?php echo esc_url($room_url); ?>"><?php echo esc_html($stadio['name']); ?></a> &middot;
            <span class="rta-label"><strong>18+</strong></span>
        </div>
    </div>
</section>

<section class="section" style="padding-top:16px;">
    <div class="container">
        <div class="aria-room-intro" style="max-width:none;padding:0;margin-bottom:18px;">
            <?php if ($essenza) : ?>
                <p><?php echo esc_html($essenza); ?></p>
            <?php endif; ?>
            <p>
                <?php echo esc_html($nome); ?> ti aspetta nella stanza <?php echo esc_html($stadio['name']); ?>:
                <?php echo esc_html(strtolower($stadio['description'])); ?>.
                La chat è già aperta qui sotto, basta scrivere. Hai quattro messaggi gratis, poi serve l'accesso.
            </p>
            <?php if ($carattere) : ?>
                <p><?php echo esc_html($carattere); ?></p>
            <?php endif; ?>
        </div>

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
        $compagni = aria_characters_with_slug($categoria, $personaggio['id'], 6);
        if ($compagni) :
            ?>
            <div style="margin-top:26px;">
                <h2 class="pv-section-title pv-section-title--left">Altri personaggi in <?php echo esc_html($stadio['name']); ?></h2>
                <div class="page-links">
                    <?php foreach ($compagni as $altro) : ?>
                        <a class="internal-links" style="margin:0;" href="<?php echo esc_url($base_url . $altro['slug'] . '/'); ?>"><?php echo esc_html($altro['name']); ?></a>
                    <?php endforeach; ?>
                    <a class="internal-links" style="margin:0;" href="<?php echo esc_url($room_url); ?>">Tutti i <?php echo esc_html(strtolower($stadio['name'])); ?></a>
                </div>
            </div>
        <?php endif; ?>
    </div>
</section>

<?php get_footer(); ?>
