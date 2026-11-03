#!/bin/bash
# =============================================================================
# Script per creare automaticamente le 24 stanze WordPress (CPT "stanza")
# del plugin Aria Chat, una per categoria tematica.
#
# Requisiti:
#   - WordPress installato in /var/www/pornovirtuale/
#   - WP-CLI installato (consigliato) oppure PHP con accesso a wp-load.php
#   - Plugin aria-chat attivato
#   - Eseguito come root o utente con permessi su WordPress
# =============================================================================

set -uo pipefail

# ─── CONFIGURAZIONE ───────────────────────────────────────────────────────────
WP_PATH="/var/www/pornovirtuale"
WP_CLI_BIN="$(which wp 2>/dev/null || true)"
PHP_BIN="$(which php 2>/dev/null || true)"

# Le 24 categorie con slug e titolo
declare -a STANZE=(
    "amanti-segreti|Amanti Segreti"
    "bdsm|BDSM"
    "bisex|Bisex"
    "camera-privata|Camera Privata"
    "chat-romantica|Chat Romantica"
    "dirty-talk|Dirty Talk"
    "dominazione|Dominazione"
    "fantasie-erotiche|Fantasie Erotiche"
    "fantasie-proibite|Fantasie Proibite"
    "feticismi|Feticismi"
    "gay|Gay"
    "incontri-bollenti|Incontri Bollenti"
    "lesbo|Lesbo"
    "masturbazione|Masturbazione"
    "mature|Mature"
    "milf|MILF"
    "roleplay-erotico|Roleplay Erotico"
    "scambio-di-coppia|Scambio di Coppia"
    "senza-tabu|Senza Tabù"
    "sesso-orale|Sesso Orale"
    "sesso-virtuale|Sesso Virtuale"
    "sottomissione|Sottomissione"
    "threesome|Threesome"
    "voyeurismo|Voyeurismo"
)

# ─── FUNZIONI ─────────────────────────────────────────────────────────────────

log()  { echo "[INFO]  $*"; }
ok()   { echo "[OK]    $*"; }
err()  { echo "[ERRORE] $*" >&2; }
warn() { echo "[ATTENZ] $*"; }

check_requirements() {
    if [[ ! -d "$WP_PATH" ]]; then
        err "WordPress path non trovato: $WP_PATH"
        exit 1
    fi

    if [[ -z "$WP_CLI_BIN" && -z "$PHP_BIN" ]]; then
        err "Né WP-CLI né PHP sono disponibili."
        exit 1
    fi

    if [[ -n "$WP_CLI_BIN" ]]; then
        ok "WP-CLI trovato: $WP_CLI_BIN"
    fi
    if [[ -n "$PHP_BIN" ]]; then
        ok "PHP trovato: $PHP_BIN"
    fi
}

# ─── WP-CLI METODO ────────────────────────────────────────────────────────────

run_wpcli() {
    # Prova con URL diversi se necessario
    local urls=("https://www.pornovirtuale.com" "http://www.pornovirtuale.com" "https://pornovirtuale.com" "http://pornovirtuale.com" "")
    local output=""
    local exit_code=1

    for url in "${urls[@]}"; do
        if [[ -n "$url" ]]; then
            output=$(wp --path="$WP_PATH" --url="$url" --allow-root "$@" 2>&1)
            exit_code=$?
        else
            output=$(wp --path="$WP_PATH" --allow-root "$@" 2>&1)
            exit_code=$?
        fi
        if [[ $exit_code -eq 0 && -n "$output" ]]; then
            echo "$output"
            return 0
        fi
    done

    echo "$output"
    return $exit_code
}

check_post_type_exists_wpcli() {
    local pt_list
    pt_list=$(run_wpcli post type list --format=ids 2>/dev/null | tr -d '\n' || echo "")
    if echo "$pt_list" | tr ' ' '\n' | grep -qx "stanza"; then
        return 0
    fi
    return 1
}

post_exists_wpcli() {
    local title="$1"
    local existing
    existing=$(run_wpcli post list --post_type=stanza --post_status=any \
        --posts_per_page=1 --field=ID --format=ids --search="$title" 2>/dev/null | tr -d '\n' || echo "")
    [[ -n "$existing" ]]
}

create_stanza_wpcli() {
    local slug_cat="$1"
    local title="$2"
    local shortcode="[aria_chat category=\"$slug_cat\"]"

    log "Creazione stanza: $title"

    if post_exists_wpcli "$title"; then
        warn "  -> già esistente, salto"
        return 0
    fi

    local output
    output=$(run_wpcli post create \
        --post_type=stanza \
        --post_title="$title" \
        --post_content="$shortcode" \
        --post_status=publish \
        --post_author=1 \
        --format=ids 2>&1)
    local exit_code=$?

    output=$(echo "$output" | tr -d '[:space:]')

    if [[ $exit_code -eq 0 && "$output" =~ ^[0-9]+$ ]]; then
        ok "  -> creata (ID: $output)"
        return 0
    else
        err "  -> FALLITA (codice: $exit_code)"
        err "     Output: $output"
        return 1
    fi
}

