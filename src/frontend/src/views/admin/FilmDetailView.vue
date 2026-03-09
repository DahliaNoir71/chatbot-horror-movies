<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getFilmById } from '@/api/films.api'
import type { FilmDetail as FilmDetailType } from '@/types'
import FilmDetailComponent from '@/components/films/FilmDetail.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'

const props = defineProps<{
  id: number
}>()

const film = ref<FilmDetailType | null>(null)
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    film.value = await getFilmById(props.id)
  } catch {
    error.value = 'Film introuvable ou erreur de chargement.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <RouterLink
      to="/films"
      class="inline-flex items-center gap-1 text-sm text-smoke-gray-400 hover:text-smoke-gray-200 transition-colors"
    >
      <svg
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      Retour aux films
    </RouterLink>

    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner size="lg" />
    </div>

    <ErrorAlert
      v-else-if="error"
      :message="error"
      dismissible
      @dismiss="error = ''"
    />

    <FilmDetailComponent v-else-if="film" :film="film" />
  </div>
</template>
