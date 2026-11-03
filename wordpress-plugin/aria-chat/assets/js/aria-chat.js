(function($) {
    'use strict';
    var config = window.ariaChatConfig || {};
    var currentCharacter = '';
    var isLoggedIn = false;
    var $messages = $('#aria-messages');
    var $input = $('#aria-message-input');
    var $sendBtn = $('#aria-send-btn');
    var $charSelect = $('#aria-character-select');
    var $charSearch = $('#aria-character-search');
    var allCharacters = [];
    var searchTimer = null;
    var $loginBtn = $('#aria-login-btn');
    var $registerBtn = $('#aria-register-btn');
    var $logoutBtn = $('#aria-logout-btn');
    var $loginModal = $('#aria-login-modal');
    var $registerModal = $('#aria-register-modal');
    var $status = $('#aria-status');

    function init() {
        config = window.ariaChatConfig || config;
        // Il plugin enqueue questo JS su tutto il sito: senza contenitore chat non c'e'
        // nulla da inizializzare (evita TypeError su $input[0]/$messages[0] assenti).
        if (!$messages.length || !$input.length) { return; }
        // Leggi la categoria dallo shortcode (se non già in config)
        var shortcodeCat = document.getElementById('aria-shortcode-category');
        if (shortcodeCat && shortcodeCat.value && !(config && config.category)) {
            config.category = shortcodeCat.value;
        }
        loadCharacters();
        checkAuthStatus();
        setupEventListeners();
        autoResizeInput();
        loadAvgResponseTime();
        // Se c'è un character preselezionato (stanza dedicata), selezionalo direttamente
        var preset = document.getElementById('aria-preset-character');
        if ((!preset || !preset.value) && config && config.character) {
            currentCharacter = config.character;
        }
        if (preset && preset.value) {
            currentCharacter = preset.value;
            loadAvgResponseTime(currentCharacter);
            apriConversazione(currentCharacter);
            // Seleziona nell'option del select se esiste
            var $sel = $('#aria-character-select');
            if ($sel.length) {
                $sel.val(preset.value);
            }
            addSystemMessage('Personaggio selezionato: ' + preset.value);
        }
        // Mostra il contesto della categoria (se specificata nello shortcode)
        if (ariaChatConfig.category) {
            addSystemMessage('Stanza: ' + ariaChatConfig.category);
        }
        // Verifica età una tantum (se non già verificato in sessione precedente)
        checkAgeVerification();
    }
    
    function setupEventListeners() {
        $sendBtn.on('click', sendMessage);
        $input.on('keydown', function(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (typeof sendMessage === 'function') sendMessage(); } });
        $charSelect.on('change', function() {
            currentCharacter = $(this).val();
            if (currentCharacter) {
                addSystemMessage('Personaggio: ' + $(this).find('option:selected').text());
                // La barra va calibrata sul tempo di QUESTA chat, non su quella precedente
                loadAvgResponseTime(currentCharacter);
            }
        });
        $charSearch.on('input', filterCharacters);
        $loginBtn.on('click', showLoginModal);
        $registerBtn.on('click', showRegisterModal);
        $logoutBtn.on('click', logout);
        $('#aria-login-submit').on('click', doLogin);
        $('#aria-login-cancel').on('click', hideLoginModal);
        $('#aria-register-submit').on('click', doRegister);
        $('#aria-register-cancel').on('click', hideRegisterModal);
        $('#aria-switch-to-register').on('click', function(e) { e.preventDefault(); hideLoginModal(); showRegisterModal(); });
        $('#aria-switch-to-login').on('click', function(e) { e.preventDefault(); hideLoginModal(); showLoginModal(); });
        $input.on('input', autoResizeInput);
    }
    
    
    function loadCharacters() {
        var responseStart = performance.now();
        var data = { action: 'aria_chat_characters', limit: 200 };
        // Se c'è una categoria preimpostata (stanza dedicata), filtra per quella categoria
        if (ariaChatConfig && ariaChatConfig.category) {
            data['category'] = ariaChatConfig.category;
        }
        $.ajax({
            url: config.ajaxUrl, type: 'POST',
            data: data,
            success: function(response) {
                if (response && response.success && response.data) {
                    var chars = Array.isArray(response.data) ? response.data : [];
                    var valid = [];
                    for (var i = 0; i < chars.length; i++) {
                        var c = chars[i];
                        if (c && c.id && c.name) valid.push(c);
                    }
                    valid.sort(function(a, b) {
                        return String(a.name).toLowerCase().localeCompare(String(b.name).toLowerCase());
                    });
                    allCharacters = valid;
                    renderCharacters(allCharacters);
                    if (allCharacters.length > 0) {
                        currentCharacter = $charSelect.val();
                        addSystemMessage('Personaggi caricati (' + allCharacters.length + '). Seleziona e chatta!');
                    }
                } else {
                    addSystemMessage('Errore nel caricamento personaggi');
                }
            },
            error: function() { addSystemMessage('Errore connessione'); }
        });
    }
    
    function renderCharacters(list) {
        var selected = currentCharacter;
        $charSelect.empty();
        $charSelect.append('<option value="">-- Seleziona personaggio --</option>');
        var found = false;
        for (var i = 0; i < list.length; i++) {
            var c = list[i];
            if (c && c.id && c.name) {
                var label = c.name + (c.role ? ' (' + c.role + ')' : '');
                $charSelect.append($('<option></option>').val(c.id).text(label));
                if (c.id === selected) found = true;
            }
        }
        if (found) {
            $charSelect.val(selected);
        }
    }
    
    function filterCharacters() {
        var q = ($charSearch.val() || '').trim();
        if (!q) {
            renderCharacters(allCharacters);
            return;
        }
        var qLower = q.toLowerCase();
        var quick = allCharacters.filter(function(c) {
            var name = String(c.name || '').toLowerCase();
            var role = String(c.role || '').toLowerCase();
            return name.indexOf(qLower) !== -1 || role.indexOf(qLower) !== -1;
        });
        renderCharacters(quick);
        if (searchTimer) clearTimeout(searchTimer);
        searchTimer = setTimeout(function() {
            var searchData = { action: 'aria_chat_characters', search: q, limit: 200 };
            if (ariaChatConfig && ariaChatConfig.category) {
                searchData['category'] = ariaChatConfig.category;
            }
            $.ajax({
                url: config.ajaxUrl, type: 'POST',
                data: searchData,
                success: function(response) {
                    if (response && response.success && response.data) {
                        var chars = Array.isArray(response.data) ? response.data : [];
                        var valid = [];
                        for (var i = 0; i < chars.length; i++) {
                            var c = chars[i];
                            if (c && c.id && c.name) valid.push(c);
                        }
                        valid.sort(function(a, b) {
                            return String(a.name).toLowerCase().localeCompare(String(b.name).toLowerCase());
                        });
                        renderCharacters(valid);
                    } else {
                        renderCharacters([]);
                    }
                },
                error: function() { renderCharacters([]); }
            });
        }, 300);
    }
    
    function checkAuthStatus() {
        $.ajax({
            url: config.ajaxUrl, type: 'POST',
            data: { action: 'aria_chat_auth_status' },
            success: function(response) { isLoggedIn = !!(response && response.isLoggedIn); updateAuthUI(); }
        });
    }
    
    function updateAuthUI() {
        if (isLoggedIn) { $loginBtn.hide(); $registerBtn.hide(); $logoutBtn.show(); }
        else { $loginBtn.show(); $registerBtn.show(); $logoutBtn.hide(); }
    }
    
    function showLoginModal() { $loginModal.show(); $('#aria-login-error').hide(); }
    function hideLoginModal() { $loginModal.hide(); }
    function showRegisterModal() { $registerModal.show(); $('#aria-register-error').hide(); $('#aria-register-success').hide(); }
    function hideRegisterModal() { $registerModal.hide(); }
    function showAgeVerificationModal() {
        var existing = document.getElementById('aria-age-modal');
        if (existing) existing.remove();
        var modal = document.createElement('div');
        modal.id = 'aria-age-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Verifica di eta');
        modal.setAttribute('style', 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.94);z-index:9999;display:flex;align-items:center;justify-content:center;font-family:Roboto,sans-serif;color:#fff;text-align:center;padding:20px');
        modal.innerHTML =
            "<div style='max-width:520px'>" +
            "<h1 style='font-family:Orbitron,sans-serif;color:#FF3C5B;margin-bottom:12px'>Pornovirtuale</h1>" +
            "<p style='margin-bottom:8px'>Il sito contiene contenuti espliciti riservati a maggiorenni.</p>" +
            "<p style='margin-bottom:18px;font-size:.9em;color:#aaa'>Confermando dichiari di avere almeno 18 anni e di essere in possesso di un documento d'identita valido.</p>" +
            "<button id='ag-yes' style='padding:12px 28px;background:#FF3C5B;color:#fff;border:0;border-radius:8px;font-weight:600;cursor:pointer;margin-right:8px'>Ho 18 anni o piu</button>" +
            "<a id='ag-no' href='https://www.google.com' style='padding:12px 28px;background:#2B2B3C;color:#fff;border-radius:8px;text-decoration:none;display:inline-block'>Esci</a>" +
            "</div>";
        document.body.appendChild(modal);
        document.getElementById('ag-yes').onclick = function() {
            localStorage.setItem('aria_age_verified', 'true');
            document.getElementById('aria-age-modal').remove();
            verifyAgeOnServer();
            addSystemMessage('Età verificata. Buona conversazione!');
        };
        document.getElementById('ag-no').onclick = function() {
            document.getElementById('aria-age-modal').remove();
            addSystemMessage('Verifica età richiesta per continuare.');
        };
    }
    
    function checkAgeVerification() {
        if (localStorage.getItem('aria_age_verified') === 'true') return;
        if (!isLoggedIn && !(config && config.userLoggedIn)) return;
        showAgeVerificationModal();
    }
    
    function autoResizeInput() { if (!$input.length) return; $input.css('height', 'auto'); $input.css('height', Math.min($input[0].scrollHeight, 100) + 'px'); }

    function addUserMessage(text) { $messages.append($('<div class="aria-message aria-message-user"><div class="aria-message-content">'+escapeHtml(text)+'</div><div class="aria-message-meta">'+new Date().toLocaleTimeString()+'</div></div>')); scrollToBottom(); }

    function refreshMemoryPanel() {
        if (typeof loadMemory === 'function') { loadMemory(); }
    }

    function addAIMessage(text, emotion) {
        var emo = getEmotionEmoji(emotion);
        var $div = $('<div class="aria-message aria-message-ai"><div class="aria-message-content">'+emo+' '+escapeHtml(text)+'</div><div class="aria-message-meta">'+new Date().toLocaleTimeString()+'</div></div>');
        $messages.append($div);
        scrollToBottom();
        // Effetto stream simulato: mostra carattere per carattere
        var $content = $div.find('.aria-message-content');
        var chars = $content.text().split('');
        $content.text('');
        var i = 0;
        var tick = setInterval(function(){
            if (i < chars.length) { $content.text($content.text() + chars[i]); i++; }
            else {
                clearInterval(tick);
                // Nascondi barra di caricamento solo dopo che lo stream è completo
                hideProgressBar();
                // Salva tempo effettivo per media adattativa barra successiva
                if (window.chatStartTime) {
                    var endAt = window.ariaFetchDoneAt || performance.now();
                    var elapsedMs = Math.round(endAt - window.chatStartTime);
                    window.ariaFetchDoneAt = 0;
                    saveResponseTime(elapsedMs, window.ariaLastChar || currentCharacter);
                    var elapsed = (elapsedMs / 1000).toFixed(1);
                    $div.find('.aria-message-meta').append(' <span style="font-size:10px;color:#888;">('+elapsed+'s)</span>');
                }
                // Aggiorna pannello memoria dopo la risposta
                setTimeout(function(){ if (typeof refreshMemoryPanel === 'function') refreshMemoryPanel(); }, 300);
            }
        }, 20);
    }
    function addSystemMessage(text) { $messages.append($('<div class="aria-message aria-message-system"><div class="aria-message-content">'+escapeHtml(text)+'</div></div>')); scrollToBottom(); }
    function getEmotionEmoji(e) { var m={'gioia':'😊','joy':'😊','tristezza':'😢','sadness':'😢','rabbia':'😠','anger':'😠','paura':'😨','fear':'😨','amore':'❤️','romance':'❤️','flirt':'😉','neutro':'😐','neutral':'😐','sfida':'💪','challenge':'💪'}; return m[e]||'🤖'; }
    function setStatus(s) { if (!$status.length) return; var $d=$status.find('.aria-status-dot'), $t=$status.find('.aria-status-text'); $d.removeClass('disconnect typing'); if(s==='disconnected'){$d.addClass('disconnect'); $t.text('Disconnesso');} else if(s==='typing'){$d.addClass('typing'); $t.text('Sta scrivendo...');} else {$t.text('Connesso');} }
    function scrollToBottom() { if ($messages.length) { $messages.scrollTop($messages[0].scrollHeight); } }
    function escapeHtml(t) { var d=document.createElement('div'); d.textContent=t; return d.innerHTML; }
    
    function showError(msg) { $('#aria-login-error').text(msg).show(); }
    function showRegError(msg) { $('#aria-register-error').text(msg).show(); }

    function ajaxPost(data, done, fail) {
        $.ajax({ url: config.ajaxUrl || '/wp-admin/admin-ajax.php', type: 'POST', data: data,
            success: function(r) { if (typeof done === 'function') done(r); },
            error: function() { if (typeof fail === 'function') fail(); }
        });
    }

    function adultBirthYear() {
        if (config && config.birthYear && parseInt(config.birthYear, 10) > 0) return parseInt(config.birthYear, 10);
        var bd = $('#aria-register-birthdate');
        if (bd.length && bd.val() && /^\d{4}/.test(bd.val())) return parseInt(bd.val().substring(0, 4), 10);
        return 2000;
    }

    // Il backend ARIA blocca i personaggi 18+ se l'eta' non e' verificata LATO SERVER:
    // localStorage da solo non basta, quindi lo comunichiamo all'API.
    function verifyAgeOnServer() {
        if (window.ariaAgePushed) return;
        window.ariaAgePushed = true;
        ajaxPost({ action: 'aria_chat_verify_age', birth_year: adultBirthYear(), nonce: config.nonce }, function(r) {
            if (!r || !r.success) {
                // Non ancora autenticati lato ARIA: ritenta quando la sessione esiste
                window.ariaAgePushed = false;
            } else {
                addSystemMessage('Verifica eta registrata sul server.');
            }
        }, function() { window.ariaAgePushed = false; });
    }

    function doLogin() {
        var username = $('#aria-login-username').val().trim();
        var password = $('#aria-login-password').val();
        if (!username || !password) { showError('Inserisci username e password'); return; }
        ajaxPost({ action: 'aria_chat_login', username: username, password: password, nonce: config.nonce }, function(response) {
            if (response && response.success) {
                isLoggedIn = true; updateAuthUI(); hideLoginModal();
                addSystemMessage('Login riuscito!');
                if (localStorage.getItem('aria_age_verified') === 'true') verifyAgeOnServer();
            } else {
                showError((response && response.error) ? response.error : 'Login fallito');
            }
        }, function() { showError('Errore di connessione'); });
    }

    function doRegister() {
        var username = $('#aria-register-username').val().trim();
        var email = $('#aria-register-email').val().trim();
        var password = $('#aria-register-password').val();
        var birthdate = $('#aria-register-birthdate').val();
        if (!username || !email || !password || !birthdate) { showRegError('Compila tutti i campi'); return; }
        ajaxPost({ action: 'aria_chat_register', username: username, email: email, password: password, birth_date: birthdate, nonce: config.nonce }, function(response) {
            if (response && response.success) {
                isLoggedIn = true; updateAuthUI(); hideRegisterModal();
                localStorage.setItem('aria_age_verified', 'true');
                verifyAgeOnServer();
                addSystemMessage(response.message || 'Registrazione completata!');
            } else {
                showRegError((response && response.error) ? response.error : 'Registrazione fallita');
            }
        }, function() { showRegError('Errore di connessione'); });
    }

    function logout() {
        ajaxPost({ action: 'aria_chat_logout', nonce: config.nonce }, function() {
            isLoggedIn = false; updateAuthUI();
            addSystemMessage('Logout effettuato');
        });
    }

    /**
     * Tempo medio di risposta della chat corrente (utente + personaggio).
     * Il server tiene le misurazioni di ogni singola chat e restituisce la media
     * di QUELLA coppia (con allargamento al personaggio e poi al sito se i
     * campioni sono ancora pochi): la barra deve essere proporzionale al tempo
     * reale di questa chat, non a una media unica uguale per tutti.
     */
    function loadAvgResponseTime(charId) {
        var char = charId || currentCharacter || (config && config.character) || '';
        var preset = document.getElementById('aria-preset-character');
        if (!char && preset && preset.value) char = preset.value;
        ajaxPost({ action: 'aria_chat_get_avg_response_time', character_id: char }, function(r) {
            window.ariaAvgChar = char;
            if (r && r.success && r.avg_ms) {
                window.ariaAvgMs = parseInt(r.avg_ms, 10);
                window.ariaAvgScope = r.scope || '';
            }
        });
    }

    function saveResponseTime(ms, charId) {
        if (!ms || ms <= 0) return;
        var char = charId || currentCharacter || (config && config.character) || '';
        ajaxPost({ action: 'aria_chat_save_response_time', ms: ms, character_id: char }, function(r) {
            // Il server restituisce subito la nuova media: la barra successiva
            // e' gia' calibrata senza un giro di richieste in piu'.
            if (r && r.success && r.avg_ms) {
                window.ariaAvgMs = parseInt(r.avg_ms, 10);
                window.ariaAvgChar = char;
                window.ariaAvgScope = r.scope || '';
            }
        });
    }

    var progressTimer = null;

    /**
     * Barra di caricamento in attesa della risposta del modello.
     * Avanza in modo stimato sulla media reale dei tempi del server
     * (window.ariaAvgMs) e si ferma al 95% finche' non arriva la risposta.
     */
    function showProgressBar() {
        setStatus('typing');
        if (document.getElementById('aria-progress-bar')) return;
        var avg = parseInt(window.ariaAvgMs || 0, 10) || 12000;
        $messages.append(
            '<div id="aria-progress-bar" class="aria-typing-bar" role="status" aria-live="polite">' +
                '<div class="aria-typing-dots"><span></span><span></span><span></span></div>' +
                '<div class="aria-typing-track"><div class="aria-typing-fill"></div></div>' +
                '<span class="aria-typing-label">Sta scrivendo...</span>' +
            '</div>');
        scrollToBottom();
        var started = performance.now();
        var $fill = $('#aria-progress-bar .aria-typing-fill');
        progressTimer = setInterval(function () {
            var ratio = Math.min((performance.now() - started) / avg, 0.95);
            $fill.css('width', Math.round(ratio * 100) + '%');
        }, 200);
    }
    function hideProgressBar() {
        if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
        var b = document.getElementById('aria-progress-bar');
        if (!b) return;
        var fill = b.querySelector('.aria-typing-fill');
        if (fill) fill.style.width = '100%';
        setTimeout(function () { if (b && b.parentNode) b.parentNode.removeChild(b); }, 180);
    }

    function sendMessage() {
        // Per chat dedicata con carattere preimpostato
        var presetEl = document.getElementById('aria-preset-character');
        var charId = currentCharacter || (presetEl && presetEl.value ? presetEl.value : '') || ($('#aria-character-select').val() || '');
        // Se nessun personaggio selezionato ma c'è un preset hidden, usalo
        if (!charId && presetEl && presetEl.value) charId = presetEl.value;
        // Se ancora vuoto ma abbiamo un carattere preimpostato nel template dedicato
        if (!charId) {
            var hiddenChar = document.getElementById('aria-preset-character');
            if (hiddenChar && hiddenChar.value) charId = hiddenChar.value;
        }
        var text = $input.val().trim();
        if (!charId || !text) {
            alert('Seleziona un personaggio e scrivi un messaggio.');
            return;
        }
        if (localStorage.getItem('aria_age_verified') === 'true') verifyAgeOnServer();
        addUserMessage(text);
        $input.val('');
        $input.css('height', 'auto');
        window.ariaLastChar = charId;
        window.ariaUserSent = true;   // interrompe una eventuale apertura in corso
        showProgressBar();
        // Rete di sicurezza: nessuna barra puo' restare appesa all'infinito
        setTimeout(hideProgressBar, 180000);
        var responseStart = performance.now();
        window.chatStartTime = responseStart;
        var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
        var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
        var data = new FormData();
        data.append('character', charId);
        data.append('text', text);
        data.append('username', (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.username : 'Ospite');
        data.append('user_id', userId);

        inviaInStreaming(ajaxUrl, data);
    }


    /**
     * Apertura automatica: il personaggio scrive per primo.
     * Il template della stanza appare subito (0 ms); il modello lo riscrive in
     * streaming e lo sostituisce. Non riapre se la conversazione è recente.
     */
    function apriConversazione(charId) {
        if (!charId) return;
        var chiave = 'aria_open_' + charId;
        var ultimo = parseInt(localStorage.getItem(chiave) || '0', 10);
        if (ultimo && (Date.now() - ultimo) < 30 * 60 * 1000) return;

        window.ariaUserSent = false;
        var $bolla = null;
        var $testo = null;
        var parziale = '';

        function mostra(testo) {
            if (!parziale) {
                $bolla = $('<div class="aria-message aria-message-ai aria-message-opening"><div class="aria-message-content"></div><div class="aria-message-meta">' + new Date().toLocaleTimeString() + '</div></div>');
                $messages.append($bolla);
                $testo = $bolla.find('.aria-message-content');
            }
            parziale = testo;
            $testo.text(parziale);
            scrollToBottom();
        }

        var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : '/wp-admin/admin-ajax.php';
        var dati = new FormData();
        dati.append('action', 'aria_chat_opening');
        dati.append('character', charId);
        dati.append('username', (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.username : '');

        fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: dati, headers: { 'Accept': 'text/event-stream' } })
            .then(function (r) {
                if (!r.body || !r.body.getReader) return r.text().then(gestisci);
                var reader = r.body.getReader();
                var decoder = new TextDecoder('utf-8');
                var buffer = '';
                function leggi() {
                    return reader.read().then(function (res) {
                        if (res.done) { if (buffer.trim().charAt(0) === '{') gestisci(buffer); return; }
                        buffer += decoder.decode(res.value, { stream: true });
                        var p2;
                        while ((p2 = buffer.indexOf('\n\n')) !== -1) {
                            gestisci(buffer.slice(0, p2) + '\n\n');
                            buffer = buffer.slice(p2 + 2);
                        }
                        return leggi();
                    });
                }
                return leggi();
            })
            .catch(function () { /* apertura fallita: resta la chat vuota */ });

        function gestisci(corpo) {
            if (!corpo) return;
            if (corpo.trim().charAt(0) === '{') {
                try { if (JSON.parse(corpo).skip) return; } catch (e) {}
            }
            corpo.split('\n\n').forEach(function (frame) {
                if (!frame.trim()) return;
                var evento = 'message', dati2 = '';
                frame.split('\n').forEach(function (riga) {
                    if (riga.indexOf('event:') === 0) evento = riga.slice(6).trim();
                    else if (riga.indexOf('data:') === 0) dati2 += riga.slice(5).trim();
                });
                if (!dati2) return;
                var obj; try { obj = JSON.parse(dati2); } catch (e) { return; }
                if (window.ariaUserSent) return;   // l'utente ha preso la parola
                if (evento === 'template') mostra(obj.text || '');
                else if (evento === 'delta') mostra(parziale + (obj.t || ''));
                else if (evento === 'final') {
                    if ($testo) {
                        $bolla.removeClass('aria-message-opening');
                        $testo.text(obj.text || parziale);
                    }
                    localStorage.setItem(chiave, String(Date.now()));
                    scrollToBottom();
                }
            });
        }
    }

    /**
     * Invio con risposta in streaming.
     * Il primo pezzo arriva in pochi secondi e le parole si compongono mentre il
     * modello scrive. Se lo stream non parte o si rompe prima di qualsiasi testo,
     * si ricade da soli sull'invio normale: l'utente non resta mai a mani vuote.
     */
    function inviaInStreaming(ajaxUrl, data) {
        var ricevuto = false;
        var $bolla = null;
        var $testo = null;
        var aperta = false;
        var parziale = '';

        function apriBolla() {
            if (aperta) return;
            aperta = true;
            hideProgressBar();
            $bolla = $('<div class="aria-message aria-message-ai aria-message-streaming"><div class="aria-message-content"><span class="aria-caret"></span></div><div class="aria-message-meta">' + new Date().toLocaleTimeString() + '</div></div>');
            $messages.append($bolla);
            $testo = $bolla.find('.aria-message-content');
            scrollToBottom();
        }

        function scrivi(pezzo) {
            parziale += pezzo;
            if (!aperta) apriBolla();
            $testo.text(parziale);
            scrollToBottom();
        }

        function chiudi(emo, finale) {
            hideProgressBar();
            setStatus('connected');
            if (!aperta) apriBolla();
            $bolla.removeClass('aria-message-streaming');
            $testo.text((getEmotionEmoji(emo ? emo : 'neutro') + ' ') + finale);
            $bolla.find('.aria-caret').remove();
            if (window.chatStartTime) {
                var fine = window.ariaFetchDoneAt || performance.now();
                var ms = Math.round(fine - window.chatStartTime);
                window.ariaFetchDoneAt = 0;
                saveResponseTime(ms, window.ariaLastChar || currentCharacter);
                $bolla.find('.aria-message-meta').append(' <span style="font-size:10px;color:#888;">(' + (ms / 1000).toFixed(1) + 's)</span>');
            }
            scrollToBottom();
            setTimeout(function () { if (typeof refreshMemoryPanel === 'function') refreshMemoryPanel(); }, 300);
        }

        function fallback() {
            var d2 = new FormData();
            data.forEach(function (v, k) { d2.append(k, v); });
            d2.append('action', 'aria_chat_send');
            fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: d2 })
                .then(function (r) { return r.text(); })
                .then(function (t) {
                    var resp;
                    try { resp = JSON.parse(t); } catch (e) { resp = { success: false, error: 'Risposta non-JSON dal server' }; }
                    window.ariaFetchDoneAt = performance.now();
                    if (resp && resp.success) {
                        var payload = resp.data || {};
                        var txt = payload.ai_text || payload.response || '';
                        if (!txt) txt = '(nessuna risposta dal modello)';
                        if (aperta) {
                            $bolla.removeClass('aria-message-streaming');
                            $bolla.find('.aria-caret').remove();
                            $testo.text(getEmotionEmoji(payload.emotion || 'neutro') + ' ' + txt);
                            hideProgressBar();
                            setStatus('connected');
                        } else {
                            addAIMessage(txt, payload.emotion || 'neutro');
                        }
                    } else {
                        hideProgressBar();
                        addSystemMessage('Errore: ' + ((resp && typeof resp.error === 'string') ? resp.error : 'risposta non valida dal server'));
                    }
                })
                .catch(function () {
                    hideProgressBar();
                    setStatus('disconnected');
                    addSystemMessage('Errore di connessione al server chat.');
                });
        }

        data.append('action', 'aria_chat_stream');
        fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: data, headers: { 'Accept': 'text/event-stream' } })
            .then(function (r) {
                if (!r.ok || !r.body || !r.body.getReader) throw new Error('stream non disponibile');
                var reader = r.body.getReader();
                var decoder = new TextDecoder('utf-8');
                var buffer = '';
                var fine = false;

                function leggi() {
                    return reader.read().then(function (res) {
                        if (res.done) { fine = true; return; }
                        buffer += decoder.decode(res.value, { stream: true });
                        var taglio;
                        while ((taglio = buffer.indexOf('\n\n')) !== -1) {
                            var frame = buffer.slice(0, taglio);
                            buffer = buffer.slice(taglio + 2);
                            var evento = 'message';
                            var dati = '';
                            frame.split('\n').forEach(function (riga) {
                                if (riga.indexOf('event:') === 0) evento = riga.slice(6).trim();
                                else if (riga.indexOf('data:') === 0) dati += riga.slice(5).trim();
                            });
                            if (!dati) continue;
                            var obj;
                            try { obj = JSON.parse(dati); } catch (e) { continue; }
                            if (evento === 'delta' && obj.t) {
                                if (!ricevuto) { ricevuto = true; window.ariaFetchDoneAt = performance.now(); }
                                scrivi(obj.t);
                            } else if (evento === 'final') {
                                ricevuto = true;
                                window.ariaFetchDoneAt = performance.now();
                                chiudi(obj.emotion, obj.response || obj.ai_text || '(nessuna risposta)');
                                fine = true;
                            } else if (evento === 'error') {
                                if (!ricevuto) { fallback(); return; }
                                hideProgressBar();
                                if (aperta) { $bolla.removeClass('aria-message-streaming'); $bolla.find('.aria-caret').remove(); }
                                addSystemMessage('Errore: ' + (obj.error || 'risposta non valida'));
                                fine = true;
                            }
                        }
                        if (fine) return;
                        return leggi();
                    });
                }
                return leggi();
            })
            .then(function () {
                if (!ricevuto && !aperta) fallback();
            })
            .catch(function () {
                if (!ricevuto) fallback();
            });
    }

    $(document).ready(init);
    window.initAriaChat = init;
})(jQuery);


