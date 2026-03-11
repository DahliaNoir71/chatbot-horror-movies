import type { Page } from '@playwright/test'

/** Inject auth tokens + mock API so authenticated pages load without backend. */
export async function setupAuth(page: Page) {
  const futureExpiry = String(Date.now() + 3_600_000) // +1h

  await page.addInitScript(
    ({ expiry }) => {
      localStorage.setItem('horrorbot_token', 'fake-jwt-for-e2e')
      localStorage.setItem('horrorbot_token_expiry', expiry)
      localStorage.setItem('horrorbot_username', 'testuser')
      localStorage.setItem('horrorbot_role', 'admin')
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
 * The routers use createWebHashHistory() so we navigate directly
 * via the hash URL: e.g. /chatbot.html#/chat
 */
export async function navigateToRoute(
  page: Page,
  htmlEntry: string,
  route: string,
) {
  await page.goto(`${htmlEntry}#${route}`)
  await page.waitForFunction(() => {
    const app = document.querySelector('#app')
    return app && app.children.length > 0
  })
}
