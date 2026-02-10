/**
 * DOM manipulation module for HorrorBot integration client.
 *
 * Handles message bubbles, intent badges, typing indicators,
 * and panel transitions.  Pure DOM — no framework dependency.
 *
 * E4 migration → replaced by ChatView.vue + LoginView.vue components
 */

/** Intent → badge colour mapping. */
const INTENT_COLORS = {
  horror_recommendation: '#cc0000',
  horror_trivia: '#228822',
  horror_discussion: '#8844cc',
  film_details: '#cc8800',
  greeting: '#666666',
  farewell: '#666666',
  out_of_scope: '#444444',
};

export const UI = {
  // ------------------------------------------------------------------
  // Panel visibility
  // ------------------------------------------------------------------

  showLoginPanel() {
    _el('login-panel').classList.remove('hidden');
    _el('chat-panel').classList.add('hidden');
  },

  showChatPanel() {
    _el('login-panel').classList.add('hidden');
    _el('chat-panel').classList.remove('hidden');
    _el('message-input').focus();
  },

  // ------------------------------------------------------------------
  // Header / status
  // ------------------------------------------------------------------

  /** @param {string} username */
  setUsername(username) {
    _el('display-username').textContent = username;
  },

  /** @param {string|null} sid */
  setSessionId(sid) {
    _el('display-session').textContent = sid ? sid.slice(0, 8) + '...' : '--';
  },

  /** @param {number} seconds */
  updateTokenCountdown(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    _el('token-countdown').textContent = `${m}:${String(s).padStart(2, '0')}`;
  },

  // ------------------------------------------------------------------
  // Login form
  // ------------------------------------------------------------------

  /** @param {string} msg */
  showLoginError(msg) {
    const el = _el('login-error');
    el.textContent = msg;
    el.classList.remove('hidden');
  },

  hideLoginError() {
    _el('login-error').classList.add('hidden');
  },

  setLoginLoading(loading) {
    _el('login-btn').disabled = loading;
    _el('login-btn').textContent = loading ? 'Connexion...' : 'Se connecter';
  },

  // ------------------------------------------------------------------
  // Messages
  // ------------------------------------------------------------------

  /**
   * Add a user message bubble (right-aligned).
   * @param {string} text
   */
  addUserMessage(text) {
    const bubble = _createBubble('user');
    bubble.querySelector('.bubble-text').textContent = text;
    _appendMessage(bubble);
  },

  /**
   * Add a complete bot message bubble (left-aligned).
   * @param {string} text
   * @param {string} intent
   * @param {number} confidence
   */
  addBotMessage(text, intent, confidence) {
    const bubble = _createBubble('bot');
    bubble.querySelector('.bubble-text').textContent = text;
    bubble.appendChild(_createIntentBadge(intent, confidence));
    _appendMessage(bubble);
  },

  /**
   * Create an empty bot bubble for progressive streaming.
   * @returns {HTMLElement}
   */
  createStreamingBubble() {
    const bubble = _createBubble('bot');
    _appendMessage(bubble);
    return bubble;
  },

  /**
   * Append a text chunk to a streaming bubble.
   * @param {HTMLElement} bubble
   * @param {string} text
   */
  appendToStreamingBubble(bubble, text) {
    bubble.querySelector('.bubble-text').textContent += text;
    _scrollToBottom();
  },

  /**
   * Finalise a streaming bubble with intent badge.
   * @param {HTMLElement} bubble
   * @param {string} intent
   * @param {number} confidence
   */
  finalizeStreamingBubble(bubble, intent, confidence) {
    bubble.appendChild(_createIntentBadge(intent, confidence));
    _scrollToBottom();
  },

  // ------------------------------------------------------------------
  // Typing indicator
  // ------------------------------------------------------------------

  showTypingIndicator() {
    _el('typing-indicator').classList.remove('hidden');
    _scrollToBottom();
  },

  hideTypingIndicator() {
    _el('typing-indicator').classList.add('hidden');
  },

  // ------------------------------------------------------------------
  // Toast / errors
  // ------------------------------------------------------------------

  /** @param {string} msg */
  showError(msg) {
    _showToast(msg, 'error');
  },

  /** @param {string} msg */
  showToast(msg) {
    _showToast(msg, 'info');
  },

  // ------------------------------------------------------------------
  // Input
  // ------------------------------------------------------------------

  /** @returns {string} */
  getMessageInput() {
    return _el('message-input').value.trim();
  },

  clearMessageInput() {
    _el('message-input').value = '';
  },

  setInputDisabled(disabled) {
    _el('message-input').disabled = disabled;
    _el('send-btn').disabled = disabled;
  },

  /** @returns {'sync'|'stream'} */
  getMode() {
    return _el('mode-stream').checked ? 'stream' : 'sync';
  },
};

// ====================================================================
// Private helpers
// ====================================================================

/** @param {string} id @returns {HTMLElement} */
function _el(id) {
  return document.getElementById(id);
}

/**
 * Create a message bubble element.
 * @param {'user'|'bot'} role
 * @returns {HTMLElement}
 */
function _createBubble(role) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = `bubble ${role}-bubble`;

  const textEl = document.createElement('span');
  textEl.className = 'bubble-text';
  bubble.appendChild(textEl);

  wrap.appendChild(bubble);
  return wrap;
}

/**
 * Create a coloured intent badge pill.
 * @param {string} intent
 * @param {number} confidence
 * @returns {HTMLElement}
 */
function _createIntentBadge(intent, confidence) {
  const badge = document.createElement('span');
  badge.className = 'intent-badge';
  badge.style.backgroundColor = INTENT_COLORS[intent] || '#555';
  badge.textContent = `${intent} (${(confidence * 100).toFixed(0)}%)`;
  return badge;
}

function _appendMessage(el) {
  const container = _el('messages');
  container.appendChild(el);
  _scrollToBottom();
}

function _scrollToBottom() {
  const container = _el('messages');
  container.scrollTop = container.scrollHeight;
}

/**
 * Show a transient toast notification.
 * @param {string} msg
 * @param {'info'|'error'} type
 */
function _showToast(msg, type) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);

  // Trigger CSS animation
  requestAnimationFrame(() => toast.classList.add('show'));

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
