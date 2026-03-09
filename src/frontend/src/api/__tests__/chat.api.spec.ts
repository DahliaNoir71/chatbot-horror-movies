import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { askStream } from '../chat.api'
import { TOKEN_KEY } from '../client'

function createSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

function mockFetchSSE(chunks: string[]) {
  vi.mocked(fetch).mockResolvedValue({
    ok: true,
    status: 200,
    body: createSSEStream(chunks),
  } as unknown as Response)
}

describe('askStream', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
    import.meta.env.VITE_API_URL = 'http://localhost:8000'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  describe('SSE event handling', () => {
    it('receives chunk events correctly', async () => {
      mockFetchSSE(['data: {"type":"chunk","content":"Hello"}\n'])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledOnce()
      expect(onEvent).toHaveBeenCalledWith({ type: 'chunk', content: 'Hello' })
    })

    it('receives done event with metadata', async () => {
      mockFetchSSE([
        'data: {"type":"done","intent":"recommendation","confidence":0.95,"session_id":"s1"}\n',
      ])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledWith({
        type: 'done',
        intent: 'recommendation',
        confidence: 0.95,
        session_id: 's1',
      })
    })

    it('receives error event', async () => {
      mockFetchSSE(['data: {"type":"error","content":"Internal error"}\n'])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledWith({
        type: 'error',
        content: 'Internal error',
      })
    })

    it('accumulates multiple events in order', async () => {
      mockFetchSSE([
        'data: {"type":"chunk","content":"A"}\ndata: {"type":"chunk","content":"B"}\ndata: {"type":"done","intent":"info"}\n',
      ])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledTimes(3)
      expect(onEvent.mock.calls[0]![0]).toEqual({ type: 'chunk', content: 'A' })
      expect(onEvent.mock.calls[1]![0]).toEqual({ type: 'chunk', content: 'B' })
      expect(onEvent.mock.calls[2]![0]).toEqual({
        type: 'done',
        intent: 'info',
      })
    })

    it('skips malformed SSE lines', async () => {
      mockFetchSSE([
        'not-sse-line\ndata: \ndata: {invalid-json}\ndata: {"type":"chunk","content":"ok"}\n',
      ])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledOnce()
      expect(onEvent).toHaveBeenCalledWith({ type: 'chunk', content: 'ok' })
    })

    it('handles partial lines split across stream chunks', async () => {
      mockFetchSSE(['data: {"type":"chu', 'nk","content":"split"}\n'])
      const onEvent = vi.fn()

      await askStream({ message: 'hi' }, onEvent)

      expect(onEvent).toHaveBeenCalledOnce()
      expect(onEvent).toHaveBeenCalledWith({ type: 'chunk', content: 'split' })
    })
  })

  describe('fetch configuration', () => {
    it('sends Authorization header when token exists', async () => {
      localStorage.setItem(TOKEN_KEY, 'my-jwt')
      mockFetchSSE([])

      await askStream({ message: 'hi' }, vi.fn())

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/chat/stream',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            Authorization: 'Bearer my-jwt',
          }),
        })
      )
    })

    it('does not send Authorization header when no token', async () => {
      mockFetchSSE([])

      await askStream({ message: 'hi' }, vi.fn())

      const callArgs = vi.mocked(fetch).mock.calls[0]!
      const headers = callArgs[1]?.headers as Record<string, string>
      expect(headers).not.toHaveProperty('Authorization')
    })
  })

  describe('error handling', () => {
    it('throws on non-ok response', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 500,
      } as Response)

      await expect(askStream({ message: 'hi' }, vi.fn())).rejects.toThrow(
        'Stream request failed: 500'
      )
    })

    it('clears token and redirects on 401', async () => {
      localStorage.setItem(TOKEN_KEY, 'expired-token')

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

      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
      } as Response)

      await expect(askStream({ message: 'hi' }, vi.fn())).rejects.toThrow(
        'Stream request failed: 401'
      )
      expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
      expect(hrefSetter).toHaveBeenCalledWith('/login')
    })

    it('throws when response body is null', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 200,
        body: null,
      } as unknown as Response)

      await expect(askStream({ message: 'hi' }, vi.fn())).rejects.toThrow(
        'ReadableStream not supported'
      )
    })
  })

  describe('abort support', () => {
    it('passes AbortSignal to fetch', async () => {
      mockFetchSSE([])
      const controller = new AbortController()

      await askStream({ message: 'hi' }, vi.fn(), controller.signal)

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          signal: controller.signal,
        })
      )
    })
  })
})