// === GESTIONE MEMORIA GRANULARE (vanilla JS, senza jQuery) ===
function toggleMemoryPanel() {
    var panel = document.getElementById('aria-memory-panel');
    if (!panel) return;
    if (panel.style.display === 'none' || panel.style.display === '') {
        panel.style.display = 'block';
        if (typeof loadMemory === 'function') loadMemory();
    } else {
        panel.style.display = 'none';
    }
}

function loadMemory() {
    var list = document.getElementById('aria-memory-list');
    if (!list) return;
    list.innerHTML = '<div style="font-size:12px;color:#777;">Caricamento...</div>';
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action', 'aria_chat_get_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    data.append('token', localStorage.getItem('aria_access_token') || '');
    fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: data })
        .then(function(r){ return r.json(); })
        .then(function(r){
            if (r && r.success && r.data) {
                var html = ''; var count = 0;
                for (var k in r.data) { if (r.data.hasOwnProperty(k)) { count++;
                    html += '<div style="font-size:12px;padding:4px 2px;border-bottom:1px solid #f0f0f0;word-break:break-word;"><b>' + String(k).replace(/</g,'<').replace(/>/g,'>') + '</b>: ' + String(r.data[k]).replace(/</g,'<').replace(/>/g,'>') + '</div>';
                }}
                if (count === 0) list.innerHTML = '<div style="font-size:12px;color:#777;">Nessuna memoria salvata. Puoi correggere qualcosa con <b>Memoria: chiave=valore</b> direttamente in chat.</div>';
                else list.innerHTML = html;
            } else {
                list.innerHTML = '<div style="font-size:12px;color:#777;">Nessuna memoria salvata.</div>';
            }
        })
        .catch(function(){ list.innerHTML = '<div style="font-size:12px;color:#d33;">Errore nel caricamento della memoria.</div>'; });
}