# ─── PHP DIRETTO METODO ───────────────────────────────────────────────────────

create_stanza_php() {
    local slug_cat="$1"
    local title="$2"
    local shortcode="[aria_chat category=\"$slug_cat\"]"

    log "Creazione stanza: $title (via PHP diretto)"

    local result
    result=$(php -r "
        require '$WP_PATH/wp-load.php';

        \$existing = get_page_by_title('$title', OBJECT, 'stanza');
        if (\$existing) {
            echo 'EXISTS:' . \$existing->ID;
            exit;
        }

        \$post_id = wp_insert_post(array(
            'post_title'   => '$title',
            'post_content' => '$shortcode',
            'post_status'  => 'publish',
            'post_type'    => 'stanza',
            'post_author'  => 1,
            'post_excerpt' => 'Stanza chat dedicata alla categoria: $title',
        ));

        if (is_wp_error(\$post_id)) {
            echo 'ERROR:' . \$post_id->get_error_message();
        } else {
            echo 'CREATED:' . \$post_id;
        }
    " 2>&1)

    result=$(echo "$result" | tr -d '[:space:]')

    if [[ "$result" == CREATED:* ]]; then
        local id="${result#CREATED:}"
        ok "  -> creata (ID: $id)"
        return 0
    elif [[ "$result" == EXISTS:* ]]; then
        warn "  -> già esistente, salto"
        return 0
    else
        err "  -> FALLITA"
        err "     Output PHP: $result"
        return 1
    fi
}

# ─── MAIN ─────────────────────────────────────────────────────────────────────

main() {
    echo "======================================================================"
    echo "  Creazione Stanze WordPress - Aria Chat (24 categorie)"
    echo "======================================================================"
    echo ""

    check_requirements

    echo ""

    # ─── DEBUG WP-CLI ────────────────────────────────────────────────────
    if [[ -n "$WP_CLI_BIN" ]]; then
        log "Debug WP-CLI: versione e post type disponibili"
        local wp_version
        wp_version=$(run_wpcli core version 2>/dev/null | tr -d '\n' || echo "n/d")
        log "  WordPress version: $wp_version"

        local pt_list
        pt_list=$(run_wpcli post type list --format=ids 2>/dev/null | tr -d '\n' || echo "")
        log "  Post type trovati: $pt_list"

        if check_post_type_exists_wpcli; then
            ok "  CPT 'stanza' trovato da WP-CLI"
        else
            err "  CPT 'stanza' NON trovato da WP-CLI"
        fi

        local plugin_status
        plugin_status=$(run_wpcli plugin list --format=ids --fields=name,status 2>/dev/null | grep -i aria || echo "plugin aria-chat non trovato")
        log "  Plugin aria-chat: $plugin_status"

        echo ""
    fi

    # Determina quale metodo usare
    USE_WPCLI=false
    USE_PHP=false

    if [[ -n "$WP_CLI_BIN" ]]; then
        USE_WPCLI=true
    fi
    if [[ -n "$PHP_BIN" && -f "$WP_PATH/wp-load.php" ]]; then
        USE_PHP=true
    fi

    if ! $USE_WPCLI && ! $USE_PHP; then
        err "Nessun metodo disponibile per creare post."
        exit 1
    fi

    log "Trovate ${#STANZE[@]} categorie da processare."
    echo ""

    local created=0
    local failed=0

    for entry in "${STANZE[@]}"; do
        local slug_cat="${entry%%|*}"
        local title="${entry##*|}"

        if $USE_WPCLI; then
            if create_stanza_wpcli "$slug_cat" "$title"; then
                ((created++)) || true
            else
                ((failed++)) || true
            fi
        elif $USE_PHP; then
            if create_stanza_php "$slug_cat" "$title"; then
                ((created++)) || true
            else
                ((failed++)) || true
            fi
        fi
    done

    echo ""
    echo "======================================================================"
    echo "  RIEPILOGO"
    echo "======================================================================"
    echo "  Stanze processate: ${#STANZE[@]}"
    echo "  Stanze create/verificate: $created"
    echo "  Stanze fallite: $failed"
    echo "======================================================================"
    echo ""
    if [[ $failed -eq 0 ]]; then
        ok "Operazione completata con successo."
    else
        err "Operazione completata con $failed fallimento/i."
    fi
    log "Verifica in: wp-admin/edit.php?post_type=stanza"
}

main "$@"