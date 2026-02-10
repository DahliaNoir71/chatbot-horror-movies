/**
 * Chat service for HorrorBot — sync and streaming modes.
 *
 * Handles /chat (synchronous) and /chat/stream (SSE via
 * fetch + ReadableStream, since the endpoint uses POST
 * and EventSource only supports GET).
 *
 * E4 migration → stores/chat.ts (Pinia defineStore)
 */

export class ChatService {
  /**
   * @param {import('./api-client.js').ApiClient} apiClient
   * @param {import('./auth-service.js').AuthService} authService
   */
  constructor(apiClient, authService) {
    this._api = apiClient;
    this._auth = authService;
    this._sessionId = sessionStorage.getItem('horrorbot_session_id') || null;
  }

  /** @returns {string|null} Current session UUID */
  get sessionId() {
    return this._sessionId;
  }

  /** Start a new conversation (clear session). */
  newSession() {
    this._sessionId = null;
    sessionStorage.removeItem('horrorbot_session_id');
  }

  /**
   * Send a message via the synchronous /chat endpoint.
   *
   * @param {string} message
   * @returns {Promise<{response: string, intent: string, confidence: number, session_id: string}>}
   */
  async sendSync(message) {
    const headers = this._auth.getAuthHeaders();
    const body = { message };
    if (this._sessionId) body.session_id = this._sessionId;

    const { data } = await this._api.post('/api/v1/chat', body, headers);

    this._updateSessionId(data.session_id);
    return data;
  }

  /**
   * Send a message via the streaming /chat/stream endpoint.
   *
   * Uses fetch + ReadableStream to parse SSE events from a POST
   * response (EventSource only supports GET).
   *
   * @param {string} message
   * @param {(text: string) => void} onChunk  - Called for each text fragment
   * @param {(meta: {intent: string, confidence: number, session_id: string}) => void} onDone
   * @param {(error: string) => void} onError
   */
  async sendStream(message, onChunk, onDone, onError) {
    const headers = this._auth.getAuthHeaders();
    const body = { message };
    if (this._sessionId) body.session_id = this._sessionId;

    let resp;
    try {
      resp = await this._api.postStream('/api/v1/chat/stream', body, headers);
    } catch (err) {
      onError(err.message || 'Connection failed');
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop(); // keep incomplete tail

        for (const block of blocks) {
          this._processSSEBlock(block, onChunk, onDone, onError);
        }
      }

      // Process any remaining data in buffer
      if (buffer.trim()) {
        this._processSSEBlock(buffer, onChunk, onDone, onError);
      }
    } catch (err) {
      onError(`Stream interrupted: ${err.message}`);
    }
  }

  /**
   * Parse a single SSE block and dispatch to appropriate callback.
   * @private
   */
  _processSSEBlock(block, onChunk, onDone, onError) {
    for (const line of block.split('\n')) {
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;

      let event;
      try {
        event = JSON.parse(raw);
      } catch {
        continue;
      }

      switch (event.type) {
        case 'chunk':
          if (event.content) onChunk(event.content);
          break;
        case 'done':
          this._updateSessionId(event.session_id);
          onDone({
            intent: event.intent,
            confidence: event.confidence,
            session_id: event.session_id,
          });
          break;
        case 'error':
          onError(event.content || 'Unknown streaming error');
          break;
      }
    }
  }

  /** @private */
  _updateSessionId(sid) {
    if (sid) {
      this._sessionId = sid;
      sessionStorage.setItem('horrorbot_session_id', sid);
    }
  }
}