function saveMemoryItem() {
    var k = document.getElementById('aria-mem-key');
    var v = document.getElementById('aria-mem-val');
    if (!k || !v) return;
    var keyv = k.value.trim();
    var valv = v.value.trim();
    if (keyv === '') { alert('Inserisci una chiave'); return; }
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action', 'aria_chat_save_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    data.append('key', keyv);
    data.append('value', valv);
    data.append('token', localStorage.getItem('aria_access_token') || '');
    fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: data })
        .then(function(r){ return r.json(); })
        .then(function(r){
            if (r && r.success) {
                alert('Memoria aggiornata: ' + keyv + ' = ' + (valv === '' ? '(vuoto)' : valv));
                k.value = ''; v.value = '';
                if (typeof loadMemory === 'function') loadMemory();
            } else { alert('Errore nel salvataggio'); }
        })
        .catch(function(){ alert('Errore di connessione'); });
}

function clearAllMemory() {
    if (!confirm('Cancellare TUTTA la memoria per questo personaggio?')) return;
    var ajaxUrl = (typeof ariaChatConfig !== 'undefined' && ariaChatConfig.ajaxUrl) ? ariaChatConfig.ajaxUrl : (typeof ajaxurl !== 'undefined' ? ajaxurl : '/wp-admin/admin-ajax.php');
    var userId = (typeof ariaChatConfig !== 'undefined') ? ariaChatConfig.userId : 0;
    var charId = (typeof currentCharacter !== 'undefined') ? currentCharacter : '';
    var data = new FormData();
    data.append('action', 'aria_chat_delete_memory');
    data.append('user_id', userId);
    data.append('character_id', charId);
    data.append('token', localStorage.getItem('aria_access_token') || '');
    fetch(ajaxUrl, { method: 'POST', credentials: 'same-origin', body: data })
        .then(function(r){ return r.json(); })
        .then(function(r){
            if (r && r.success) { alert('Memoria cancellata'); if (typeof loadMemory === 'function') loadMemory(); }
            else alert('Errore');
        })
        .catch(function(){ alert('Errore'); });
}
// === FINE GESTIONE MEMORIA ===
