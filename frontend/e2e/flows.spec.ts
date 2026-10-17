import { readFileSync } from 'node:fs'
import { expect, fixture, regionBoxes, test, uploadFromHome } from './fixtures'

const pct = (fraction: number) => `${Math.round(fraction * 100)}%`
const LABELS: Record<string, string> = {
  tumor: 'Tumor',
  stroma: 'Stroma',
  immune: 'Immune',
  necrosis: 'Necrosis',
  normal: 'Normal',
  fat_other: 'Fat / other',
}

test('full flow: upload a slide, see 5 regions, open region 3', async ({ page, request }) => {
  const id = await uploadFromHome(page, fixture('slide'))

  await expect(page.getByRole('heading', { name: 'Suggested sampling sites' })).toBeVisible({ timeout: 30_000 })
  await expect(regionBoxes(page)).toHaveCount(5)
  await expect(page.getByText('Demo model').first()).toBeVisible()

  const job = await (await request.get(`/api/jobs/${id}`)).json()
  expect(job.status).toBe('done')
  const region3 = job.result.regions.find((r: { rank: number }) => r.rank === 3)

  const box = page.getByRole('button', { name: /^Region 3:/ })
  await box.click()
  await expect(box).toHaveAttribute('aria-pressed', 'true')

  const panel = page.getByRole('region', { name: 'Region details' })
  await expect(panel.getByRole('heading', { name: 'Region 3' })).toBeVisible()
  await expect(panel).toContainText(`Score ${region3.score.toFixed(2)}`)
  const composition = panel.getByRole('list', { name: 'Cell composition' })
  for (const [cls, label] of Object.entries(LABELS)) {
    await expect(composition.getByRole('listitem').filter({ hasText: label })).toContainText(pct(region3.composition[cls]))
  }
  for (const reason of region3.reasons) await expect(panel.getByText(reason, { exact: true })).toBeVisible()
  await expect(panel.getByTestId('tumor-vs-slide')).toHaveText(
    `${pct(region3.composition.tumor)} here vs. ${pct(job.result.slide_composition.tumor)} across the slide`,
  )
  await expect(panel.getByTestId('coverage')).toHaveText(pct(region3.tissue_coverage))

  // The box sits where the API says, scaled to the rendered image.
  const img = page.getByRole('img', { name: /uploaded slide/ })
  const imgBox = (await img.boundingBox())!
  const scale = imgBox.width / job.result.image.width
  const b = (await box.boundingBox())!
  expect(b.x - imgBox.x).toBeCloseTo(region3.x * scale, 0)
  expect(b.y - imgBox.y).toBeCloseTo(region3.y * scale, 0)
  expect(b.width).toBeCloseTo(region3.w * scale, 0)
})

test('history: a finished analysis gets a card that opens its results', async ({ page }) => {
  const id = await uploadFromHome(page, fixture('slide'))
  await expect(page.getByRole('heading', { name: 'Suggested sampling sites' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Cancer type')).toBeVisible()

  await page.getByRole('navigation').getByRole('link', { name: 'History' }).click()
  await expect(page).toHaveURL(/\/history$/)
  await expect(page.getByRole('heading', { name: 'History' })).toBeVisible()
  const card = page.getByRole('link', { name: /Analysis/ }).first() // newest first
  await expect(card).toHaveAttribute('href', `/jobs/${id}`)
  await expect(card).toContainText('Not identified yet')
  await expect(card).toContainText('Done')
  await expect(card.locator('time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}T/)

  await card.click()
  await expect(page).toHaveURL(new RegExp(`/jobs/${id}$`))
  await expect(regionBoxes(page)).toHaveCount(5)
})

test('error flow: a blank image ends in the error state, and "Try another image" returns to upload', async ({ page }) => {
  await uploadFromHome(page, fixture('blank'))
  await expect(page.getByText('No tissue found in this image.')).toHaveAttribute('role', 'alert', { timeout: 30_000 })
  await page.getByRole('link', { name: 'Try another image' }).click()
  await expect(page).toHaveURL(/\/upload$/)
  await expect(page.getByRole('heading', { name: 'Analyze a slide' })).toBeVisible()
})

test('an upload over 10 MB reaches FastAPI through the Next.js rewrite', async ({ request }) => {
  const buffer = readFileSync(fixture('large'))
  expect(buffer.length).toBeGreaterThan(10 * 1024 * 1024)
  const res = await request.post('/api/jobs', {
    multipart: { file: { name: 'large.png', mimeType: 'image/png', buffer } },
  })
  expect(res.status()).toBe(200)
  expect((await res.json()).job_id).toMatch(/^[0-9a-f]+$/)
})

test.describe('at 375 px', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('no screen scrolls horizontally', async ({ page }) => {
    const noHorizontalScroll = async () =>
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0)

    await page.goto('/')
    await noHorizontalScroll()
    await uploadFromHome(page, fixture('slide'))
    await expect(regionBoxes(page)).toHaveCount(5, { timeout: 30_000 })
    await noHorizontalScroll()
    await page.getByRole('link', { name: 'New analysis' }).click()
    await expect(page).toHaveURL(/\/upload$/)
    await page.locator('input[type="file"]').setInputFiles(fixture('slide'))
    await noHorizontalScroll()
    await page.goto('/history')
    await expect(page.getByRole('heading', { name: 'History' })).toBeVisible()
    await noHorizontalScroll()
  })
})
