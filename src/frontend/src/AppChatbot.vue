<script setup lang="ts">
import SkipLink from '@/components/ui/SkipLink.vue'
import AiBanner from '@/components/ui/AiBanner.vue'
import ChatbotHeader from '@/components/layout/ChatbotHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
</script>

<template>
  <div class="flex flex-col min-h-screen bg-deep-black-900 text-smoke-gray-100">
    <SkipLink />
    <AiBanner />
    <ChatbotHeader />

    <main id="main-content" tabindex="-1" class="flex-1 flex flex-col">
      <router-view />
    </main>

    <AppFooter />
  </div>
</template>

<style scoped>
#main-content:focus {
  outline: none;
}
</style>
