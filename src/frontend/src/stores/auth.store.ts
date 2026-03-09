import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin } from '@/api/auth.api'
import { TOKEN_KEY } from '@/api/client'
import type { LoginRequest, User } from '@/types'

const TOKEN_EXPIRY_KEY = 'horrorbot_token_expiry'
const USERNAME_KEY = 'horrorbot_username'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const tokenExpiry = ref<number | null>(null)
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value && !isTokenExpired())
  const authHeader = computed(() =>
    token.value ? `Bearer ${token.value}` : ''
  )

  function isTokenExpired(): boolean {
    if (!tokenExpiry.value) return true
    return Date.now() >= tokenExpiry.value - 60_000
  }

  async function login(credentials: LoginRequest): Promise<void> {
    const response = await apiLogin(credentials)
    token.value = response.access_token
    tokenExpiry.value = Date.now() + response.expires_in * 1000
    user.value = { username: credentials.username }

    localStorage.setItem(TOKEN_KEY, response.access_token)
    localStorage.setItem(TOKEN_EXPIRY_KEY, String(tokenExpiry.value))
    localStorage.setItem(USERNAME_KEY, credentials.username)
  }

  function logout(): void {
    token.value = null
    tokenExpiry.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_EXPIRY_KEY)
    localStorage.removeItem(USERNAME_KEY)
  }

  function initFromStorage(): void {
    const storedToken = localStorage.getItem(TOKEN_KEY)
    const storedExpiry = localStorage.getItem(TOKEN_EXPIRY_KEY)
    const storedUsername = localStorage.getItem(USERNAME_KEY)

    if (!storedToken || !storedExpiry) return

    const expiry = Number(storedExpiry)
    if (Date.now() >= expiry - 60_000) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(TOKEN_EXPIRY_KEY)
      localStorage.removeItem(USERNAME_KEY)
      return
    }

    token.value = storedToken
    tokenExpiry.value = expiry
    if (storedUsername) {
      user.value = { username: storedUsername }
    }
  }

  return {
    token,
    tokenExpiry,
    user,
    isAuthenticated,
    authHeader,
    isTokenExpired,
    login,
    logout,
    initFromStorage,
  }
})
