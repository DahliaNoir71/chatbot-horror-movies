import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth.store'

vi.mock('@/api/auth.api', () => ({
  loginUser: vi.fn(),
  loginAdmin: vi.fn(),
}))

import {
  loginUser as apiLoginUser,
  loginAdmin as apiLoginAdmin,
} from '@/api/auth.api'

const TOKEN_KEY = 'horrorbot_token'
const TOKEN_EXPIRY_KEY = 'horrorbot_token_expiry'
const USERNAME_KEY = 'horrorbot_username'
const ROLE_KEY = 'horrorbot_role'

/** Build a fake JWT with the given payload (no signature verification needed). */
function fakeJwt(payload: Record<string, unknown> = {}): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(
    JSON.stringify({ sub: 'testuser', role: 'user', ...payload })
  )
  return `${header}.${body}.fakesig`
}

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('stores token and user on success', async () => {
      const token = fakeJwt({ sub: 'testuser', role: 'user' })
      vi.mocked(apiLoginUser).mockResolvedValue({
        access_token: token,
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'testuser', password: 'password123' })

      expect(store.token).toBe(token)
      expect(store.user?.username).toBe('testuser')
      expect(store.user?.role).toBe('user')
      expect(store.tokenExpiry).toBeGreaterThan(Date.now())
      expect(store.isAuthenticated).toBe(true)
      expect(store.isAdmin).toBe(false)
      expect(localStorage.getItem(TOKEN_KEY)).toBe(token)
      expect(localStorage.getItem(USERNAME_KEY)).toBe('testuser')
      expect(localStorage.getItem(ROLE_KEY)).toBe('user')
    })

    it('propagates error on failure', async () => {
      vi.mocked(apiLoginUser).mockRejectedValue(
        new Error('Invalid credentials')
      )

      const store = useAuthStore()
      await expect(
        store.login({ username: 'baduser', password: 'wrongpass1' })
      ).rejects.toThrow('Invalid credentials')

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('loginAsAdmin', () => {
    it('stores token and detects admin role', async () => {
      const token = fakeJwt({ sub: 'admin', role: 'admin' })
      vi.mocked(apiLoginAdmin).mockResolvedValue({
        access_token: token,
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.loginAsAdmin({
        email: 'admin@example.com',
        password: 'password123',
      })

      expect(store.user?.role).toBe('admin')
      expect(store.isAdmin).toBe(true)
      expect(localStorage.getItem(ROLE_KEY)).toBe('admin')
    })

    it('propagates error on failure', async () => {
      vi.mocked(apiLoginAdmin).mockRejectedValue(
        new Error('Invalid credentials')
      )

      const store = useAuthStore()
      await expect(
        store.loginAsAdmin({ email: 'bad@example.com', password: 'wrongpass1' })
      ).rejects.toThrow('Invalid credentials')

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('resets state and clears localStorage', async () => {
      const token = fakeJwt()
      vi.mocked(apiLoginUser).mockResolvedValue({
        access_token: token,
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
      expect(localStorage.getItem(ROLE_KEY)).toBeNull()
    })
  })

  describe('initFromStorage', () => {
    it('restores valid token from localStorage', () => {
      const futureExpiry = Date.now() + 3600 * 1000
      localStorage.setItem(TOKEN_KEY, 'stored-token')
      localStorage.setItem(TOKEN_EXPIRY_KEY, String(futureExpiry))
      localStorage.setItem(USERNAME_KEY, 'storeduser')
      localStorage.setItem(ROLE_KEY, 'admin')

      const store = useAuthStore()
      store.initFromStorage()

      expect(store.token).toBe('stored-token')
      expect(store.tokenExpiry).toBe(futureExpiry)
      expect(store.user?.username).toBe('storeduser')
      expect(store.user?.role).toBe('admin')
      expect(store.isAuthenticated).toBe(true)
      expect(store.isAdmin).toBe(true)
    })

    it('defaults role to user when not in storage', () => {
      const futureExpiry = Date.now() + 3600 * 1000
      localStorage.setItem(TOKEN_KEY, 'stored-token')
      localStorage.setItem(TOKEN_EXPIRY_KEY, String(futureExpiry))
      localStorage.setItem(USERNAME_KEY, 'storeduser')

      const store = useAuthStore()
      store.initFromStorage()

      expect(store.user?.role).toBe('user')
      expect(store.isAdmin).toBe(false)
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
      expect(localStorage.getItem(ROLE_KEY)).toBeNull()
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
      const token = fakeJwt()
      vi.mocked(apiLoginUser).mockResolvedValue({
        access_token: token,
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'testuser', password: 'pass12345' })
      expect(store.isTokenExpired()).toBe(false)
    })
  })

  describe('authHeader', () => {
    it('returns empty string when no token', () => {
      const store = useAuthStore()
      expect(store.authHeader).toBe('')
    })

    it('returns Bearer header when token exists', async () => {
      const token = fakeJwt()
      vi.mocked(apiLoginUser).mockResolvedValue({
        access_token: token,
        token_type: 'bearer',
        expires_in: 3600,
      })

      const store = useAuthStore()
      await store.login({ username: 'testuser', password: 'pass12345' })
      expect(store.authHeader).toBe(`Bearer ${token}`)
    })
  })
})
