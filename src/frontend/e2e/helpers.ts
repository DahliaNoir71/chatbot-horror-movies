import type { Page } from '@playwright/test'

/** Inject auth tokens + mock API so authenticated pages load without backend. */
export async function setupAuth(page: Page) {
  const futureExpiry = String(Date.now() + 3_600_000) // +1h

  await page.addInitScript(
    ({ expiry }) => {
      localStorage.setItem('horrorbot_token', 'fake-jwt-for-e2e')
      localStorage.setItem('horrorbot_token_expiry', expiry)
      localStorage.setItem('horrorbot_username', 'testuser')
    },
    { expiry: futureExpiry },
  )

  await page.route('**/api/v1/**', (route) => {
    const url = route.request().url()

    if (url.includes('/health')) {
      return route.fulfill({
        json: {
          status: 'ok',
          version: '1.0.0',
          components: { database: 'ok', model: 'ok' },
          timestamp: new Date().toISOString(),
        },
      })
    }

    if (url.includes('/films')) {
      return route.fulfill({
        json: {
          data: [],
          meta: { page: 1, size: 20, total: 0, pages: 0 },
        },
      })
    }

    return route.fulfill({ json: {} })
  })
}

/**
 * Navigate to a route within a multi-page Vue app.
 *
 * The routers use createWebHistory() so hash URLs don't work.
 * We load the HTML entry point, then trigger a client-side navigation
 * via Vue Router so it resolves the target route.
 */
export async function navigateToRoute(
  page: Page,
  htmlEntry: string,
  route: string,
) {
  await page.goto(htmlEntry)
  // Wait for Vue app to fully mount and initial router navigation to settle
  await page.waitForFunction(() => {
    const app = document.querySelector('#app')
    return app && app.children.length > 0
  })
  // Use Vue Router directly — popstate is unreliable across multi-page apps
  await page.evaluate(async (r) => {
    const el = document.querySelector('#app') as any
    const router = el?.__vue_app__?.config?.globalProperties?.$router
    if (router) {
      // Wait for initial navigation to complete before pushing
      await router.isReady()
      await router.push(r)
    }
  }, route)
}
