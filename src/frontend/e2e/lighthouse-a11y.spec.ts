import { test, expect } from '@playwright/test'
import { execSync } from 'child_process'

/**
 * Lighthouse Accessibility audit — score must exceed 90 on every public page.
 *
 * Runs the Lighthouse CLI in headless Chrome and parses the JSON report.
 * Only the "accessibility" category is audited to keep execution fast.
 */

const BASE = 'http://localhost:5173'
const MIN_SCORE = 90

const pages = [
  { name: 'Landing', path: '/' },
  { name: 'Chatbot (login)', path: '/chatbot.html' },
  { name: 'Admin (login)', path: '/admin.html' },
]

for (const page of pages) {
  test(`Lighthouse Accessibility > ${MIN_SCORE} — ${page.name}`, () => {
    const url = `${BASE}${page.path}`
    const result = execSync(
      `npx lighthouse "${url}" --only-categories=accessibility --output=json --chrome-flags="--headless=new --no-sandbox --disable-gpu"`,
      { timeout: 60_000, encoding: 'utf-8' },
    )

    const report = JSON.parse(result)
    const score = Math.round(report.categories.accessibility.score * 100)

    console.log(`  ${page.name}: Lighthouse Accessibility = ${score}`)
    expect(score, `${page.name} accessibility score (${score}) should be > ${MIN_SCORE}`).toBeGreaterThan(MIN_SCORE)
  })
}
