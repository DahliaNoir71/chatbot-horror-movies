import apiClient, { getTokenKey } from './client'
import { redirectToLogin } from './auth-redirect'
import type { ChatRequest, ChatResponse, StreamEvent } from '@/types'

export function ask(request: ChatRequest): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>('/chat', request).then((r) => r.data)
}

export async function askStream(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const token = localStorage.getItem(getTokenKey())
  const response = await fetch(`${import.meta.env.VITE_API_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(getTokenKey())
      redirectToLogin()
    }
    throw new Error(`Stream request failed: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('ReadableStream not supported')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue

        const json = trimmed.slice(5).trim()
        if (!json) continue

        try {
          const event: StreamEvent = JSON.parse(json)
          onEvent(event)
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
