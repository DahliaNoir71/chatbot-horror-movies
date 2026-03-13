import type { Page } from '@playwright/test'

/**
 * Storage key prefixes per app entry point.
 * Must match main-chatbot.ts / main-admin.ts calls to
 * setStoragePrefix() and setTokenKey().
 */
const APP_KEYS = {
  chatbot: { token: 'horrorbot_chat_token', prefix: 'horrorbot_chat' },
  admin: { token: 'horrorbot_admin_token', prefix: 'horrorbot_admin' },
} as const

export type AppName = keyof typeof APP_KEYS

/** Inject auth tokens + mock API so authenticated pages load without backend. */
export async function setupAuth(page: Page, app: AppName = 'chatbot') {
  const futureExpiry = String(Date.now() + 3_600_000) // +1h
  const { token: tokenKey, prefix } = APP_KEYS[app]

  await page.addInitScript(
    ({ tokenKey, prefix, expiry }) => {
      localStorage.setItem(tokenKey, 'fake-jwt-for-e2e')
      localStorage.setItem(`${prefix}_token_expiry`, expiry)
      localStorage.setItem(`${prefix}_username`, 'testuser')
      localStorage.setItem(`${prefix}_role`, 'admin')
    },
    { tokenKey, prefix, expiry: futureExpiry },
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
