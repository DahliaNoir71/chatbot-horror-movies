<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'

const authStore = useAuthStore()
</script>

<template>
  <aside
    v-if="authStore.isAuthenticated"
    aria-label="Navigation films"
    class="hidden lg:block w-64 shrink-0 bg-deep-black-800 border-r border-smoke-gray-700"
  >
    <nav class="p-4 flex flex-col gap-1">
      <h2
        class="text-xs font-semibold uppercase tracking-wider text-smoke-gray-500 mb-2 px-3"
      >
        Films
      </h2>
      <RouterLink
        to="/films"
        class="px-3 py-2 rounded-lg text-smoke-gray-300 hover:bg-deep-black-700 hover:text-blood-red-400 transition-colors"
        exact-active-class="bg-deep-black-700 text-blood-red-500 font-semibold"
      >
        Tous les films
      </RouterLink>
    </nav>
  </aside>
</template>
