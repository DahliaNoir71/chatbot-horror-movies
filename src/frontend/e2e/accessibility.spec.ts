import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { setupAuth, navigateToRoute } from './helpers'

/** Run axe-core WCAG 2.1 AA audit — fail on critical/serious violations. */
async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious',
  )

  if (serious.length > 0) {
    const summary = serious
      .map((v) => `[${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} nodes)`)
      .join('\n')
    expect(serious, `Accessibility violations:\n${summary}`).toEqual([])
  }
}

test.describe('Accessibility — Pages publiques', () => {
  test('Landing page — 0 violation critical/serious', async ({ page }) => {
    await page.goto('/')
    await expectNoA11yViolations(page)
  })

  test('Login chatbot — 0 violation critical/serious', async ({ page }) => {
    await navigateToRoute(page, '/chatbot.html', '/login')
    await page.waitForSelector('form')
    await expectNoA11yViolations(page)
  })

  test('Login admin — 0 violation critical/serious', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/login')
    await page.waitForSelector('form')
    await expectNoA11yViolations(page)
  })
})

test.describe('Accessibility — Pages authentifiées', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)
  })

  test('ChatView — 0 violation critical/serious', async ({ page }) => {
    await navigateToRoute(page, '/chatbot.html', '/chat')
    await page.waitForSelector('#main-content')
    await expectNoA11yViolations(page)
  })

  test('DashboardView — 0 violation critical/serious', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/dashboard')
    await page.waitForSelector('#main-content')
    await expectNoA11yViolations(page)
  })

  test('FilmsView — 0 violation critical/serious', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films')
    await page.waitForSelector('#main-content')
    await expectNoA11yViolations(page)
  })
})
