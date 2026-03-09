import { describe, it, expect, beforeEach } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { setupGuards } from '../guards'
import { useAuthStore } from '@/stores/auth.store'

const TOKEN_KEY = 'horrorbot_token'
const TOKEN_EXPIRY_KEY = 'horrorbot_token_expiry'
const USERNAME_KEY = 'horrorbot_username'

const DummyComponent = { template: '<div />' }

function createTestRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/chat' },
      {
        path: '/login',
        name: 'login',
        component: DummyComponent,
        meta: { guest: true, title: 'Login' },
      },
      {
        path: '/register',
        name: 'register',
        component: DummyComponent,
        meta: { guest: true, title: 'Register' },
      },
      {
        path: '/chat',
        name: 'chat',
        component: DummyComponent,
        meta: { requiresAuth: true, title: 'Chat' },
      },
      {
        path: '/films',
        name: 'films',
        component: DummyComponent,
        meta: { requiresAuth: true, title: 'Films' },
      },
      {
        path: '/films/:id',
        name: 'film-detail',
        component: DummyComponent,
        meta: { requiresAuth: true, title: 'Film Detail' },
        props: true,
      },
      {
        path: '/:pathMatch(.*)*',
        name: 'not-found',
        component: DummyComponent,
        meta: { title: 'Page Not Found' },
      },
    ],
  })
  setupGuards(router)
  return router
}

function simulateAuth() {
  const futureExpiry = Date.now() + 3600 * 1000
  localStorage.setItem(TOKEN_KEY, 'valid-token')
  localStorage.setItem(TOKEN_EXPIRY_KEY, String(futureExpiry))
  localStorage.setItem(USERNAME_KEY, 'testuser')
  const store = useAuthStore()
  store.initFromStorage()
}

describe('Router Guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('auth guard', () => {
    it('redirects unauthenticated user to login with redirect query', async () => {
      const router = createTestRouter()
      await router.push('/chat')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/chat')
    })

    it('allows authenticated user to access protected route', async () => {
      simulateAuth()
      const router = createTestRouter()
      await router.push('/chat')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('chat')
    })

    it('preserves full path including params in redirect query', async () => {
      const router = createTestRouter()
      await router.push('/films/42')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/films/42')
    })
  })

  describe('guest guard', () => {
    it('redirects authenticated user away from login to chat', async () => {
      simulateAuth()
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('chat')
    })

    it('redirects authenticated user away from register to chat', async () => {
      simulateAuth()
      const router = createTestRouter()
      await router.push('/register')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('chat')
    })

    it('allows unauthenticated user to access login', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('login')
    })
  })

  describe('title update', () => {
    it('sets document title from route meta', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      expect(document.title).toBe('Login | HorrorBot')
    })

    it('sets title for not-found route', async () => {
      const router = createTestRouter()
      await router.push('/nonexistent-page')
      await router.isReady()

      expect(document.title).toBe('Page Not Found | HorrorBot')
    })
  })
})
