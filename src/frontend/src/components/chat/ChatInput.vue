<script setup lang="ts">
import { ref, computed } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'

interface Props {
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  send: [message: string]
}>()

const message = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const canSend = computed(
  () => message.value.trim().length > 0 && !props.disabled
)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function handleSend() {
  const trimmed = message.value.trim()
  if (!trimmed || props.disabled) return

  emit('send', trimmed)
  message.value = ''

  const el = textareaRef.value
  if (el) {
    el.style.height = 'auto'
  }
}
</script>

<template>
  <div
    class="flex items-end gap-3 p-4 border-t border-deep-black-700 bg-deep-black-800"
  >
    <textarea
      ref="textareaRef"
      v-model="message"
      :disabled="disabled"
      rows="1"
      aria-label="Votre message"
      placeholder="Posez votre question sur les films d'horreur…"
      class="flex-1 resize-none rounded-lg px-4 py-3 bg-deep-black-700 text-smoke-gray-100 border border-smoke-gray-600 placeholder-smoke-gray-500 focus:outline-none focus:ring-2 focus:ring-blood-red-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
      @input="autoResize"
      @keydown="handleKeydown"
    />

    <BaseButton
      :disabled="!canSend"
      :loading="disabled"
      aria-label="Envoyer le message"
      @click="handleSend"
    >
      Envoyer
    </BaseButton>
  </div>
</template>
