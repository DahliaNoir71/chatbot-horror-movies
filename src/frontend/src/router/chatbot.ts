import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { setupGuards } from './guards'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guest?: boolean
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guest: true, title: 'Connexion' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guest: true, title: 'Inscription' },
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/chatbot/ChatView.vue'),
    meta: { requiresAuth: true, title: 'Chat' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Page non trouvée' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

setupGuards(router, { defaultRoute: '/chat' })

export default router
