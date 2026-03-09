<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const authStore = useAuthStore()
const router = useRouter()
const mobileMenuOpen = ref(false)

async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}

function toggleMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}
</script>

<template>
  <header
    v-if="authStore.isAuthenticated"
    role="banner"
    class="bg-deep-black-800 border-b border-blood-red-800"
  >
    <div class="flex items-center justify-between px-6 py-3">
      <span class="text-lg font-bold text-blood-red-500 tracking-wide">
        HorrorBot Admin
      </span>

      <nav
        aria-label="Navigation principale"
        class="hidden lg:flex items-center gap-6"
      >
        <RouterLink
          to="/dashboard"
          class="text-smoke-gray-300 hover:text-blood-red-400 transition-colors"
          active-class="text-blood-red-500 font-semibold"
        >
          Dashboard
        </RouterLink>
        <RouterLink
          to="/films"
          class="text-smoke-gray-300 hover:text-blood-red-400 transition-colors"
          active-class="text-blood-red-500 font-semibold"
        >
          Films
        </RouterLink>
      </nav>

      <div class="flex items-center gap-4">
        <span class="hidden sm:inline text-sm text-smoke-gray-300">
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

        <button
          class="lg:hidden p-2 text-smoke-gray-300 hover:text-blood-red-400 transition-colors"
          :aria-expanded="mobileMenuOpen"
          aria-controls="mobile-nav"
          aria-label="Menu de navigation"
          @click="toggleMenu"
        >
          <svg
            class="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              v-if="!mobileMenuOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 6h16M4 12h16M4 18h16"
            />
            <path
              v-else
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>

    <nav
      v-if="mobileMenuOpen"
      id="mobile-nav"
      aria-label="Navigation principale mobile"
      class="lg:hidden border-t border-deep-black-700 px-6 py-3 flex flex-col gap-2"
    >
      <RouterLink
        to="/dashboard"
        class="text-smoke-gray-300 hover:text-blood-red-400 py-2 transition-colors"
        active-class="text-blood-red-500 font-semibold"
        @click="mobileMenuOpen = false"
      >
        Dashboard
      </RouterLink>
      <RouterLink
        to="/films"
        class="text-smoke-gray-300 hover:text-blood-red-400 py-2 transition-colors"
        active-class="text-blood-red-500 font-semibold"
        @click="mobileMenuOpen = false"
      >
        Films
      </RouterLink>
    </nav>
  </header>
</template>
