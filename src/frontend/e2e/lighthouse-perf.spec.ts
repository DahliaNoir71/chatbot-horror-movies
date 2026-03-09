import { test, expect } from '@playwright/test'
import { execSync } from 'child_process'

/**
 * Lighthouse Performance audit — score must exceed 90 on every public page.
 *
 * Runs the Lighthouse CLI in headless Chrome and parses the JSON report.
 * Only the "performance" category is audited to keep execution fast.
 *
 * Uses the preview server (production build) for realistic performance scores.
 */

const BASE = 'http://localhost:4173'
const MIN_SCORE = 90

const pages = [
  { name: 'Landing', path: '/' },
  { name: 'Chatbot (login)', path: '/chatbot.html' },
  { name: 'Admin (login)', path: '/admin.html' },
]

for (const page of pages) {
  test(`Lighthouse Performance > ${MIN_SCORE} — ${page.name}`, () => {
    const url = `${BASE}${page.path}`
    const result = execSync(
      `npx lighthouse "${url}" --only-categories=performance --output=json --chrome-flags="--headless=new --no-sandbox --disable-gpu"`,
      { timeout: 120_000, encoding: 'utf-8' },
    )

    const report = JSON.parse(result)
    const score = Math.round(report.categories.performance.score * 100)

    console.log(`  ${page.name}: Lighthouse Performance = ${score}`)
    expect(score, `${page.name} performance score (${score}) should be > ${MIN_SCORE}`).toBeGreaterThan(MIN_SCORE)
  })
}
