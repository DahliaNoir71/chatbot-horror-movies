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
    redirect: '/dashboard',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guest: true, title: 'Connexion' },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/admin/DashboardView.vue'),
    meta: { requiresAuth: true, title: 'Tableau de bord' },
  },
  {
    path: '/films',
    name: 'films',
    component: () => import('@/views/admin/FilmsView.vue'),
    meta: { requiresAuth: true, title: 'Films' },
  },
  {
    path: '/films/:id',
    name: 'film-detail',
    component: () => import('@/views/admin/FilmDetailView.vue'),
    meta: { requiresAuth: true, title: 'Détail film' },
    props: true,
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

setupGuards(router, { defaultRoute: '/dashboard' })

export default router
