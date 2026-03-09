<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import BaseInput from '@/components/ui/BaseInput.vue'

const emit = defineEmits<{
  search: [query: string]
}>()

const query = ref('')

const debouncedSearch = useDebounceFn((value: string) => {
  emit('search', value)
}, 300)

watch(query, (value) => {
  debouncedSearch(value)
})
</script>

<template>
  <div>
    <BaseInput
      v-model="query"
      label="Rechercher un film"
      placeholder="Titre, description..."
      type="text"
    />
  </div>
</template>
