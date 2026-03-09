import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref, computed, defineComponent } from 'vue'
import ChatView from '../chatbot/ChatView.vue'

// Stub scrollTo for jsdom
Element.prototype.scrollTo = vi.fn()

const messages = ref<
  Array<{ id: string; role: string; content: string; timestamp: Date }>
>([])
const isLoading = ref(false)
const isStreaming = ref(false)
const error = ref<string | null>(null)
const sessionId = ref<string | null>(null)
const currentStreamContent = ref('')
const hasMessages = computed(() => messages.value.length > 0)

const mockStore = {
  messages,
  isLoading,
  isStreaming,
  error,
  hasMessages,
  sessionId,
  currentStreamContent,
  sendMessageStream: vi.fn(),
  clearConversation: vi.fn(),
}

vi.mock('@/stores/chat.store', () => ({
  useChatStore: () => mockStore,
}))

vi.mock('pinia', async () => {
  const actual = await vi.importActual<typeof import('pinia')>('pinia')
  return {
    ...actual,
    storeToRefs: () => ({
      messages,
      isLoading,
      isStreaming,
      error,
      hasMessages,
      sessionId,
      currentStreamContent,
    }),
  }
})

const ChatMessageStub = defineComponent({
  name: 'ChatMessageComponent',
  props: { message: { type: Object, default: null } },
  template: '<div class="chat-message" />',
})

const ChatInputStub = defineComponent({
  name: 'ChatInput',
  props: { disabled: { type: Boolean, default: false } },
  emits: ['send'],
  template: '<div class="chat-input" />',
})

const ChatHistoryStub = defineComponent({
  name: 'ChatHistory',
  emits: ['clear'],
  template: '<div class="chat-history" />',
})

const ErrorAlertStub = defineComponent({
  name: 'ErrorAlert',
  props: {
    message: { type: String, default: '' },
    dismissible: { type: Boolean, default: false },
  },
  emits: ['dismiss'],
  template: '<div class="error-alert" />',
})

function mountChat() {
  return mount(ChatView, {
    global: {
      plugins: [createPinia()],
      stubs: {
        ChatMessageComponent: ChatMessageStub,
        ChatInput: ChatInputStub,
        ChatHistory: ChatHistoryStub,
        LoadingSpinner: { template: '<div class="loading-spinner" />' },
        ErrorAlert: ErrorAlertStub,
      },
    },
  })
}

function resetStore() {
  messages.value = []
  isLoading.value = false
  isStreaming.value = false
  error.value = null
  sessionId.value = null
  currentStreamContent.value = ''
}

describe('ChatView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    resetStore()
  })

  describe('empty state', () => {
    it('renders HorrorBot heading when no messages', () => {
      const wrapper = mountChat()
      expect(wrapper.find('h1').text()).toBe('HorrorBot')
    })

    it('shows help text when no messages', () => {
      const wrapper = mountChat()
      expect(wrapper.text()).toContain("films d'horreur")
      expect(wrapper.text()).toContain('Ctrl+N')
    })

    it('hides empty state when messages exist', () => {
      messages.value = [
        { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date() },
      ]
      const wrapper = mountChat()
      expect(wrapper.find('h1').exists()).toBe(false)
    })
  })

  describe('messages', () => {
    it('renders ChatMessageComponent for each message', () => {
      messages.value = [
        { id: 'msg-1', role: 'user', content: 'Hello', timestamp: new Date() },
        {
          id: 'msg-2',
          role: 'assistant',
          content: 'Hi there',
          timestamp: new Date(),
        },
      ]
      const wrapper = mountChat()
      expect(wrapper.findAll('.chat-message')).toHaveLength(2)
    })
  })

  describe('session badge', () => {
    it('shows "Session active" when sessionId is set', () => {
      sessionId.value = 'session-123'
      const wrapper = mountChat()
      expect(wrapper.text()).toContain('Session active')
    })

    it('hides session badge when no sessionId', () => {
      const wrapper = mountChat()
      expect(wrapper.text()).not.toContain('Session active')
    })
  })

  describe('loading state', () => {
    it('shows spinner and thinking text when isLoading', () => {
      isLoading.value = true
      const wrapper = mountChat()
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
      expect(wrapper.text()).toContain('HorrorBot réfléchit')
    })

    it('shows spinner when isStreaming', () => {
      isStreaming.value = true
      const wrapper = mountChat()
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })

    it('hides spinner when not loading', () => {
      const wrapper = mountChat()
      expect(wrapper.find('.loading-spinner').exists()).toBe(false)
    })
  })

  describe('error', () => {
    it('shows ErrorAlert when error is set', () => {
      error.value = 'Something went wrong'
      const wrapper = mountChat()
      expect(wrapper.find('.error-alert').exists()).toBe(true)
    })

    it('hides ErrorAlert when no error', () => {
      const wrapper = mountChat()
      expect(wrapper.find('.error-alert').exists()).toBe(false)
    })

    it('clears error on dismiss', async () => {
      error.value = 'Something went wrong'
      const wrapper = mountChat()
      const errorAlert = wrapper.findComponent(ErrorAlertStub)
      errorAlert.vm.$emit('dismiss')
      await flushPromises()

      // Template does chatStore.error = null which replaces ref on store object
      expect(mockStore.error).toBeNull()
    })
  })

  describe('user actions', () => {
    it('calls sendMessageStream on send event', async () => {
      const wrapper = mountChat()
      const chatInput = wrapper.findComponent(ChatInputStub)
      await chatInput.vm.$emit('send', 'Hello bot')

      expect(mockStore.sendMessageStream).toHaveBeenCalledWith('Hello bot')
    })

    it('calls clearConversation on clear event', async () => {
      const wrapper = mountChat()
      const chatHistory = wrapper.findComponent(ChatHistoryStub)
      await chatHistory.vm.$emit('clear')

      expect(mockStore.clearConversation).toHaveBeenCalled()
    })

    it('disables ChatInput when loading', () => {
      isLoading.value = true
      const wrapper = mountChat()
      const chatInput = wrapper.findComponent(ChatInputStub)
      expect(chatInput.props('disabled')).toBe(true)
    })

    it('disables ChatInput when streaming', () => {
      isStreaming.value = true
      const wrapper = mountChat()
      const chatInput = wrapper.findComponent(ChatInputStub)
      expect(chatInput.props('disabled')).toBe(true)
    })
  })

  describe('keyboard shortcut', () => {
    it('Ctrl+N calls clearConversation', async () => {
      mountChat()
      const event = new KeyboardEvent('keydown', {
        key: 'n',
        ctrlKey: true,
        bubbles: true,
      })
      document.dispatchEvent(event)
      await flushPromises()

      expect(mockStore.clearConversation).toHaveBeenCalled()
    })

    it('does not trigger on plain N key', async () => {
      mountChat()
      const event = new KeyboardEvent('keydown', {
        key: 'n',
        bubbles: true,
      })
      document.dispatchEvent(event)
      await flushPromises()

      expect(mockStore.clearConversation).not.toHaveBeenCalled()
    })
  })
})
