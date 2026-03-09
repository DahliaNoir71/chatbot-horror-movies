<script setup lang="ts">
import { computed } from 'vue'
import type { FilmDetail } from '@/types'

interface Props {
  film: FilmDetail
}

const props = defineProps<Props>()

const posterUrl = computed(() =>
  props.film.poster_path
    ? `https://image.tmdb.org/t/p/w500${props.film.poster_path}`
    : null
)

const year = computed(() =>
  props.film.release_date ? props.film.release_date.slice(0, 4) : null
)

const formattedRuntime = computed(() => {
  if (!props.film.runtime) return null
  const h = Math.floor(props.film.runtime / 60)
  const m = props.film.runtime % 60
  return h > 0 ? `${h}h ${m}min` : `${m}min`
})

const formattedBudget = computed(() =>
  props.film.budget ? `$${props.film.budget.toLocaleString('en-US')}` : null
)

const formattedRevenue = computed(() =>
  props.film.revenue ? `$${props.film.revenue.toLocaleString('en-US')}` : null
)

const imdbUrl = computed(() =>
  props.film.imdb_id ? `https://www.imdb.com/title/${props.film.imdb_id}` : null
)
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-[300px_1fr] gap-8">
    <div class="aspect-[2/3] bg-deep-black-800 rounded-xl overflow-hidden">
      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="`Affiche du film ${film.title}`"
        class="w-full h-full object-cover"
      />
      <div
        v-else
        class="w-full h-full flex items-center justify-center text-smoke-gray-500"
        role="img"
        :aria-label="`Aucune affiche pour ${film.title}`"
      >
        <svg
          class="w-20 h-20"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
          />
        </svg>
      </div>
    </div>

    <div class="flex flex-col gap-4">
      <div>
        <h1 class="text-2xl font-bold text-smoke-gray-100">
          {{ film.title }}
          <span v-if="year" class="text-smoke-gray-400 font-normal"
            >({{ year }})</span
          >
        </h1>
        <p v-if="film.tagline" class="mt-1 text-smoke-gray-400 italic">
          {{ film.tagline }}
        </p>
      </div>

      <p v-if="film.overview" class="text-smoke-gray-300 leading-relaxed">
        {{ film.overview }}
      </p>

      <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div v-if="formattedRuntime">
          <dt class="text-smoke-gray-500">Durée</dt>
          <dd class="text-smoke-gray-200">{{ formattedRuntime }}</dd>
        </div>
        <div v-if="film.vote_average != null">
          <dt class="text-smoke-gray-500">Note</dt>
          <dd class="text-blood-red-400 font-semibold">
            {{ film.vote_average.toFixed(1) }} / 10
            <span
              v-if="film.vote_count"
              class="text-smoke-gray-500 font-normal"
            >
              ({{ film.vote_count.toLocaleString() }} votes)
            </span>
          </dd>
        </div>
        <div v-if="film.original_language">
          <dt class="text-smoke-gray-500">Langue originale</dt>
          <dd class="text-smoke-gray-200 uppercase">
            {{ film.original_language }}
          </dd>
        </div>
        <div v-if="film.status">
          <dt class="text-smoke-gray-500">Statut</dt>
          <dd class="text-smoke-gray-200">{{ film.status }}</dd>
        </div>
        <div v-if="formattedBudget">
          <dt class="text-smoke-gray-500">Budget</dt>
          <dd class="text-smoke-gray-200">{{ formattedBudget }}</dd>
        </div>
        <div v-if="formattedRevenue">
          <dt class="text-smoke-gray-500">Recettes</dt>
          <dd class="text-smoke-gray-200">{{ formattedRevenue }}</dd>
        </div>
      </dl>

      <div v-if="imdbUrl" class="mt-2">
        <a
          :href="imdbUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 text-blood-red-400 hover:text-blood-red-300 transition-colors"
        >
          Voir sur IMDb
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
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
      </div>
    </div>
  </div>
</template>
