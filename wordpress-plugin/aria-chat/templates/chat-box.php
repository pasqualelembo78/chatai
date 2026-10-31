<div class="aria-chat-container" style="width: <?php echo esc_attr($atts['width']); ?>; height: <?php echo esc_attr($atts['height']); ?>;">
    
    <div class="aria-chat-header">
        <div class="aria-chat-title">
            <span class="aria-chat-emoji">🤖</span>
            <span class="aria-chat-name">Aria Chat AI</span>
        </div>
        <div class="aria-chat-controls">
            <select id="aria-character-select" class="aria-character-select">
                <option value="">Caricamento personaggi...</option>
            </select>
            <button id="aria-login-btn" class="aria-btn aria-btn-small">Login</button>
            <button id="aria-logout-btn" class="aria-btn aria-btn-small" style="display:none;">Logout</button>
        </div>
    </div>
    
    <div id="aria-login-modal" class="aria-modal" style="display:none;">
        <div class="aria-modal-content">
            <h3>Accedi ad Aria Chat</h3>
            <input type="text" id="aria-login-username" placeholder="Username" class="aria-input" />
            <input type="password" id="aria-login-password" placeholder="Password" class="aria-input" />
            <div class="aria-modal-buttons">
                <button id="aria-login-submit" class="aria-btn">Accedi</button>
                <button id="aria-login-cancel" class="aria-btn aria-btn-secondary">Annulla</button>
            </div>
            <p id="aria-login-error" class="aria-error" style="display:none;"></p>
        </div>
    </div>
    
    <div class="aria-chat-messages" id="aria-messages">
        <div class="aria-message aria-message-system">
            <div class="aria-message-content">Benvenuto in Aria Chat! Seleziona un personaggio e inizia la conversazione.</div>
        </div>
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
