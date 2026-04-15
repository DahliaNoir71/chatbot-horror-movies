import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ask, askStream } from '@/api/chat.api'
import type { ChatMessage, StreamEvent } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const sessionId = ref<string | null>(null)
  const currentStreamContent = ref('')
  const currentIntent = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  function generateId(): string {
    return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  }

  async function sendMessage(question: string): Promise<void> {
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    }
    messages.value.push(userMessage)
    isLoading.value = true
    error.value = null

    try {
      const response = await ask({
        message: question,
        session_id: sessionId.value ?? undefined,
      })
      sessionId.value = response.session_id

      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: response.response,
        intent: response.intent,
        confidence: response.confidence,
        sources: response.sources,
        timings: response.timings,
        token_usage: response.token_usage,
        timestamp: new Date(),
      }
      messages.value.push(assistantMessage)
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : 'Une erreur est survenue'
    } finally {
      isLoading.value = false
    }
  }

  async function sendMessageStream(question: string): Promise<void> {
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    }
    messages.value.push(userMessage)

    isStreaming.value = true
    error.value = null
    currentStreamContent.value = ''
    currentIntent.value = null

    const controller = new AbortController()
    abortController.value = controller

    const assistantMessage: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }
    messages.value.push(assistantMessage)
    const assistantIndex = messages.value.length - 1

    const onEvent = (event: StreamEvent) => {
      const msg = messages.value[assistantIndex]
      if (!msg) return

      switch (event.type) {
        case 'chunk':
          if (event.content) {
            currentStreamContent.value += event.content
            msg.content = currentStreamContent.value
          }
          break
        case 'done':
          if (event.session_id) {
            sessionId.value = event.session_id
          }
          if (event.intent) {
            currentIntent.value = event.intent
            msg.intent = event.intent
            msg.confidence = event.confidence
          }
          msg.sources = event.sources ?? undefined
          msg.timings = event.timings ?? undefined
          msg.token_usage = event.token_usage ?? undefined
          break
        case 'error':
          error.value = event.content ?? 'Erreur streaming'
          break
      }
    }

    try {
      await askStream(
        { message: question, session_id: sessionId.value ?? undefined },
        onEvent,
        controller.signal
      )
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        error.value = err instanceof Error ? err.message : 'Erreur streaming'
      }
    } finally {
      isStreaming.value = false
      abortController.value = null
    }
  }

  function stopStreaming(): void {
    abortController.value?.abort()
    abortController.value = null
    isStreaming.value = false
  }

  function clearConversation(): void {
    messages.value = []
    sessionId.value = null
    error.value = null
    currentStreamContent.value = ''
    currentIntent.value = null
  }

  function removeMessage(id: string): void {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  return {
    messages,
    isLoading,
    isStreaming,
    error,
    sessionId,
    currentStreamContent,
    currentIntent,
    hasMessages,
    lastMessage,
    sendMessage,
    sendMessageStream,
    stopStreaming,
    clearConversation,
    removeMessage,
  }
})
