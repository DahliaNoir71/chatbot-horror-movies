import { test, expect } from '@playwright/test'
import { setupAuth, navigateToRoute } from './helpers'

test.describe('Auth — Login, échec, logout', () => {
  test('Login réussi redirige vers /chat', async ({ page }) => {
    // Mock the auth endpoint to return a valid token
    await page.route('**/api/v1/auth/token', (route) =>
      route.fulfill({
        json: {
          access_token: 'fake-jwt-for-e2e',
          token_type: 'bearer',
          expires_in: 3600,
        },
      }),
    )

    // Mock subsequent API calls for authenticated pages
    await page.route('**/api/v1/health', (route) =>
      route.fulfill({
        json: { status: 'ok', version: '1.0.0', components: {}, timestamp: new Date().toISOString() },
      }),
    )

    await navigateToRoute(page, '/chatbot.html', '/login')
    await page.waitForSelector('form')

    await page.getByLabel(/Nom d'utilisateur/i).fill('testuser')
    await page.getByLabel(/Mot de passe/i).fill('password123')
    await page.getByRole('button', { name: /Se connecter/i }).click()

    // Should redirect to /chat after successful login
    await expect(page).toHaveURL(/\/chat/)
  })

  test('Login échoué affiche erreur 401', async ({ page }) => {
    await page.route('**/api/v1/auth/token', (route) =>
      route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } }),
    )

    await navigateToRoute(page, '/chatbot.html', '/login')
    await page.waitForSelector('form')

    await page.getByLabel(/Nom d'utilisateur/i).fill('wronguser')
    await page.getByLabel(/Mot de passe/i).fill('wrongpass1')
    await page.getByRole('button', { name: /Se connecter/i }).click()

    // Should show "Identifiants invalides" error
    await expect(page.getByRole('alert')).toContainText('Identifiants invalides')
  })

  test('Validation client — champs vides', async ({ page }) => {
    await navigateToRoute(page, '/chatbot.html', '/login')
    await page.waitForSelector('form')

    // Submit empty form
    await page.getByRole('button', { name: /Se connecter/i }).click()

    // Should show validation errors
    await expect(page.getByRole('alert').first()).toBeVisible()
  })

  test('Logout redirige vers /login', async ({ page }) => {
    await setupAuth(page)
    await navigateToRoute(page, '/chatbot.html', '/chat')
    await page.waitForSelector('#main-content')

    // Click logout button
    await page.getByRole('button', { name: /Se déconnecter/i }).click()

    // Should redirect to /login
    await expect(page).toHaveURL(/\/login/)
  })
})
