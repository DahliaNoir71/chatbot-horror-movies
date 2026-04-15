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

const hasSources = computed(() =>
  !isUser.value && props.message.sources && props.message.sources.length > 0
)

const hasTimings = computed(() =>
  !isUser.value && props.message.timings != null
)

const hasTokenUsage = computed(() =>
  !isUser.value && props.message.token_usage != null
    && Object.keys(props.message.token_usage).length > 0
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

      <!-- Benchmark: timings -->
      <div
        v-if="hasTimings"
        class="mt-2 flex flex-wrap gap-2 text-xs text-smoke-gray-400"
      >
        <span>⏱ total {{ Math.round(message.timings!.total_ms) }}ms</span>
        <span v-if="message.timings!.classification_ms">
          · classif {{ Math.round(message.timings!.classification_ms) }}ms
        </span>
        <span v-if="message.timings!.retrieval_ms">
          · retrieval {{ Math.round(message.timings!.retrieval_ms) }}ms
        </span>
        <span v-if="message.timings!.rerank_ms">
          · rerank {{ Math.round(message.timings!.rerank_ms) }}ms
        </span>
        <span v-if="message.timings!.generation_ms">
          · LLM {{ Math.round(message.timings!.generation_ms) }}ms
        </span>
      </div>

      <!-- Benchmark: token usage -->
      <div
        v-if="hasTokenUsage"
        class="mt-1 text-xs text-smoke-gray-400"
      >
        🪙 prompt {{ message.token_usage!.prompt_tokens ?? '?' }}
        · completion {{ message.token_usage!.completion_tokens ?? '?' }}
      </div>

      <!-- Benchmark: sources -->
      <div
        v-if="hasSources"
        class="mt-2 border-t border-deep-black-700 pt-2"
      >
        <p class="text-xs text-smoke-gray-400 mb-1">📚 Sources ({{ message.sources!.length }})</p>
        <ul class="space-y-1">
          <li
            v-for="(src, idx) in message.sources"
            :key="idx"
            class="text-xs text-smoke-gray-300 flex items-baseline gap-2"
          >
            <span class="font-medium">{{ src.title }}</span>
            <span v-if="src.year" class="text-smoke-gray-400">({{ src.year }})</span>
            <span class="text-smoke-gray-500">
              sim {{ (src.similarity_score * 100).toFixed(1) }}%
              <template v-if="src.rerank_score != null">
                · rerank {{ src.rerank_score.toFixed(2) }}
              </template>
            </span>
          </li>
        </ul>
      </div>
    </div>
  </article>
</template>
