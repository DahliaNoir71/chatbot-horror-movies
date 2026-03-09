<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const authStore = useAuthStore()
const router = useRouter()

async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}
</script>

<template>
  <header
    v-if="authStore.isAuthenticated"
    role="banner"
    class="flex items-center justify-between px-6 py-3 bg-deep-black-800 border-b border-blood-red-800"
  >
    <span class="text-xl font-bold text-blood-red-500 tracking-wide">
      HorrorBot
    </span>

    <div class="flex items-center gap-4">
      <span class="text-sm text-smoke-gray-300">
        {{ authStore.user?.username }}
      </span>
      <BaseButton
        variant="ghost"
        size="sm"
        aria-label="Se déconnecter"
        @click="handleLogout"
      >
        Déconnexion
      </BaseButton>
    </div>
  </header>
</template>
