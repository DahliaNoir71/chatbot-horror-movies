<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div
    class="min-h-full flex flex-col items-center justify-center px-4 py-16 text-center"
  >
    <p class="text-7xl font-bold text-blood-red-500" aria-hidden="true">404</p>
    <h1 class="mt-4 text-2xl font-bold text-smoke-gray-100">
      Page non trouvée
    </h1>
    <p class="mt-2 text-smoke-gray-400">
      La page que vous recherchez n'existe pas ou a été déplacée.
    </p>
    <RouterLink
      to="/"
      class="mt-8 inline-block rounded-lg bg-blood-red-600 px-6 py-3 font-medium text-white hover:bg-blood-red-500 focus:outline-none focus:ring-2 focus:ring-blood-red-400 focus:ring-offset-2 focus:ring-offset-deep-black-800 transition-colors"
    >
      Retour à l'accueil
    </RouterLink>
  </div>
</template>
