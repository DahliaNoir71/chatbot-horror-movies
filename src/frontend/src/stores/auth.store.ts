import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  loginUser as apiLoginUser,
  loginAdmin as apiLoginAdmin,
} from '@/api/auth.api'
import { TOKEN_KEY } from '@/api/client'
import type { UserLoginRequest, AdminLoginRequest, User } from '@/types'

const TOKEN_EXPIRY_KEY = 'horrorbot_token_expiry'
const USERNAME_KEY = 'horrorbot_username'
const ROLE_KEY = 'horrorbot_role'

function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.')
  const base64Url = parts[1] ?? ''
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
  return JSON.parse(atob(base64)) as Record<string, unknown>
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const tokenExpiry = ref<number | null>(null)
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value && !isTokenExpired())
  const authHeader = computed(() =>
    token.value ? `Bearer ${token.value}` : ''
  )
  const isAdmin = computed(() => user.value?.role === 'admin')

  function isTokenExpired(): boolean {
    if (!tokenExpiry.value) return true
    return Date.now() >= tokenExpiry.value - 60_000
  }

  function handleTokenResponse(response: {
    access_token: string
    expires_in: number
  }): void {
    token.value = response.access_token
    tokenExpiry.value = Date.now() + response.expires_in * 1000

    const payload = decodeJwtPayload(response.access_token)
    const role = (payload.role as string) || 'user'
    const username = (payload.sub as string) || ''
    user.value = { username, role }

    localStorage.setItem(TOKEN_KEY, response.access_token)
    localStorage.setItem(TOKEN_EXPIRY_KEY, String(tokenExpiry.value))
    localStorage.setItem(USERNAME_KEY, username)
    localStorage.setItem(ROLE_KEY, role)
  }

  async function login(credentials: UserLoginRequest): Promise<void> {
    const response = await apiLoginUser(credentials)
    handleTokenResponse(response)
  }

  async function loginAsAdmin(credentials: AdminLoginRequest): Promise<void> {
    const response = await apiLoginAdmin(credentials)
    handleTokenResponse(response)
  }

  function logout(): void {
    token.value = null
    tokenExpiry.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_EXPIRY_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
  }

  function initFromStorage(): void {
    const storedToken = localStorage.getItem(TOKEN_KEY)
    const storedExpiry = localStorage.getItem(TOKEN_EXPIRY_KEY)
    const storedUsername = localStorage.getItem(USERNAME_KEY)
    const storedRole = localStorage.getItem(ROLE_KEY)

    if (!storedToken || !storedExpiry) return

    const expiry = Number(storedExpiry)
    if (Date.now() >= expiry - 60_000) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(TOKEN_EXPIRY_KEY)
      localStorage.removeItem(USERNAME_KEY)
      localStorage.removeItem(ROLE_KEY)
      return
    }

    token.value = storedToken
    tokenExpiry.value = expiry
    if (storedUsername) {
      user.value = { username: storedUsername, role: storedRole || 'user' }
    }
  }

  return {
    token,
    tokenExpiry,
    user,
    isAuthenticated,
    authHeader,
    isAdmin,
    isTokenExpired,
    login,
    loginAsAdmin,
    logout,
    initFromStorage,
  }
})
