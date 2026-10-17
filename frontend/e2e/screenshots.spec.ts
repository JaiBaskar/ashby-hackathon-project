import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page } from '@playwright/test'
import { expect, fixture, regionBoxes, test } from './fixtures'

// Every screen at 375 and 1440 px, light and dark, saved as reports/screenshots/<screen>-<width>-<theme>.png.
// Only synthetic fixtures appear in them (implementation-steps.md §1), so they can be opened to check layout.
const OUT = fileURLToPath(new URL('../../reports/screenshots', import.meta.url))
const WIDTHS = [375, 1440]
const THEMES = ['light', 'dark'] as const

async function shoot(page: Page, screen: string, width: number, theme: string) {
  await page.evaluate(() => document.fonts.ready)
  // Let the enter animations finish.
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(OUT, `${screen}-${width}-${theme}.png`), fullPage: true })
}

async function chooseFile(page: Page, file: string) {
  await page.goto('/upload')
  await page.locator('input[type="file"]').setInputFiles(file)
  await expect(page.getByRole('img', { name: /^Preview of/ })).toBeVisible()
}

for (const width of WIDTHS) {
  for (const theme of THEMES) {
    test.describe(`${width} px, ${theme}`, () => {
      test.use({ viewport: { width, height: width < 768 ? 812 : 900 }, colorScheme: theme })

      test('home, upload, analyzing, results and error screens', async ({ page }) => {
        await page.goto('/')
        await shoot(page, 'home', width, theme)

        await chooseFile(page, fixture('slide'))
        await shoot(page, 'upload', width, theme)

        // Analyzing: the demo model finishes in about a second, so hold the client's polling on a mid-run state.
        let jobModel = 'fake'
        await page.route('**/api/jobs/*', async (route) => {
          if (route.request().method() !== 'GET') return route.continue()
          await route.fulfill({ json: { status: 'running', step: 'analyzing', progress: 0.55, model: jobModel } })
        })
        await page.getByRole('button', { name: 'Analyze slide' }).click()
        await expect(page).toHaveURL(/\/jobs\/[0-9a-f]+$/)
        const step = page.getByRole('listitem').filter({ hasText: 'Analyzing with CONCH' })
        await expect(step).toHaveAttribute('aria-current', 'step', { timeout: 10_000 })
        await shoot(page, 'analyzing', width, theme)
        await page.unroute('**/api/jobs/*')
        jobModel = ''

        // Results: the same job, reloaded once it's done (a results URL survives a reload).
        await expect(async () => {
          await page.reload()
          await expect(regionBoxes(page)).toHaveCount(5, { timeout: 1_000 })
        }).toPass({ timeout: 30_000 })
        await shoot(page, 'results', width, theme)
        await page.getByRole('switch', { name: 'Tumor heatmap' }).click()
        await expect(page.getByTestId('heatmap')).toBeVisible()
        await page.getByRole('button', { name: /^Region 3:/ }).click()
        await shoot(page, 'results-heatmap', width, theme)

        await chooseFile(page, fixture('blank'))
        await page.getByRole('button', { name: 'Analyze slide' }).click()
        await expect(page.getByText('No tissue found in this image.')).toBeVisible({ timeout: 30_000 })
        await shoot(page, 'error', width, theme)
      })
    })
  }
}
