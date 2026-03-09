import { test, expect } from '@playwright/test'
import { setupAuth, navigateToRoute } from './helpers'

const SSE_RESPONSE = [
  'data: {"type":"chunk","content":"Voici "}\n\n',
  'data: {"type":"chunk","content":"ma réponse"}\n\n',
  'data: {"type":"done","intent":"recommendation","confidence":0.95,"session_id":"sess-123"}\n\n',
].join('')

test.describe('Chat — Envoi question, réponse, nouvelle conversation', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)

    // Mock the streaming endpoint (uses fetch, not axios)
    await page.route('**/api/v1/chat/stream', (route) =>
      route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
        body: SSE_RESPONSE,
      }),
    )

    await navigateToRoute(page, '/chatbot.html', '/chat')
    await page.waitForSelector('#main-content')
  })

  test('Envoi message et réception réponse', async ({ page }) => {
    const textarea = page.getByLabel(/Votre message/i)
    await textarea.fill('Quel est le meilleur film d\'horreur ?')
    await page.getByRole('button', { name: /Envoyer le message/i }).click()

    // User message should appear
    await expect(
      page.getByText('Quel est le meilleur film d\'horreur ?'),
    ).toBeVisible()

    // Bot response should appear (streamed content)
    await expect(page.getByText('Voici ma réponse')).toBeVisible()
  })

  test('Bouton envoyer désactivé si textarea vide', async ({ page }) => {
    const sendButton = page.getByRole('button', { name: /Envoyer le message/i })
    await expect(sendButton).toBeDisabled()
  })

  test('Nouvelle conversation efface les messages', async ({ page }) => {
    // Send a message first
    const textarea = page.getByLabel(/Votre message/i)
    await textarea.fill('Test message')
    await page.getByRole('button', { name: /Envoyer le message/i }).click()
    await expect(page.getByText('Voici ma réponse')).toBeVisible()

    // Click "Nouvelle conversation" and confirm
    await page.getByRole('button', { name: /Nouvelle conversation/i }).click()
    await page.getByRole('button', { name: /Effacer/i }).click()

    // Messages should be cleared — empty state visible
    await expect(page.getByText('Voici ma réponse')).not.toBeVisible()
    await expect(
      page.getByText(/Posez-moi vos questions sur les films d'horreur/i),
    ).toBeVisible()
  })

  test('Badge session active après envoi', async ({ page }) => {
    // Session badge should not be visible initially
    await expect(page.getByText('Session active')).not.toBeVisible()

    // Send a message (mock returns session_id)
    const textarea = page.getByLabel(/Votre message/i)
    await textarea.fill('Hello')
    await page.getByRole('button', { name: /Envoyer le message/i }).click()

    // Wait for response and session badge
    await expect(page.getByText('Voici ma réponse')).toBeVisible()
    await expect(page.getByText('Session active')).toBeVisible()
  })
})
