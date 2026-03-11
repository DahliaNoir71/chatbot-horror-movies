<script setup lang="ts">
// Forbidden page — shown when a non-admin user tries to access admin routes
</script>

<template>
  <div
    class="min-h-full flex flex-col items-center justify-center px-4 py-16 text-center"
  >
    <p class="text-7xl font-bold text-blood-red-500" aria-hidden="true">403</p>
    <h1 class="mt-4 text-2xl font-bold text-smoke-gray-100">Accès interdit</h1>
    <p class="mt-2 text-smoke-gray-400">
      Vous n'avez pas les droits nécessaires pour accéder à cette page.
    </p>
    <a
      href="/"
      class="mt-8 inline-block rounded-lg bg-blood-red-600 px-6 py-3 font-medium text-white hover:bg-blood-red-500 focus:outline-none focus:ring-2 focus:ring-blood-red-400 focus:ring-offset-2 focus:ring-offset-deep-black-800 transition-colors"
    >
      Retour à l'accueil
    </a>
  </div>
</template>
