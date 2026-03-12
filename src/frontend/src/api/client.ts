import axios from 'axios'
import { redirectToLogin } from './auth-redirect'

const TOKEN_KEY = 'horrorbot_token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
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
        localStorage.removeItem(TOKEN_KEY)
        redirectToLogin()
      }
    }
    return Promise.reject(error)
  }
)

export { TOKEN_KEY }
export default apiClient
