import axios from 'axios'
import { redirectToLogin } from './auth-redirect'

let tokenKey = 'horrorbot_token'

export function setTokenKey(key: string): void {
  tokenKey = key
}

export function getTokenKey(): string {
  return tokenKey
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(tokenKey)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      if (!url.startsWith('/auth/')) {
        localStorage.removeItem(tokenKey)
        redirectToLogin()
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient
