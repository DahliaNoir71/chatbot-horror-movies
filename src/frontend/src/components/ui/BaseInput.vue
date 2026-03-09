<script setup lang="ts">
import { useId } from 'vue'

interface Props {
  modelValue: string
  type?: 'text' | 'email' | 'password' | 'number'
  label: string
  error?: string | null
  placeholder?: string
  required?: boolean
}

withDefaults(defineProps<Props>(), {
  type: 'text',
  error: null,
  placeholder: '',
  required: false,
})

defineEmits<{
  'update:modelValue': [value: string]
}>()

const id = useId()
const inputId = `input-${id}`
const errorId = `error-${id}`
</script>

<template>
  <div>
    <label
      :for="inputId"
      class="block text-sm font-medium text-smoke-gray-200 mb-1"
    >
      {{ label
      }}<span v-if="required" class="text-blood-red-400 ml-1" aria-hidden="true"
        >*</span
      >
    </label>
    <input
      :id="inputId"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :required="required"
      :aria-invalid="!!error"
      :aria-describedby="error ? errorId : undefined"
      class="w-full bg-deep-black-700 border text-smoke-gray-100 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blood-red-500 focus:border-blood-red-500 placeholder-smoke-gray-500 transition-colors"
      :class="error ? 'border-blood-red-500' : 'border-smoke-gray-600'"
      @input="
        $emit('update:modelValue', ($event.target as HTMLInputElement).value)
      "
    />
    <p
      v-if="error"
      :id="errorId"
      role="alert"
      class="mt-1 text-sm text-blood-red-400"
    >
      {{ error }}
    </p>
  </div>
</template>
