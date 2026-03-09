<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chat.store'
import ChatMessageComponent from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ChatHistory from '@/components/chat/ChatHistory.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const chatStore = useChatStore()
const {
  messages,
  isLoading,
  isStreaming,
  error,
  hasMessages,
  sessionId,
  currentStreamContent,
} = storeToRefs(chatStore)

const messagesContainer = ref<HTMLElement | null>(null)

function scrollToBottom() {
  const el = messagesContainer.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}

watch(
  () => messages.value.length,
  () => {
    nextTick(scrollToBottom)
  }
)

watch(currentStreamContent, () => {
  nextTick(scrollToBottom)
})

function handleSend(message: string) {
  chatStore.sendMessageStream(message)
}

function handleClear() {
  chatStore.clearConversation()
}

function handleKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
    event.preventDefault()
    handleClear()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="flex flex-1 flex-col">
    <div
      class="flex items-center justify-between border-b border-deep-black-700 px-4 py-3"
    >
      <ChatHistory @clear="handleClear" />
      <span
        v-if="sessionId"
        class="rounded-full bg-deep-black-700 px-3 py-1 text-xs text-smoke-gray-400"
      >
        Session active
      </span>
    </div>

    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4"
      aria-live="polite"
    >
      <div v-if="!hasMessages" class="flex h-full items-center justify-center">
        <div class="max-w-md text-center">
          <h1 class="mb-3 text-2xl font-bold text-smoke-gray-100">HorrorBot</h1>
          <p class="text-smoke-gray-400">
            Posez-moi vos questions sur les films d'horreur : recommandations,
            anecdotes, analyses…
          </p>
          <p class="mt-2 text-xs text-smoke-gray-500">
            Ctrl+N pour une nouvelle conversation
          </p>
        </div>
      </div>

      <ChatMessageComponent
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <div
        v-if="isLoading || isStreaming"
        class="flex items-center gap-2 text-smoke-gray-400"
      >
        <LoadingSpinner size="sm" />
        <span class="text-sm">HorrorBot réfléchit…</span>
      </div>
    </div>

    <ErrorAlert
      v-if="error"
      :message="error"
      :dismissible="true"
      class="mx-4 mb-2"
      @dismiss="chatStore.error = null"
    />

    <ChatInput :disabled="isLoading || isStreaming" @send="handleSend" />
  </div>
</template>
