import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth.store'

vi.mock('@/api/auth.api', () => ({
  login: vi.fn(),
}))

import { login as apiLogin } from '@/api/auth.api'

const TOKEN_KEY = 'horrorbot_token'
const TOKEN_EXPIRY_KEY = 'horrorbot_token_expiry'
const USERNAME_KEY = 'horrorbot_username'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('stores token and user on success', async () => {
      vi.mocked(apiLogin).mockResolvedValue({
        access_token: 'jwt-token-123',
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'testuser', password: 'password123' })

      expect(store.token).toBe('jwt-token-123')
      expect(store.user?.username).toBe('testuser')
      expect(store.tokenExpiry).toBeGreaterThan(Date.now())
      expect(store.isAuthenticated).toBe(true)
      expect(localStorage.getItem(TOKEN_KEY)).toBe('jwt-token-123')
      expect(localStorage.getItem(USERNAME_KEY)).toBe('testuser')
    })

    it('propagates error on failure', async () => {
      vi.mocked(apiLogin).mockRejectedValue(new Error('Invalid credentials'))

      const store = useAuthStore()
      await expect(
        store.login({ username: 'bad', password: 'wrong' })
      ).rejects.toThrow('Invalid credentials')

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('resets state and clears localStorage', async () => {
      vi.mocked(apiLogin).mockResolvedValue({
        access_token: 'jwt-token-123',
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'testuser', password: 'password123' })
      store.logout()

      expect(store.token).toBeNull()
      expect(store.tokenExpiry).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
      expect(localStorage.getItem(TOKEN_EXPIRY_KEY)).toBeNull()
      expect(localStorage.getItem(USERNAME_KEY)).toBeNull()
    })
  })

  describe('initFromStorage', () => {
    it('restores valid token from localStorage', () => {
      const futureExpiry = Date.now() + 3600 * 1000
      localStorage.setItem(TOKEN_KEY, 'stored-token')
      localStorage.setItem(TOKEN_EXPIRY_KEY, String(futureExpiry))
      localStorage.setItem(USERNAME_KEY, 'storeduser')

      const store = useAuthStore()
      store.initFromStorage()

      expect(store.token).toBe('stored-token')
      expect(store.tokenExpiry).toBe(futureExpiry)
      expect(store.user?.username).toBe('storeduser')
      expect(store.isAuthenticated).toBe(true)
    })

    it('rejects expired token (60s margin)', () => {
      const pastExpiry = Date.now() + 30_000 // 30s left, within 60s margin
      localStorage.setItem(TOKEN_KEY, 'expired-token')
      localStorage.setItem(TOKEN_EXPIRY_KEY, String(pastExpiry))
      localStorage.setItem(USERNAME_KEY, 'user')

      const store = useAuthStore()
      store.initFromStorage()

      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    })

    it('does nothing when no token in storage', () => {
      const store = useAuthStore()
      store.initFromStorage()

      expect(store.token).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('isTokenExpired', () => {
    it('returns true when no expiry set', () => {
      const store = useAuthStore()
      expect(store.isTokenExpired()).toBe(true)
    })

    it('returns false for valid token', async () => {
      vi.mocked(apiLogin).mockResolvedValue({
        access_token: 'token',
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'user', password: 'pass' })
      expect(store.isTokenExpired()).toBe(false)
    })
  })

  describe('authHeader', () => {
    it('returns empty string when no token', () => {
      const store = useAuthStore()
      expect(store.authHeader).toBe('')
    })

    it('returns Bearer header when token exists', async () => {
      vi.mocked(apiLogin).mockResolvedValue({
        access_token: 'my-token',
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'user', password: 'pass' })
      expect(store.authHeader).toBe('Bearer my-token')
    })
  })
})
