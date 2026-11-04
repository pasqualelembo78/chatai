<?php
// Variabili di intestazione: devono essere calcolate PRIMA dell'HTML.
$is_dedicated = !empty($atts['character']);
$cat_slug = !empty($atts['category']) ? $atts['category'] : '';
$char_name_for_header = '';
if ($is_dedicated) {
    $char_name_for_header = $atts['character'];
    $json_dir = '/opt/aria/backend/characters/data';
    if (is_dir($json_dir)) {
        foreach (glob($json_dir . '/*.json') as $file) {
            if (basename($file) === 'categories.json') continue;
            $data = json_decode(file_get_contents($file), true);
            if (!is_array($data)) continue;
            foreach ($data as $c) {
                if (!empty($c['id']) && $c['id'] === $atts['character']) {
                    $char_name_for_header = $c['name'] ?? $atts['character'];
                    break 2;
                }
            }
        }
    }
}
$chat_greeting = $is_dedicated
    ? 'Sei in una chat privata con ' . $char_name_for_header . '. Scrivi per iniziare.'
    : 'Benvenuto in Aria Chat! Seleziona un personaggio e inizia la conversazione.';
?>
<div class="aria-chat-container" style="width: <?php echo esc_attr($atts['width']); ?>; height: <?php echo esc_attr($atts['height']); ?>;">
    
    <div class="aria-chat-header">
        <div class="aria-chat-title">
            <span class="aria-chat-emoji">🤖</span>
            <span class="aria-chat-name">
                <?php if ($is_dedicated && !empty($char_name_for_header)): ?>
                    <?php echo esc_html($char_name_for_header); ?>
                <?php else: ?>
                    Aria Chat AI
                <?php endif; ?>
            </span>
            <?php if (!empty($cat_slug) && !$is_dedicated): ?>
                <span style="font-size:11px; opacity:0.85; margin-left:4px;">— <?php echo esc_html(ucwords(str_replace('-',' ',$cat_slug))); ?></span>
            <?php endif; ?>
        </div>
        <div class="aria-chat-controls">
            <?php if (!$is_dedicated): ?>
            <form class="aria-search-form" onsubmit="return false;">
                <input type="search" id="aria-character-search" class="aria-character-search" placeholder="Cerca personaggio..." />
            </form>
            <select id="aria-character-select" class="aria-character-select">
                <option value="">Caricamento personaggi...</option>
            </select>
            <?php endif; ?>
            <button id="aria-login-btn" class="aria-btn aria-btn-small">Login</button>
            <button id="aria-register-btn" class="aria-btn aria-btn-small">Registrati</button>
            <button id="aria-logout-btn" class="aria-btn aria-btn-small" style="display:none;">Logout</button>
            <?php if ($is_dedicated || $cat_slug): ?>
            <button type="button" id="aria-export-btn" class="aria-btn aria-btn-small" title="Scarica la conversazione in un file di testo">Esporta</button>
            <?php endif; ?>
        </div>
    </div>
    <?php if ($is_dedicated): ?>
    <input type="hidden" id="aria-preset-character" value="<?php echo esc_attr($atts['character']); ?>" />
    <?php else: ?>
    <input type="hidden" id="aria-preset-character" value="" />
    <?php endif; ?>
    <?php if (!empty($atts['category'])): ?>
    <input type="hidden" id="aria-shortcode-category" value="<?php echo esc_attr($atts['category']); ?>" />
    <?php endif; ?>
    <style>.pv-player--empty { display: none !important; }</style>
    
    <div id="aria-login-modal" class="aria-modal" style="display:none;">
        <div class="aria-modal-content">
            <h3>Accedi ad Aria Chat</h3>
            <input type="text" id="aria-login-username" placeholder="Username" class="aria-input" />
            <input type="password" id="aria-login-password" placeholder="Password" class="aria-input" />
            <div class="aria-modal-buttons">
                <button id="aria-login-submit" class="aria-btn">Accedi</button>
                <button id="aria-login-cancel" class="aria-btn aria-btn-secondary">Annulla</button>
            </div>
            <p class="aria-modal-link">Non hai un account? <a href="#" id="aria-switch-to-register">Registrati</a></p>
            <p id="aria-login-error" class="aria-error" style="display:none;"></p>
        </div>
    </div>
    
    <div id="aria-register-modal" class="aria-modal" style="display:none;">
        <div class="aria-modal-content">
            <h3>Registrati ad Aria Chat</h3>
            <input type="text" id="aria-register-username" placeholder="Username" class="aria-input" />
            <input type="email" id="aria-register-email" placeholder="Email" class="aria-input" />
            <input type="password" id="aria-register-password" placeholder="Password" class="aria-input" />
            <input type="date" id="aria-register-birthdate" class="aria-input" />
            <div class="aria-modal-buttons">
                <button id="aria-register-submit" class="aria-btn">Registrati</button>
                <button id="aria-register-cancel" class="aria-btn aria-btn-secondary">Annulla</button>
            </div>
            <p class="aria-modal-link">Hai già un account? <a href="#" id="aria-switch-to-login">Accedi</a></p>
            <p id="aria-register-error" class="aria-error" style="display:none;"></p>
            <p id="aria-register-success" class="aria-success" style="display:none;"></p>
        </div>
    </div>
    
    <div class="aria-chat-messages" id="aria-messages">
        <div class="aria-message aria-message-system">
            <div class="aria-message-content"><?php echo esc_html($chat_greeting); ?></div>
        </div>
    </div>
    
    <?php
    // Un solo pulsante: chiede al personaggio una domanda d'apertura, per chi non sa
    // da dove cominciare. La frase la genera il modello, non è un elenco fisso.
    ?>
    <div class="aria-spunto-row">
        <button type="button" id="aria-spunto" class="aria-spunto"
                title="Non so cosa dire: fammi una domanda" aria-label="Fammi una domanda">?</button>
        <span class="aria-spunto-hint" id="aria-spunto-hint">Non sai da dove cominciare? Premi il punto interrogativo.</span>
    </div>

    <div class="aria-chat-input-container">
        <textarea 
            id="aria-message-input" 
            class="aria-message-input" 
            placeholder="Scrivi il tuo messaggio..." 
            rows="1"
        ></textarea>
        <button id="aria-send-btn" class="aria-btn aria-send-button">
            <span>➤</span>
        </button>
    </div>
    
    <div class="aria-chat-status" id="aria-status">
        <span class="aria-status-dot"></span>
        <span class="aria-status-text">Connesso</span>
    </div>
