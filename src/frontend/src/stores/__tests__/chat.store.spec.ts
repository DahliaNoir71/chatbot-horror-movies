import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat.store'

vi.mock('@/api/chat.api', () => ({
  ask: vi.fn(),
  askStream: vi.fn(),
}))

import { ask, askStream } from '@/api/chat.api'

describe('Chat Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('sendMessage', () => {
    it('adds user and assistant messages', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'Try watching The Shining!',
        intent: 'recommendation',
        confidence: 0.95,
        session_id: 'session-1',
      })

      const store = useChatStore()
      await store.sendMessage('Recommend a horror movie')

      expect(store.messages).toHaveLength(2)
      const userMsg = store.messages[0]!
      const assistantMsg = store.messages[1]!
      expect(userMsg.role).toBe('user')
      expect(userMsg.content).toBe('Recommend a horror movie')
      expect(assistantMsg.role).toBe('assistant')
      expect(assistantMsg.content).toBe('Try watching The Shining!')
      expect(assistantMsg.intent).toBe('recommendation')
      expect(assistantMsg.confidence).toBe(0.95)
    })

    it('sets isLoading during request', async () => {
      let loadingDuringRequest = false
      vi.mocked(ask).mockImplementation(() => {
        const store = useChatStore()
        loadingDuringRequest = store.isLoading
        return Promise.resolve({
          response: 'answer',
          intent: 'info',
          confidence: 0.9,
          session_id: 'session-1',
        })
      })

      const store = useChatStore()
      await store.sendMessage('test')

      expect(loadingDuringRequest).toBe(true)
      expect(store.isLoading).toBe(false)
    })

    it('handles error and sets error state', async () => {
      vi.mocked(ask).mockRejectedValue(new Error('Network error'))

      const store = useChatStore()
      await store.sendMessage('test')

      expect(store.error).toBe('Network error')
      expect(store.isLoading).toBe(false)
      expect(store.messages).toHaveLength(1) // only user message
    })

    it('persists sessionId from response', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'answer',
        intent: 'info',
        confidence: 0.9,
        session_id: 'session-abc',
      })

      const store = useChatStore()
      await store.sendMessage('test')

      expect(store.sessionId).toBe('session-abc')
    })
  })

  describe('sendMessageStream', () => {
    it('adds messages and handles stream events', async () => {
      vi.mocked(askStream).mockImplementation(async (_request, onEvent) => {
        onEvent({ type: 'chunk', content: 'Hello ' })
        onEvent({ type: 'chunk', content: 'world!' })
        onEvent({
          type: 'done',
          intent: 'greeting',
          confidence: 0.88,
          session_id: 'stream-session-1',
        })
      })

      const store = useChatStore()
      await store.sendMessageStream('Hi')

      expect(store.messages).toHaveLength(2)
      const userMsg = store.messages[0]!
      const assistantMsg = store.messages[1]!
      expect(userMsg.role).toBe('user')
      expect(assistantMsg.role).toBe('assistant')
      expect(assistantMsg.content).toBe('Hello world!')
      expect(assistantMsg.intent).toBe('greeting')
      expect(assistantMsg.confidence).toBe(0.88)
      expect(store.sessionId).toBe('stream-session-1')
      expect(store.isStreaming).toBe(false)
    })

    it('sets error on stream error event', async () => {
      vi.mocked(askStream).mockImplementation(async (_request, onEvent) => {
        onEvent({ type: 'error', content: 'Server overloaded' })
      })

      const store = useChatStore()
      await store.sendMessageStream('test')

      expect(store.error).toBe('Server overloaded')
    })
  })

  describe('stopStreaming', () => {
    it('resets isStreaming', () => {
      const store = useChatStore()
      store.isStreaming = true
      store.stopStreaming()

      expect(store.isStreaming).toBe(false)
    })
  })

  describe('clearConversation', () => {
    it('resets all state', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'answer',
        intent: 'info',
        confidence: 0.9,
        session_id: 'session-1',
      })

      const store = useChatStore()
      await store.sendMessage('test')
      store.clearConversation()

      expect(store.messages).toHaveLength(0)
      expect(store.sessionId).toBeNull()
      expect(store.error).toBeNull()
      expect(store.currentStreamContent).toBe('')
      expect(store.currentIntent).toBeNull()
    })
  })

  describe('removeMessage', () => {
    it('removes message by id', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'answer',
        intent: 'info',
        confidence: 0.9,
        session_id: 'session-1',
      })

      const store = useChatStore()
      await store.sendMessage('test')
      expect(store.messages).toHaveLength(2)
      const messageId = store.messages[0]!.id
      store.removeMessage(messageId)

      expect(store.messages).toHaveLength(1)
      expect(store.messages[0]!.role).toBe('assistant')
    })
  })

  describe('getters', () => {
    it('hasMessages returns false when empty', () => {
      const store = useChatStore()
      expect(store.hasMessages).toBe(false)
    })

    it('hasMessages returns true when messages exist', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'answer',
        intent: 'info',
        confidence: 0.9,
        session_id: 'session-1',
      })

      const store = useChatStore()
      await store.sendMessage('test')
      expect(store.hasMessages).toBe(true)
    })

    it('lastMessage returns null when empty', () => {
      const store = useChatStore()
      expect(store.lastMessage).toBeNull()
    })

    it('lastMessage returns last message', async () => {
      vi.mocked(ask).mockResolvedValue({
        response: 'last answer',
        intent: 'info',
        confidence: 0.9,
        session_id: 'session-1',
      })

      const store = useChatStore()
      await store.sendMessage('test')
      expect(store.lastMessage?.content).toBe('last answer')
    })
  })
})
