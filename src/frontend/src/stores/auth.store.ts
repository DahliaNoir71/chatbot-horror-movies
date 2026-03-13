import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  loginUser as apiLoginUser,
  loginAdmin as apiLoginAdmin,
} from '@/api/auth.api'
import { getTokenKey } from '@/api/client'
import type { UserLoginRequest, AdminLoginRequest, User } from '@/types'

let storagePrefix = 'horrorbot'

export function setStoragePrefix(prefix: string): void {
  storagePrefix = prefix
}

function tokenExpiryKey(): string {
  return `${storagePrefix}_token_expiry`
}

function usernameKey(): string {
  return `${storagePrefix}_username`
}

function roleKey(): string {
  return `${storagePrefix}_role`
}

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

    localStorage.setItem(getTokenKey(), response.access_token)
    localStorage.setItem(tokenExpiryKey(), String(tokenExpiry.value))
    localStorage.setItem(usernameKey(), username)
    localStorage.setItem(roleKey(), role)
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
    localStorage.removeItem(getTokenKey())
    localStorage.removeItem(tokenExpiryKey())
    localStorage.removeItem(usernameKey())
    localStorage.removeItem(roleKey())
  }

  function initFromStorage(): void {
    const storedToken = localStorage.getItem(getTokenKey())
    const storedExpiry = localStorage.getItem(tokenExpiryKey())
    const storedUsername = localStorage.getItem(usernameKey())
    const storedRole = localStorage.getItem(roleKey())

    if (!storedToken || !storedExpiry) return

    const expiry = Number(storedExpiry)
    if (Date.now() >= expiry - 60_000) {
      localStorage.removeItem(getTokenKey())
      localStorage.removeItem(tokenExpiryKey())
      localStorage.removeItem(usernameKey())
      localStorage.removeItem(roleKey())
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
