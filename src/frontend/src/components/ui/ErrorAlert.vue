<script setup lang="ts">
interface Props {
  message: string
  dismissible?: boolean
}

withDefaults(defineProps<Props>(), {
  dismissible: false,
})

defineEmits<{
  dismiss: []
}>()
</script>

<template>
  <div
    role="alert"
    aria-live="assertive"
    class="bg-blood-red-900/50 border border-blood-red-600 text-blood-red-100 rounded-lg p-4 flex items-start gap-3"
  >
    <p class="flex-1">{{ message }}</p>
    <button
      v-if="dismissible"
      type="button"
      aria-label="Fermer l'alerte"
      class="text-blood-red-300 hover:text-blood-red-100 transition-colors shrink-0"
      @click="$emit('dismiss')"
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
</template>
