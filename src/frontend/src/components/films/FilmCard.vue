<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { Film } from '@/types'

interface Props {
  film: Film
}

const props = defineProps<Props>()

const posterUrl = computed(() =>
  props.film.poster_path
    ? `https://image.tmdb.org/t/p/w300${props.film.poster_path}`
    : null
)

const year = computed(() =>
  props.film.release_date ? props.film.release_date.slice(0, 4) : 'N/A'
)

const rating = computed(() =>
  props.film.vote_average != null ? props.film.vote_average.toFixed(1) : '—'
)
</script>

<template>
  <article
    class="bg-deep-black-700 rounded-xl overflow-hidden hover:ring-2 hover:ring-blood-red-600 transition-all"
  >
    <RouterLink
      :to="`/films/${film.id}`"
      class="block focus:outline-none focus:ring-2 focus:ring-blood-red-500 focus:ring-inset"
    >
      <div class="aspect-2/3 bg-deep-black-800">
        <img
          v-if="posterUrl"
          :src="posterUrl"
          :alt="`Affiche du film ${film.title}`"
          class="w-full h-full object-cover"
          loading="lazy"
        />
        <div
          v-else
          class="w-full h-full flex items-center justify-center text-smoke-gray-500"
          :aria-label="`Aucune affiche pour ${film.title}`"
        >
          <svg
            class="w-16 h-16"
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

      <div class="p-3">
        <h3 class="text-sm font-semibold text-smoke-gray-100 truncate">
          {{ film.title }}
        </h3>
        <div
          class="flex items-center justify-between mt-1 text-xs text-smoke-gray-400"
        >
          <span>{{ year }}</span>
          <span class="text-blood-red-400 font-medium">{{ rating }} / 10</span>
        </div>
      </div>
    </RouterLink>
  </article>
</template>
