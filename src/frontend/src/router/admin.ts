import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { setupGuards } from './guards'
import { useAuthStore } from '@/stores/auth.store'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
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
    component: () => import('@/views/AdminLoginView.vue'),
    meta: { guest: true, title: 'Connexion Admin' },
  },
  {
    path: '/forbidden',
    name: 'forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { title: 'Accès interdit' },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/admin/DashboardView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Tableau de bord' },
  },
  {
    path: '/monitoring',
    name: 'monitoring',
    component: () => import('@/views/admin/MonitoringView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Monitoring' },
  },
  {
    path: '/films',
    name: 'films',
    component: () => import('@/views/admin/FilmsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Films' },
  },
  {
    path: '/films/:id',
    name: 'film-detail',
    component: () => import('@/views/admin/FilmDetailView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Détail film' },
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

// Admin guard: redirect non-admin users to forbidden page
router.beforeEach((to) => {
  if (to.meta.requiresAdmin) {
    const auth = useAuthStore()
    if (!auth.isAdmin) {
      return { name: 'forbidden' }
    }
  }
  return true
})

export default router
