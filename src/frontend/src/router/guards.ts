import { nextTick } from 'vue'
import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'

const APP_TITLE = 'HorrorBot'

export interface GuardOptions {
  defaultRoute: string
}

export function setupGuards(
  router: Router,
  options: GuardOptions = { defaultRoute: '/chat' }
): void {
  router.beforeEach((to) => {
    const auth = useAuthStore()

    // Auth guard: redirect unauthenticated users to login
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    // Guest guard: redirect authenticated users away from guest pages
    if (to.meta.guest && auth.isAuthenticated) {
      return options.defaultRoute
    }

    return true
  })

  router.afterEach((to) => {
    // Title update
    document.title = to.meta.title
      ? `${to.meta.title} | ${APP_TITLE}`
      : APP_TITLE

    // Focus management (accessibility)
    nextTick(() => {
      const main = document.getElementById('main-content')
      if (main) {
        main.setAttribute('tabindex', '-1')
        main.focus()
        main.removeAttribute('tabindex')
      }
    })
  })
}
