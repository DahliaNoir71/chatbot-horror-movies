<script setup lang="ts">
import { computed } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const isDisabled = computed(() => props.disabled || props.loading)

const variantClasses: Record<string, string> = {
  primary:
    'bg-blood-red-600 hover:bg-blood-red-500 text-white focus:ring-blood-red-400',
  secondary:
    'bg-deep-black-600 hover:bg-deep-black-500 text-smoke-gray-200 border border-smoke-gray-600 focus:ring-smoke-gray-400',
  danger:
    'bg-blood-red-800 hover:bg-blood-red-700 text-blood-red-100 focus:ring-blood-red-500',
  ghost:
    'bg-transparent hover:bg-deep-black-700 text-smoke-gray-300 focus:ring-smoke-gray-500',
}

const sizeClasses: Record<string, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
}

const buttonClasses = computed(() => [
  'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
  'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-deep-black-800',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  variantClasses[props.variant],
  sizeClasses[props.size],
])

function handleClick(event: MouseEvent) {
  if (!isDisabled.value) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    :class="buttonClasses"
    :disabled="isDisabled"
    :aria-busy="loading"
    :aria-disabled="isDisabled"
    @click="handleClick"
  >
    <span class="relative inline-flex items-center gap-2">
      <span :class="{ 'opacity-0': loading }">
        <slot />
      </span>
      <LoadingSpinner
        v-if="loading"
        size="sm"
        class="absolute inset-0 m-auto"
      />
    </span>
  </button>
</template>