</div>
<!-- Pannello Memoria Granulare -->
<div id="aria-memory-panel" style="display:none; position:fixed; bottom:60px; right:10px; background:#fff; border:1px solid #ddd; border-radius:8px; padding:12px; width:320px; max-height:400px; overflow-y:auto; z-index:10000; box-shadow:0 4px 12px rgba(0,0,0,0.25); font-family:sans-serif; font-size:13px;">
  <h3 style="margin:0 0 8px; font-size:14px; color:#333;">Memoria personale</h3>
  <div id="aria-memory-list"></div>
  <div style="margin-top:8px; border-top:1px solid #eee; padding-top:8px;">
    <input id="aria-mem-key" type="text" placeholder="Chiave (es. città, nome)" style="width:45%; padding:4px; font-size:12px;" />
    <input id="aria-mem-val" type="text" placeholder="Valore (correggi)" style="width:45%; padding:4px; font-size:12px;" />
    <button onclick="saveMemoryItem()" style="padding:4px 8px; font-size:12px; background:#e91e8c; color:#fff; border:none; border-radius:3px;">Salva</button>
  </div>
  <button onclick="clearAllMemory()" style="margin-top:8px; padding:4px 8px; font-size:12px; background:#ff4444; color:#fff; border:none; border-radius:3px;">Cancella tutto</button>
  <button onclick="toggleMemoryPanel()" style="margin-top:8px; display:block; font-size:11px; color:#777;">Chiudi</button>
</div>
<button type="button" onclick="try{ toggleMemoryPanel(); }catch(e){ var p=document.getElementById('aria-memory-panel'); if(p){ if(p.style.display==='none'||p.style.display===''){p.style.display='block'; if(typeof loadMemory==='function')loadMemory();}else{p.style.display='none';} } }" style="position:fixed; bottom:10px; right:10px; padding:6px 12px; background:#e91e8c; color:#fff; border:none; border-radius:20px; font-size:12px; cursor:pointer; z-index:10001;">Memoria</button>


