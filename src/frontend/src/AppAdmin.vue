<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'
import SkipLink from '@/components/ui/SkipLink.vue'
import AdminHeader from '@/components/layout/AdminHeader.vue'
import AdminSidebar from '@/components/layout/AdminSidebar.vue'
import AppFooter from '@/components/layout/AppFooter.vue'

const authStore = useAuthStore()
const route = useRoute()

const showSidebar = computed(() => {
  return authStore.isAuthenticated && route.path.startsWith('/films')
})
</script>

<template>
  <div
    id="app-shell"
    class="flex flex-col min-h-screen bg-deep-black-900 text-smoke-gray-100"
  >
    <SkipLink />
    <AdminHeader />

    <div class="flex flex-1 overflow-hidden">
      <AdminSidebar v-if="showSidebar" />

      <main
        id="main-content"
        tabindex="-1"
        class="flex-1 flex flex-col overflow-y-auto"
      >
        <router-view />
      </main>
    </div>

    <AppFooter />
  </div>
</template>

<style scoped>
#main-content:focus {
  outline: none;
}
</style>
