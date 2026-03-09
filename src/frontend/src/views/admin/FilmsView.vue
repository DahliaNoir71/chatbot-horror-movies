<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listFilms, searchFilms } from '@/api/films.api'
import type { Film, PaginatedMeta, FilmSearchResult } from '@/types'
import FilmCard from '@/components/films/FilmCard.vue'
import FilmSearch from '@/components/films/FilmSearch.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ErrorAlert from '@/components/ui/ErrorAlert.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const films = ref<Film[]>([])
const meta = ref<PaginatedMeta | null>(null)
const searchResults = ref<FilmSearchResult[]>([])
const searchQuery = ref('')
const loading = ref(false)
const error = ref('')

const PAGE_SIZE = 20

async function loadPage(page = 1) {
  loading.value = true
  error.value = ''
  try {
    const res = await listFilms(page, PAGE_SIZE)
    films.value = res.data
    meta.value = res.meta
  } catch {
    error.value = 'Impossible de charger les films.'
  } finally {
    loading.value = false
  }
}

async function onSearch(query: string) {
  searchQuery.value = query
  if (!query.trim()) {
    searchResults.value = []
    if (!films.value.length) await loadPage(1)
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await searchFilms({ query })
    searchResults.value = res.results
  } catch {
    error.value = 'Erreur lors de la recherche.'
  } finally {
    loading.value = false
  }
}

onMounted(() => loadPage(1))

const isSearchMode = () => searchQuery.value.trim().length > 0
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-smoke-gray-100">Films</h1>

    <FilmSearch @search="onSearch" />

    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner size="lg" />
    </div>

    <ErrorAlert
      v-else-if="error"
      :message="error"
      dismissible
      @dismiss="error = ''"
    />

    <!-- Search results -->
    <template v-else-if="isSearchMode()">
      <p class="text-sm text-smoke-gray-400">
        {{ searchResults.length }} résultat(s) pour « {{ searchQuery }} »
      </p>
      <div
        v-if="searchResults.length"
        class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4"
      >
        <article
          v-for="result in searchResults"
          :key="result.id"
          class="bg-deep-black-700 rounded-xl overflow-hidden hover:ring-2 hover:ring-blood-red-600 transition-all"
        >
          <RouterLink
            :to="`/films/${result.id}`"
            class="block p-4 focus:outline-none focus:ring-2 focus:ring-blood-red-500 focus:ring-inset"
          >
            <h3 class="text-sm font-semibold text-smoke-gray-100 truncate">
              {{ result.title }}
            </h3>
            <p
              v-if="result.release_date"
              class="text-xs text-smoke-gray-400 mt-1"
            >
              {{ result.release_date.slice(0, 4) }}
            </p>
            <p class="text-xs text-blood-red-400 mt-1">
              Score : {{ (result.score * 100).toFixed(0) }}%
            </p>
            <p
              v-if="result.overview"
              class="text-xs text-smoke-gray-500 mt-2 line-clamp-3"
            >
              {{ result.overview }}
            </p>
          </RouterLink>
        </article>
      </div>
      <p v-else class="text-smoke-gray-500 text-center py-8">
        Aucun résultat trouvé.
      </p>
    </template>

    <!-- Browse mode -->
    <template v-else>
      <div
        v-if="films.length"
        class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4"
      >
        <FilmCard v-for="film in films" :key="film.id" :film="film" />
      </div>
      <p v-else class="text-smoke-gray-500 text-center py-8">
        Aucun film disponible.
      </p>

      <!-- Pagination -->
      <div
        v-if="meta && meta.pages > 1"
        class="flex items-center justify-center gap-4 pt-4"
      >
        <BaseButton
          variant="secondary"
          size="sm"
          :disabled="meta.page <= 1"
          @click="loadPage(meta!.page - 1)"
        >
          Précédent
        </BaseButton>
        <span class="text-sm text-smoke-gray-400">
          Page {{ meta.page }} / {{ meta.pages }}
        </span>
        <BaseButton
          variant="secondary"
          size="sm"
          :disabled="meta.page >= meta.pages"
          @click="loadPage(meta!.page + 1)"
        >
          Suivant
        </BaseButton>
      </div>
    </template>
  </div>
</template>
