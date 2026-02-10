/**
 * Application entry point for HorrorBot integration client.
 *
 * Instantiates services, wires event listeners, and orchestrates
 * the login → chat flow.
 *
 * E4 migration → replaced by App.vue + router/index.ts
 */

import { ApiClient } from './api-client.js';
import { AuthService } from './auth-service.js';
import { ChatService } from './chat-service.js';
import { UI } from './ui.js';

// ------------------------------------------------------------------
// Configuration
// ------------------------------------------------------------------

// Detect API base: same origin when served from FastAPI, fallback for standalone
const API_BASE = window.location.origin.includes('localhost:8000')
  ? ''  // same origin — use relative paths
  : 'http://localhost:8000';

// ------------------------------------------------------------------
// Service instantiation
// ------------------------------------------------------------------

const api = new ApiClient(API_BASE);
const auth = new AuthService(api);
const chat = new ChatService(api, auth);

// ------------------------------------------------------------------
// Auth events
// ------------------------------------------------------------------

window.addEventListener('auth:login', (e) => {
  UI.showChatPanel();
  UI.setUsername(e.detail.username);
  UI.setSessionId(chat.sessionId);
});

window.addEventListener('auth:logout', () => {
  UI.showLoginPanel();
});

window.addEventListener('auth:expired', () => {
  auth.logout();
  UI.showError('Session expirée — veuillez vous reconnecter.');
});

window.addEventListener('auth:countdown', (e) => {
  UI.updateTokenCountdown(e.detail.seconds);
});

window.addEventListener('auth:refreshed', () => {
  UI.showToast('Token renouvelé automatiquement.');
});

window.addEventListener('api:rate-limited', (e) => {
  UI.showError(`Rate limit atteint. Réessayez dans ${e.detail.retryAfter}s.`);
});

// ------------------------------------------------------------------
// Login form
// ------------------------------------------------------------------

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  UI.hideLoginError();
  UI.setLoginLoading(true);

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  try {
    await auth.login(username, password);
  } catch (err) {
    UI.showLoginError(
      err.status === 401
        ? 'Identifiants invalides.'
        : `Erreur de connexion (${err.message}).`
    );
  } finally {
    UI.setLoginLoading(false);
  }
});

// ------------------------------------------------------------------
// Chat input
// ------------------------------------------------------------------

document.getElementById('send-btn').addEventListener('click', sendMessage);
document.getElementById('message-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const text = UI.getMessageInput();
  if (!text) return;

  UI.clearMessageInput();
  UI.addUserMessage(text);
  UI.setInputDisabled(true);
  UI.showTypingIndicator();

  const mode = UI.getMode();

  try {
    if (mode === 'sync') {
      await _sendSync(text);
    } else {
      await _sendStream(text);
    }
  } catch (err) {
    UI.hideTypingIndicator();
    if (err.status === 401) {
      auth.logout();
    } else {
      UI.showError(err.message || 'Erreur inattendue.');
    }
  } finally {
    UI.setInputDisabled(false);
    UI.setSessionId(chat.sessionId);
  }
}

async function _sendSync(text) {
  const data = await chat.sendSync(text);
  UI.hideTypingIndicator();
  UI.addBotMessage(data.response, data.intent, data.confidence);
}

async function _sendStream(text) {
  const bubble = UI.createStreamingBubble();
  UI.hideTypingIndicator();

  await chat.sendStream(
    text,
    // onChunk
    (chunk) => UI.appendToStreamingBubble(bubble, chunk),
    // onDone
    (meta) => UI.finalizeStreamingBubble(bubble, meta.intent, meta.confidence),
    // onError
    (errMsg) => UI.showError(errMsg)
  );
}

// ------------------------------------------------------------------
// Logout & New session buttons
// ------------------------------------------------------------------

document.getElementById('logout-btn').addEventListener('click', () => auth.logout());

document.getElementById('new-session-btn').addEventListener('click', () => {
  chat.newSession();
  UI.setSessionId(null);
  document.getElementById('messages').innerHTML = '';
  UI.showToast('Nouvelle session démarrée.');
});

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------

if (auth.isAuthenticated()) {
  UI.showChatPanel();
  UI.setUsername(auth.getUsername());
  UI.setSessionId(chat.sessionId);
  // Re-start countdown watcher
  auth._startExpiryWatcher();
} else {
  UI.showLoginPanel();
}
