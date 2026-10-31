(function($) {
    'use strict';
    
    const config = window.ariaChatConfig || {};
    let currentCharacter = '';
    let isLoggedIn = false;
    let isConnected = true;
    
    const $container = $('.aria-chat-container');
    const $messages = $('#aria-messages');
    const $input = $('#aria-message-input');
    const $sendBtn = $('#aria-send-btn');
    const $charSelect = $('#aria-character-select');
    const $loginBtn = $('#aria-login-btn');
    const $logoutBtn = $('#aria-logout-btn');
    const $loginModal = $('#aria-login-modal');
    const $status = $('#aria-status');
    
    function init() {
        loadCharacters();
        checkAuthStatus();
        setupEventListeners();
        autoResizeInput();
    }
    
    function setupEventListeners() {
        $sendBtn.on('click', sendMessage);
        $input.on('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        $charSelect.on('change', function() {
            currentCharacter = $(this).val();
            addSystemMessage('Personaggio cambiato: ' + $(this).find('option:selected').text());
        });
        
        $loginBtn.on('click', showLoginModal);
        $logoutBtn.on('click', logout);
        $('#aria-login-submit').on('click', doLogin);
        $('#aria-login-cancel').on('click', hideLoginModal);
        
        $input.on('input', autoResizeInput);
    }
    
    function autoResizeInput() {
        $input.css('height', 'auto');
        $input[0].scrollHeight;
        $input.css('height', Math.min($input[0].scrollHeight, 100) + 'px');
    }
    
    function loadCharacters() {
        $.ajax({
            url: config.ajaxUrl,
            type: 'POST',
            data: {
                action: 'aria_chat_characters',
                nonce: config.nonce,
                limit: 100
            },
            success: function(response) {
                if (response.success && response.data) {
                    $charSelect.empty();
                    $charSelect.append('<option value="">-- Seleziona personaggio --</option>');
                    response.data.forEach(function(char) {
                        $charSelect.append(
                            $('<option></option>').val(char.id).text(char.name)
                        );
                    });
                    if (response.data.length > 0) {
                        currentCharacter = response.data[0].id;
                        $charSelect.val(currentCharacter);
                    }
                }
            },
            error: function() {
                addSystemMessage('Errore nel caricamento personaggi');
            }
        });
    }
    
    function checkAuthStatus() {
        $.ajax({
            url: config.ajaxUrl,
            type: 'POST',
            data: {
                action: 'aria_chat_auth_status',
                nonce: config.nonce
            },
            success: function(response) {
                isLoggedIn = response.isLoggedIn;
                updateAuthUI();
            }
        });
    }
    
    function updateAuthUI() {
        if (isLoggedIn) {
            $loginBtn.hide();
            $logoutBtn.show();
            addSystemMessage('Loggato come ' + config.username);
        } else {
            $loginBtn.show();
            $logoutBtn.hide();
        }
    }
    
    function showLoginModal() {
        $loginModal.show();
        $('#aria-login-error').hide();
        $('#aria-login-username').val('');
        $('#aria-login-password').val('');
    }
    
    function hideLoginModal() {
        $loginModal.hide();
    }
    
    function doLogin() {
        const username = $('#aria-login-username').val().trim();
        const password = $('#aria-login-password').val();
        
        if (!username || !password) {
            showError('Inserisci username e password');
            return;
        }
        
        $.ajax({
            url: config.ajaxUrl,
            type: 'POST',
            data: {
                action: 'aria_chat_login',
                username: username,
                password: password
            },
            success: function(response) {
                if (response.success) {
                    isLoggedIn = true;
                    updateAuthUI();
                    hideLoginModal();
                    addSystemMessage('Login riuscito!');
                } else {
                    showError(response.error || 'Login fallito');
                }
            },
            error: function() {
                showError('Errore di connessione');
            }
        });
    }
    
    function logout() {
        $.ajax({
            url: config.ajaxUrl,
            type: 'POST',
            data: {
                action: 'aria_chat_logout',
                nonce: config.nonce
            },
            success: function() {
                isLoggedIn = false;
                updateAuthUI();
                addSystemMessage('Logout effettuato');
            }
        });
    }
    
    function showError(msg) {
        $('#aria-login-error').text(msg).show();
    }
    
    function sendMessage() {
        const text = $input.val().trim();
        if (!text || !currentCharacter) {
            alert('Seleziona un personaggio e scrivi un messaggio');
            return;
        }
        
        addUserMessage(text);
        $input.val('');
        $input.css('height', 'auto');
        $sendBtn.prop('disabled', true);
        setStatus('typing');
        
        $.ajax({
            url: config.ajaxUrl,
            type: 'POST',
            data: {
                action: 'aria_chat_send',
                nonce: config.nonce,
                character: currentCharacter,
                text: text,
                username: config.username
            },
            success: function(response) {
                setStatus('connected');
                $sendBtn.prop('disabled', false);
                
                if (response.success && response.data) {
                    const aiText = response.data.response || response.data.ai_text || response.data.message || JSON.stringify(response.data);
                    const emotion = response.data.emotion || '';
                    addAIMessage(aiText, emotion);
                } else {
                    addSystemMessage('Errore: ' + (response.error || 'Risposta non valida'));
                }
            },
            error: function() {
                setStatus('disconnected');
                $sendBtn.prop('disabled', false);
                addSystemMessage('Errore di connessione al server');
            }
        });
    }
    
    function addUserMessage(text) {
        const $msg = $(`
            <div class="aria-message aria-message-user">
                <div class="aria-message-content">${escapeHtml(text)}</div>
                <div class="aria-message-meta">${new Date().toLocaleTimeString()}</div>
            </div>
        `);
        $messages.append($msg);
        scrollToBottom();
    }
    
    function addAIMessage(text, emotion) {
        const emotionEmoji = getEmotionEmoji(emotion);
        const $msg = $(`
            <div class="aria-message aria-message-ai">
                <div class="aria-message-content">${emotionEmoji} ${escapeHtml(text)}</div>
                <div class="aria-message-meta">${new Date().toLocaleTimeString()}</div>
            </div>
        `);
        $messages.append($msg);
        scrollToBottom();
    }
    
    function addSystemMessage(text) {
        const $msg = $(`
            <div class="aria-message aria-message-system">
                <div class="aria-message-content">${escapeHtml(text)}</div>
            </div>
        `);
        $messages.append($msg);
        scrollToBottom();
    }
    
    function getEmotionEmoji(emotion) {
        const emojis = {
            'gioia': '😊', 'joy': '😊',
            'tristezza': '😢', 'sadness': '😢',
            'rabbia': '😠', 'anger': '😠',
            'paura': '😨', 'fear': '😨',
            'amore': '❤️', 'romance': '❤️',
            'flirt': '😉',
            'neutro': '😐', 'neutral': '😐',
            'sfida': '💪', 'challenge': '💪'
        };
        return emojis[emotion] || '🤖';
    }
    
    function setStatus(status) {
        const $dot = $status.find('.aria-status-dot');
        const $text = $status.find('.aria-status-text');
        
        $dot.removeClass('disconnect typing');
        $text.text('Connesso');
        
        if (status === 'disconnected') {
            $dot.addClass('disconnect');
            $text.text('Disconnesso');
        } else if (status === 'typing') {
            $dot.addClass('typing');
            $text.text('Sta scrivendo...');
        }
    }
    
    function scrollToBottom() {
        $messages.scrollTop($messages[0].scrollHeight);
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    $(document).ready(init);
    
})(jQuery);
