<?php
/**
 * Plugin Name: PV Nofollow esterni
 * Description: Aggiunge rel="nofollow noopener" a tutti i link esterni nei contenuti e negli excerpt.
 *
 * Perché: i link in uscita servono al lettore e alla credibilità, ma non devono passare
 * "autorità" a terzi. I link interni restano normali. Il filtro agisce sia al salvataggio
 * sia al render, così copre anche articoli programmati e modifiche fatte da altri strumenti.
 */

if (!defined('ABSPATH')) {
    exit;
}

/** Riscrive i tag <a> esterni. */
function pv_nofollow_esterni($html) {
    if (!is_string($html) || strpos($html, '<a ') === false) {
        return $html;
    }
    $host = wp_parse_url(home_url(), PHP_URL_HOST);

    return preg_replace_callback('#<a\s[^>]*href=(["\'])([^"\']+)\1[^>]*>#i', function ($m) use ($host) {
        $url = $m[2];
        if (strpos($url, 'mailto:') === 0 || strpos($url, '#') === 0 || strpos($url, '/') === 0) {
            return $m[0];
        }
        $dest = wp_parse_url($url, PHP_URL_HOST);
        if (!$dest) {
            return $m[0];
        }
        $dest = preg_replace('/^www\./i', '', $dest);
        $host = preg_replace('/^www\./i', '', $host);
        if ($dest === $host) {
            return $m[0];
        }
        $tag = $m[0];
        if (preg_match('/\srel=/i', $tag)) {
            // rel già presente: aggiunge solo i valori mancanti
            return preg_replace_callback('/\srel=(["\'])([^"\']*)\1/i', function ($r) {
                $valori = preg_split('/\s+/', strtolower(trim($r[2])));
                foreach (array('nofollow', 'noopener') as $v) {
                    if (!in_array($v, $valori, true)) {
                        $valori[] = $v;
                    }
                }
                return ' rel="' . trim(implode(' ', array_filter($valori))) . '"';
            }, $tag);
        }
        return str_replace('<a ', '<a rel="nofollow noopener" ', $tag);
    }, $html);
}

add_filter('the_content', 'pv_nofollow_esterni', 20);
add_filter('the_excerpt', 'pv_nofollow_esterni', 20);

/** Al salvataggio: il rel resta scritto nel contenuto, non solo a schermo. */
function pv_nofollow_al_salvataggio($data, $postarr) {
    if (!empty($data['post_content'])) {
        $data['post_content'] = pv_nofollow_esterni($data['post_content']);
    }
    return $data;
}
add_filter('wp_insert_post_data', 'pv_nofollow_al_salvataggio', 20, 2);
