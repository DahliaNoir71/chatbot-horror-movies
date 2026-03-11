import { test, expect } from '@playwright/test'
import { setupAuth, navigateToRoute } from './helpers'

const MOCK_FILMS_PAGE1 = {
  data: [
    { id: 1, tmdb_id: 694, title: 'The Shining', release_date: '1980-05-23', vote_average: 8.4, popularity: 50, poster_path: null },
    { id: 2, tmdb_id: 539, title: 'Psycho', release_date: '1960-06-16', vote_average: 8.5, popularity: 45, poster_path: null },
  ],
  meta: { page: 1, size: 20, total: 22, pages: 2 },
}

const MOCK_FILMS_PAGE2 = {
  data: [
    { id: 3, tmdb_id: 999, title: 'Nosferatu', release_date: '1922-03-04', vote_average: 7.9, popularity: 30, poster_path: null },
  ],
  meta: { page: 2, size: 20, total: 22, pages: 2 },
}

const MOCK_SEARCH_RESULTS = {
  query: 'shining',
  results: [
    { id: 1, tmdb_id: 694, title: 'The Shining', overview: 'Jack Torrance accepts a caretaker position...', release_date: '1980-05-23', score: 0.92 },
  ],
  count: 1,
}

const MOCK_FILM_DETAIL = {
  id: 1, tmdb_id: 694, title: 'The Shining', release_date: '1980-05-23',
  vote_average: 8.4, popularity: 50, poster_path: null,
  imdb_id: 'tt0081505', original_title: 'The Shining',
  overview: 'Jack Torrance accepts a caretaker position at the Overlook Hotel.',
  runtime: 146, budget: 19000000, revenue: 44017374, vote_count: 16500,
  tagline: 'A masterpiece of modern horror', status: 'Released',
  original_language: 'en',
}

test.describe('Films — Recherche, pagination, détail', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page)

    // Override the default films mock from setupAuth with detailed routing
    await page.unrouteAll()

    const futureExpiry = String(Date.now() + 3_600_000)
    await page.addInitScript(
      ({ expiry }) => {
        localStorage.setItem('horrorbot_token', 'fake-jwt-for-e2e')
        localStorage.setItem('horrorbot_token_expiry', expiry)
        localStorage.setItem('horrorbot_username', 'testuser')
        localStorage.setItem('horrorbot_role', 'admin')
      },
      { expiry: futureExpiry },
    )

    await page.route('**/api/v1/films/search', (route) =>
      route.fulfill({ json: MOCK_SEARCH_RESULTS }),
    )

    await page.route('**/api/v1/films/1', (route) =>
      route.fulfill({ json: MOCK_FILM_DETAIL }),
    )

    await page.route('**/api/v1/films?*page=2*', (route) =>
      route.fulfill({ json: MOCK_FILMS_PAGE2 }),
    )

    await page.route('**/api/v1/films**', (route) => {
      const url = route.request().url()
      // Already handled by more specific routes above
      if (url.includes('/films/search') || url.includes('/films/1')) {
        return route.fallback()
      }
      if (url.includes('page=2')) {
        return route.fulfill({ json: MOCK_FILMS_PAGE2 })
      }
      return route.fulfill({ json: MOCK_FILMS_PAGE1 })
    })

    await page.route('**/api/v1/health', (route) =>
      route.fulfill({
        json: { status: 'ok', version: '1.0.0', components: {}, timestamp: new Date().toISOString() },
      }),
    )
  })

  test('Liste des films se charge', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films')
    await page.waitForSelector('#main-content')

    await expect(page.getByText('The Shining')).toBeVisible()
    await expect(page.getByText('Psycho')).toBeVisible()
    await expect(page.getByText('Page 1 / 2')).toBeVisible()
  })

  test('Pagination — page suivante et précédente', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films')
    await page.waitForSelector('#main-content')
    await expect(page.getByText('Page 1 / 2')).toBeVisible()

    // Go to page 2
    await page.getByRole('button', { name: /Suivant/i }).click()
    await expect(page.getByText('Nosferatu')).toBeVisible()
    await expect(page.getByText('Page 2 / 2')).toBeVisible()

    // Go back to page 1
    await page.getByRole('button', { name: /Précédent/i }).click()
    await expect(page.getByText('The Shining')).toBeVisible()
    await expect(page.getByText('Page 1 / 2')).toBeVisible()
  })

  test('Recherche de films', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films')
    await page.waitForSelector('#main-content')

    await page.getByLabel(/Rechercher un film/i).fill('shining')

    // Wait for debounced search results
    await expect(page.getByText(/1 résultat\(s\) pour « shining »/)).toBeVisible()
    await expect(page.getByText('Score : 92%')).toBeVisible()
  })

  test('Détail d\'un film', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films')
    await page.waitForSelector('#main-content')

    // Click on The Shining film card
    await page.getByText('The Shining').first().click()

    // Should show film detail
    await expect(page.getByRole('heading', { name: /The Shining/ })).toBeVisible()
    await expect(page.getByText('Jack Torrance accepts a caretaker position')).toBeVisible()
    await expect(page.getByText('8.4 / 10')).toBeVisible()
    await expect(page.getByText('A masterpiece of modern horror')).toBeVisible()
  })

  test('Retour à la liste depuis le détail', async ({ page }) => {
    await navigateToRoute(page, '/admin.html', '/films/1')
    await page.waitForSelector('#main-content')

    await expect(page.getByRole('heading', { name: /The Shining/ })).toBeVisible()

    // Click back link
    await page.getByText('Retour aux films').click()

    // Should be back on films list
    await expect(page.getByRole('heading', { name: 'Films' })).toBeVisible()
    await expect(page.getByText('The Shining')).toBeVisible()
  })
})
