<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types'

interface Props {
  message: ChatMessage
}

const props = defineProps<Props>()

const isUser = computed(() => props.message.role === 'user')

const ariaLabel = computed(() =>
  isUser.value
    ? `Message de vous : ${props.message.content.slice(0, 50)}`
    : `Réponse de l'assistant : ${props.message.content.slice(0, 50)}`
)

const formattedTime = computed(() =>
  props.message.timestamp.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })
)

const confidencePercent = computed(() =>
  props.message.confidence != null
    ? Math.round(props.message.confidence * 100)
    : null
)
</script>

<template>
  <article
    :aria-label="ariaLabel"
    class="flex"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[80%] rounded-lg px-4 py-3"
      :class="
        isUser
          ? 'bg-blood-red-700 text-white'
          : 'bg-deep-black-600 text-smoke-gray-100'
      "
    >
      <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>

      <div class="mt-2 flex items-center gap-3 text-xs text-smoke-gray-300">
        <time :datetime="message.timestamp.toISOString()">
          {{ formattedTime }}
        </time>

        <span
          v-if="!isUser && message.intent"
          class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-deep-black-700 text-smoke-gray-300"
        >
          {{ message.intent }}
          <span v-if="confidencePercent != null">{{ confidencePercent }}%</span>
        </span>
      </div>
    </div>
  </article>
</template>
