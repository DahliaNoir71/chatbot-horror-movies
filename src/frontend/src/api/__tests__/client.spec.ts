import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import type { InternalAxiosRequestConfig, AxiosResponse, AxiosHeaders } from 'axios'

// Must mock before importing client
vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios')
  const instance = actual.default.create()
  const createSpy = vi.fn(() => instance)
  return {
    ...actual,
    default: {
      ...actual.default,
      create: createSpy,
      isAxiosError: actual.default.isAxiosError,
    },
  }
})

const TOKEN_KEY = 'horrorbot_token'

function getInterceptors() {
  const instance = (axios.create as ReturnType<typeof vi.fn>).mock.results[0]?.value
  return instance?.interceptors
}

describe('API Client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    // Force re-import to trigger axios.create and register interceptors
    vi.resetModules()
  })

  describe('Request interceptor', () => {
    it('adds Authorization header when token exists', async () => {
      localStorage.setItem(TOKEN_KEY, 'test-jwt-token')

      const { default: apiClient } = await import('../client')
      // Get the request interceptor by making a mock request config
      const config: InternalAxiosRequestConfig = {
        headers: new axios.AxiosHeaders(),
      }

      // Access the interceptor handlers via the instance
      const interceptors = apiClient.interceptors.request as unknown as {
        handlers: Array<{ fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }>
      }
      const handler = interceptors.handlers[0]
      const result = handler.fulfilled(config)

      expect(result.headers.Authorization).toBe('Bearer test-jwt-token')
    })

    it('does not add Authorization header when no token', async () => {
      const { default: apiClient } = await import('../client')
      const config: InternalAxiosRequestConfig = {
        headers: new axios.AxiosHeaders(),
      }

      const interceptors = apiClient.interceptors.request as unknown as {
        handlers: Array<{ fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }>
      }
      const handler = interceptors.handlers[0]
      const result = handler.fulfilled(config)

      expect(result.headers.Authorization).toBeUndefined()
    })
  })

  describe('Response interceptor', () => {
    it('clears token and redirects on 401', async () => {
      localStorage.setItem(TOKEN_KEY, 'expired-token')

      const { default: apiClient } = await import('../client')

      // Mock window.location
      const hrefSetter = vi.fn()
      Object.defineProperty(window, 'location', {
        value: { href: '' },
        writable: true,
        configurable: true,
      })
      Object.defineProperty(window.location, 'href', {
        set: hrefSetter,
        get: () => '',
        configurable: true,
      })

      const interceptors = apiClient.interceptors.response as unknown as {
        handlers: Array<{
          fulfilled: (response: AxiosResponse) => AxiosResponse
          rejected: (error: unknown) => Promise<never>
        }>
      }
      const handler = interceptors.handlers[0]

      const axiosError = new axios.AxiosError('Unauthorized', '401', undefined, undefined, {
        status: 401,
        data: {},
        statusText: 'Unauthorized',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
      })

      await expect(handler.rejected(axiosError)).rejects.toThrow()
      expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
      expect(hrefSetter).toHaveBeenCalledWith('/login')
    })

    it('passes through non-401 errors', async () => {
      const { default: apiClient } = await import('../client')

      const interceptors = apiClient.interceptors.response as unknown as {
        handlers: Array<{
          fulfilled: (response: AxiosResponse) => AxiosResponse
          rejected: (error: unknown) => Promise<never>
        }>
      }
      const handler = interceptors.handlers[0]

      const axiosError = new axios.AxiosError('Server Error', '500', undefined, undefined, {
        status: 500,
        data: {},
        statusText: 'Internal Server Error',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
      })

      await expect(handler.rejected(axiosError)).rejects.toThrow()
      // No redirect on 500
    })
  })
})
