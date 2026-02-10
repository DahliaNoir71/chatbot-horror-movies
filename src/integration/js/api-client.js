/**
 * Generic HTTP client for HorrorBot API.
 *
 * Wraps `fetch` with JSON handling, auth headers, and centralised
 * error management.  Emits CustomEvents for cross-cutting concerns
 * (token expiry, rate limiting) so the UI layer stays decoupled.
 *
 * E4 migration → services/api.ts
 */

export class ApiClient {
  /**
   * @param {string} baseUrl - API base URL (e.g. "http://localhost:8000")
   */
  constructor(baseUrl) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  /**
   * POST JSON request returning parsed response.
   *
   * @param {string} path    - API path (e.g. "/api/v1/chat")
   * @param {object} data    - Request body
   * @param {object} headers - Extra headers (typically auth)
   * @returns {Promise<{ok: boolean, status: number, data: object}>}
   */
  async post(path, data, headers = {}) {
    const url = `${this.baseUrl}${path}`;
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify(data),
      });

      if (!resp.ok) {
        this._handleHttpError(resp.status, resp);
      }

      const json = await resp.json();
      return { ok: true, status: resp.status, data: json };
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(0, `Network error: ${err.message}`);
    }
  }

  /**
   * POST request that returns the raw Response for streaming.
   *
   * The caller is responsible for reading the body via
   * `response.body.getReader()`.
   *
   * @param {string} path
   * @param {object} data
   * @param {object} headers
   * @returns {Promise<Response>}
   */
  async postStream(path, data, headers = {}) {
    const url = `${this.baseUrl}${path}`;
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify(data),
      });

      if (!resp.ok) {
        this._handleHttpError(resp.status, resp);
      }

      return resp;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(0, `Network error: ${err.message}`);
    }
  }

  /**
   * Central HTTP error handler — dispatches CustomEvents.
   * @param {number} status
   * @param {Response} resp
   */
  _handleHttpError(status, resp) {
    if (status === 401) {
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
    if (status === 429) {
      const retryAfter = resp.headers.get('Retry-After') || '60';
      window.dispatchEvent(
        new CustomEvent('api:rate-limited', { detail: { retryAfter: Number(retryAfter) } })
      );
    }
    throw new ApiError(status, `HTTP ${status}`);
  }
}

/**
 * Typed API error with HTTP status code.
 */
export class ApiError extends Error {
  /**
   * @param {number} status
   * @param {string} message
   */
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
