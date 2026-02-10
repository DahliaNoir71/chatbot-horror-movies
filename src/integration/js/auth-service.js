/**
 * JWT authentication service for HorrorBot.
 *
 * Manages login, token storage (localStorage), expiry countdown,
 * and automatic token refresh before expiration.
 *
 * E4 migration → stores/auth.ts (Pinia defineStore)
 */

const TOKEN_KEY = 'horrorbot_token';
const EXPIRY_KEY = 'horrorbot_token_expiry';
const USERNAME_KEY = 'horrorbot_username';
const REFRESH_MARGIN_MS = 2 * 60 * 1000; // refresh 2 min before expiry

export class AuthService {
  /**
   * @param {import('./api-client.js').ApiClient} apiClient
   */
  constructor(apiClient) {
    this._api = apiClient;
    this._credentials = null; // stored in memory only for auto-refresh
    this._watcherInterval = null;
  }

  /**
   * Authenticate and store JWT token.
   *
   * @param {string} username
   * @param {string} password
   * @returns {Promise<{token: string, expiresIn: number}>}
   * @throws {import('./api-client.js').ApiError}
   */
  async login(username, password) {
    const { data } = await this._api.post('/api/v1/auth/token', {
      username,
      password,
    });

    const expiresAtMs = Date.now() + data.expires_in * 1000;
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(EXPIRY_KEY, String(expiresAtMs));
    localStorage.setItem(USERNAME_KEY, username);

    // Keep credentials in closure for auto-refresh (never in storage)
    this._credentials = { username, password };

    this._startExpiryWatcher();
    window.dispatchEvent(
      new CustomEvent('auth:login', { detail: { username } })
    );

    return { token: data.access_token, expiresIn: data.expires_in };
  }

  /** Clear stored token and notify listeners. */
  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRY_KEY);
    localStorage.removeItem(USERNAME_KEY);
    this._credentials = null;
    this._stopExpiryWatcher();
    window.dispatchEvent(new CustomEvent('auth:logout'));
  }

  /**
   * Get current JWT token or null if missing / expired.
   * @returns {string|null}
   */
  getToken() {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const expiry = Number(localStorage.getItem(EXPIRY_KEY) || '0');
    if (Date.now() >= expiry) {
      this.logout();
      return null;
    }
    return token;
  }

  /** @returns {boolean} */
  isAuthenticated() {
    return this.getToken() !== null;
  }

  /** @returns {string|null} */
  getUsername() {
    return localStorage.getItem(USERNAME_KEY);
  }

  /**
   * Build Authorization headers for API calls.
   * @returns {object}
   */
  getAuthHeaders() {
    const token = this.getToken();
    if (!token) return {};
    return {
      Authorization: `Bearer ${token}`,
    };
  }

  /**
   * Seconds remaining until token expires (0 if expired).
   * @returns {number}
   */
  getSecondsRemaining() {
    const expiry = Number(localStorage.getItem(EXPIRY_KEY) || '0');
    return Math.max(0, Math.floor((expiry - Date.now()) / 1000));
  }

  // -------------------------------------------------------------------
  // Auto-refresh
  // -------------------------------------------------------------------

  _startExpiryWatcher() {
    this._stopExpiryWatcher();
    this._watcherInterval = setInterval(() => this._checkExpiry(), 1000);
  }

  _stopExpiryWatcher() {
    if (this._watcherInterval) {
      clearInterval(this._watcherInterval);
      this._watcherInterval = null;
    }
  }

  async _checkExpiry() {
    const remaining = this.getSecondsRemaining();

    // Notify UI for countdown update
    window.dispatchEvent(
      new CustomEvent('auth:countdown', { detail: { seconds: remaining } })
    );

    if (remaining <= 0) {
      this.logout();
      return;
    }

    // Auto-refresh when within margin
    if (remaining * 1000 <= REFRESH_MARGIN_MS && this._credentials) {
      try {
        await this.login(this._credentials.username, this._credentials.password);
        window.dispatchEvent(new CustomEvent('auth:refreshed'));
      } catch {
        // Refresh failed — let the countdown expire naturally
      }
    }
  }
}
