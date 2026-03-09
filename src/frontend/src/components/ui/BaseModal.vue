<script setup lang="ts">
import { ref, watch, nextTick, useId } from 'vue'
import { useScrollLock } from '@vueuse/core'
import { useFocusTrap } from '@/composables/useFocusTrap'

interface Props {
  open: boolean
  title: string
}

const props = defineProps<Props>()

defineEmits<{
  close: []
}>()

const titleId = `modal-title-${useId()}`
const modalRef = ref<HTMLElement | null>(null)
let previouslyFocused: Element | null = null

const scrollLocked = useScrollLock(document.body)

useFocusTrap(modalRef)

watch(
  () => props.open,
  async (isOpen) => {
    scrollLocked.value = isOpen

    if (isOpen) {
      previouslyFocused = document.activeElement
      await nextTick()
      modalRef.value?.focus()
    } else {
      if (previouslyFocused instanceof HTMLElement) {
        previouslyFocused.focus()
      }
      previouslyFocused = null
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center"
    >
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-black/70"
        aria-hidden="true"
        @click="$emit('close')"
      />

      <!-- Dialog -->
      <div
        ref="modalRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        tabindex="-1"
        class="relative bg-deep-black-700 border border-smoke-gray-700 rounded-xl shadow-2xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto focus:outline-none"
        @keydown.esc="$emit('close')"
      >
        <!-- Header -->
        <div class="flex items-center justify-between mb-4">
          <h2 :id="titleId" class="text-xl font-bold text-smoke-gray-100">
            {{ title }}
          </h2>
          <button
            type="button"
            aria-label="Fermer"
            class="text-smoke-gray-400 hover:text-smoke-gray-200 transition-colors"
            @click="$emit('close')"
          >
            <svg
              class="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
              />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <slot />
      </div>
    </div>
  </Teleport>
</template>