<!-- FALLBACK MEMORIA VANILLA JS -->
<script>
(function(){
  window.toggleMemoryPanel = window.toggleMemoryPanel || function(){
    var panel = document.getElementById('aria-memory-panel');
    if(!panel) return;
    if(panel.style.display === 'none' || panel.style.display === ''){
      panel.style.display = 'block';
      if(typeof window.loadMemory === 'function'){ window.loadMemory(); }
      return;
    }
    panel.style.display = 'none';
  };

  window.loadMemory = window.loadMemory || function(){
    var list = document.getElementById('aria-memory-list');
    if(!list) return;
    list.innerHTML = '<div style="font-size:12px;color:#777;">Caricamento...</div>';
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action','aria_chat_get_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    fetch(ajaxUrl, {method:'POST', credentials:'same-origin', body:data})
      .then(function(r){return r.json();})
      .then(function(r){
        if(r && r.success && r.data){
          var html=''; var count=0;
          for(var k in r.data){ if(r.data.hasOwnProperty(k)){ count++; html += '<div style="font-size:12px;padding:4px 2px;border-bottom:1px solid #f0f0f0;word-break:break-word;"><b>'+k.replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</b>: '+String(r.data[k]).replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</div>'; }}
          if(count===0) list.innerHTML = '<div style="font-size:12px;color:#777;">Nessuna memoria salvata. Puoi correggere qualcosa con <b>Memoria: chiave=valore</b> direttamente in chat.</div>';
          else list.innerHTML = html;
        }else{
          list.innerHTML = '<div style="font-size:12px;color:#777;">Nessuna memoria salvata. Puoi correggere qualcosa con <b>Memoria: chiave=valore</b> direttamente in chat.</div>';
        }
      })
      .catch(function(){ list.innerHTML = '<div style="font-size:12px;color:#d33;">Errore nel caricamento.</div>'; });
  };

  window.saveMemoryItem = window.saveMemoryItem || function(){
    var k = document.getElementById('aria-mem-key'); var v = document.getElementById('aria-mem-val');
    if(!k||!v) return;
    var keyv = k.value.trim(); var valv = v.value.trim();
    if(keyv===''){ alert('Inserisci una chiave'); return; }
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action','aria_chat_save_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    data.append('key', keyv);
    data.append('value', valv);
    fetch(ajaxUrl,{method:'POST',credentials:'same-origin',body:data})
      .then(function(r){return r.json();})
      .then(function(r){
        if(r && r.success){ alert('Memoria aggiornata: '+keyv+' = '+(valv===''?'(vuoto)':valv)); k.value=''; v.value=''; if(typeof loadMemory==='function') loadMemory(); }
        else alert('Errore nel salvataggio');
      })
      .catch(function(){ alert('Errore di connessione'); });
  };

  window.clearAllMemory = window.clearAllMemory || function(){
    if(!confirm('Cancellare TUTTA la memoria per questo personaggio?')) return;
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action','aria_chat_delete_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    fetch(ajaxUrl,{method:'POST',credentials:'same-origin',body:data})
      .then(function(r){return r.json();})
      .then(function(r){
        if(r && r.success){ alert('Memoria cancellata'); if(typeof loadMemory==='function') loadMemory(); }
        else alert('Errore');
      })
      .catch(function(){ alert('Errore'); });
  };
// === PANNELLO PREMIUM / IMPOSTAZIONI ===
var ariaPremium = {
    features: {
        impersonation:   { name: 'Impersonificazione (fingi di essere qualcun altro)', cost: 1000, unlocked: true },
        extended_memory: { name: 'Memoria Estesa', cost: 80, unlocked: true },
        premium_voice:   { name: 'Messaggi Vocali Premium', cost: 30, unlocked: true },
        image_gen:       { name: 'Generazione Immagini', cost: 50, unlocked: true },
        video_gen:       { name: 'Generazione Video', cost: 100, unlocked: true },
        group_chat:      { name: 'Chat di Gruppo', cost: 40, unlocked: true },
        no_ads:          { name: 'Nessuna Pubblicità', cost: 120, unlocked: true },
        daily_limit:     { name: 'Messaggi Illimitati (no limite giornaliero)', cost: 100, unlocked: true }
    },
    toggle: function(featureId) {
        var f = this.features[featureId];
        if (!f) return;
        f.unlocked = !f.unlocked;
        this.save();
        this.render();
    },
    save: function() {
        try {
            var data = {};
            for (var k in this.features) {
                data[k] = this.features[k].unlocked;
            }
            localStorage.setItem('aria_premium_features', JSON.stringify(data));
        } catch(e) {}
    },
    load: function() {
        try {
            var stored = localStorage.getItem('aria_premium_features');
            if (stored) {
                var data = JSON.parse(stored);
                for (var k in data) {
                    if (this.features[k]) this.features[k].unlocked = data[k];
                }
            }
        } catch(e) {}
    },
    render: function() {
        var list = document.getElementById('aria-premium-list');
        if (!list) return;
        var html = '';
        for (var id in this.features) {
            var f = this.features[id];
            html += '<div style="font-size:12px;padding:6px 2px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">' +
                '<div style="word-break:break-word;"><b>'+f.name+'</b> <span style="font-size:10px;color:#777;">('+f.cost+' MVC)</span></div>' +
                '<label style="position:relative;display:inline-block;width:44px;height:24px;">' +
                '<input type="checkbox" ' + (f.unlocked ? 'checked' : '') + ' onchange="ariaPremium.toggle(\'' + id + '\')" style="opacity:0;width:0;height:0;">' +
                '<span style="position:absolute;top:0;left:0;width:100%;height:100%;background:'+(f.unlocked?'#e91e8c':'#ccc')+';border-radius:24px;transition:0.2s;"></span>' +
                '<span style="position:absolute;top:2px;left:2px;width:20px;height:20px;background:#fff;border-radius:50%;transition:0.2s;'+(f.unlocked?'transform:translateX(20px)':'')+';"></span>' +
                '</label>' +
                '</div>';
        }
        list.innerHTML = html;
    }
};

function togglePremiumPanel() {
    var panel = document.getElementById('aria-premium-panel');
    if (!panel) return;
    if (panel.style.display === 'none' || panel.style.display === '') {
        panel.style.display = 'block';
        ariaPremium.render();
    } else {
        panel.style.display = 'none';
    }
}

ariaPremium.load();

// Pulsante Premium accanto a Memoria
var btnPremium = document.createElement('button');
btnPremium.type = 'button';
btnPremium.onclick = function(e){ e.stopPropagation(); togglePremiumPanel(); };
btnPremium.style.cssText = 'position:fixed; bottom:50px; right:10px; padding:6px 12px; background:#6a1b9a; color:#fff; border:none; border-radius:20px; font-size:12px; cursor:pointer; z-index:10001;';
btnPremium.textContent = 'Premium';
document.body.appendChild(btnPremium);

// Pannello Premium HTML
var panelHTML = '<div id="aria-premium-panel" style="display:none; position:fixed; bottom:90px; right:10px; background:#fff; border:1px solid #ddd; border-radius:8px; padding:12px; width:340px; max-height:500px; overflow-y:auto; z-index:10000; box-shadow:0 4px 12px rgba(0,0,0,0.25); font-family:sans-serif; font-size:13px;">' +
  '<h3 style="margin:0 0 8px; font-size:14px; color:#333;">Impostazioni Premium</h3>' +
  '<div id="aria-premium-list"></div>' +
  '<div style="margin-top:10px; border-top:1px solid #eee; padding-top:8px; font-size:11px; color:#777;">Modalità test: tutte le funzionalità sono sbloccate di default. Puoi disattivarle singolarmente.</div>' +
  '<button onclick="togglePremiumPanel()" style="margin-top:8px; padding:4px 8px; font-size:11px; background:#777; color:#fff; border:none; border-radius:3px;">Chiudi</button>' +
  '</div>';
document.body.insertAdjacentHTML('beforeend', panelHTML);

})();
</script>

