import { readFileSync } from 'node:fs'
import { expect, fixture, regionBoxes, resultsReady, test, uploadFromHome } from './fixtures'

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

  await resultsReady(page)
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

test('worklist: a finished case gets a row with its numbers, and the local label follows it', async ({ page }) => {
  const id = await uploadFromHome(page, fixture('slide'))
  await resultsReady(page)
  await page.getByRole('textbox', { name: 'Case label' }).fill('E2E-A1')

  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Worklist' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: 'Worklist' })).toBeVisible()
  const row = page.getByRole('listitem').filter({ has: page.getByRole('link', { name: 'Open case E2E-A1' }) })
  await expect(row.getByRole('link')).toHaveAttribute('href', `/jobs/${id}`)
  await expect(row).toContainText('tumor, best region')
  await expect(row.locator('time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}T/)
  await expect(row.getByTestId('thumb').locator('img')).toHaveAttribute('src', `/api/jobs/${id}/display.png`)

  await row.getByRole('link').click()
  await expect(page).toHaveURL(new RegExp(`/jobs/${id}$`))
  await expect(regionBoxes(page)).toHaveCount(5)
})

test('a batch: two slides become two cases; J moves to the next one; the sampling sheet opens', async ({ page }) => {
  // Other tests' cases share this worklist, so these two are told apart by their (local) labels.
  await page.goto('/upload')
  await page.locator('input[type="file"]').setInputFiles([fixture('slide'), fixture('slide')])
  const labels = page.getByRole('textbox', { name: /^Case label for/ })
  await labels.nth(0).fill('BATCH-1')
  await labels.nth(1).fill('BATCH-2')
  await page.getByRole('button', { name: 'Analyze 2 slides' }).click()
  await expect(page).toHaveURL(/\/$/)
  const one = page.getByRole('link', { name: 'Open case BATCH-1' })
  const two = page.getByRole('link', { name: 'Open case BATCH-2' })
  await expect(one).toBeVisible({ timeout: 10_000 })
  await expect(two).toBeVisible()
  for (const link of [one, two]) {
    await expect(page.getByRole('listitem').filter({ has: link })).toContainText('tumor, best region', { timeout: 30_000 })
  }

  // Newest first: BATCH-2 is listed above BATCH-1, so "next" from BATCH-2 is BATCH-1.
  const firstHref = (await one.getAttribute('href'))!
  await two.click()
  await resultsReady(page)
  await page.locator('body').click({ position: { x: 5, y: 5 } })
  await page.keyboard.press('j')
  await expect(page).toHaveURL(new RegExp(`${firstHref}$`))

  await resultsReady(page)
  await expect(page.getByRole('textbox', { name: 'Case label' })).toHaveValue('BATCH-1')
  await page.getByRole('link', { name: 'Sampling sheet' }).click()
  await expect(page.getByRole('heading', { name: 'Sampling sheet' })).toBeVisible()
  await expect(page.getByTestId('sheet-label')).toHaveText('BATCH-1')
  await expect(page.getByTestId('sheet-instruction')).toContainText('Macrodissect region 1')
})

test('box size: 1 mm re-ranks through the API, and 0.5 mm brings the original boxes back', async ({ page, request }) => {
  const id = await uploadFromHome(page, fixture('slide'))
  await expect(regionBoxes(page)).toHaveCount(5, { timeout: 30_000 })
  const first = (await (await request.get(`/api/jobs/${id}`)).json()).result
  const big = await (await request.get(`/api/jobs/${id}/regions?box_um=1024`)).json()
  expect(big.regions.length).toBeGreaterThan(0)

  const sizes = page.getByRole('radiogroup', { name: /box size/i })
  await sizes.getByText('1 mm', { exact: true }).click()
  await expect(regionBoxes(page)).toHaveCount(big.regions.length)
  await expect(page.getByRole('region', { name: 'Region details' }).getByTestId('size')).toContainText('1024 µm')
  if (big.note) await expect(page.getByText(big.note)).toBeVisible()

  // Twice the side of a 0.5 mm box, at the rendered scale.
  const img = (await page.getByRole('img', { name: /uploaded slide/ }).boundingBox())!
  const scale = img.width / first.image.width
  const b = (await regionBoxes(page).first().boundingBox())!
  expect(b.width).toBeCloseTo(2 * first.regions[0].w * scale, 0)

  await sizes.getByText('0.5 mm', { exact: true }).click()
  await expect(regionBoxes(page)).toHaveCount(first.regions.length)
  await expect(page.getByRole('region', { name: 'Region details' }).getByTestId('size')).toContainText('512 µm')
})

test('free box: draw any rectangle, resize it by a corner, and its numbers come from the API', async ({ page, request }) => {
  const id = await uploadFromHome(page, fixture('slide'))
  await expect(regionBoxes(page)).toHaveCount(5, { timeout: 30_000 })
  const img = (await page.getByRole('img', { name: /uploaded slide/ }).boundingBox())!

  await page.getByRole('button', { name: 'Draw a box' }).click()
  const from = { x: img.x + img.width * 0.3, y: img.y + img.height * 0.3 }
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 120, from.y + 60, { steps: 5 })
  await page.mouse.up()

  const box = page.getByRole('group', { name: /^Your box/ })
  await expect(box).toBeVisible()
  const panel = page.getByRole('region', { name: 'Region details' })
  await expect(panel.getByRole('heading', { name: 'Your box' })).toBeVisible()
  const drawn = (await box.boundingBox())!
  expect(drawn.width).toBeCloseTo(120, 0)
  expect(drawn.height).toBeCloseTo(60, 0)

  // Resize from the bottom-right handle.
  const handle = (await box.getByTestId('handle-se').boundingBox())!
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2)
  await page.mouse.down()
  await page.mouse.move(handle.x + handle.width / 2 + 80, handle.y + handle.height / 2 + 40, { steps: 5 })
  await page.mouse.up()
  const resized = (await box.boundingBox())!
  expect(resized.width).toBeCloseTo(200, 0)
  expect(resized.height).toBeCloseTo(100, 0)

  // The panel shows what the API measures for the box's current rectangle.
  const job = (await (await request.get(`/api/jobs/${id}`)).json()).result
  const scale = img.width / job.image.width
  const q = new URLSearchParams({
    x: String((resized.x - img.x) / scale),
    y: String((resized.y - img.y) / scale),
    w: String(resized.width / scale),
    h: String(resized.height / scale),
  })
  const measured = await (await request.get(`/api/jobs/${id}/measure?${q}`)).json()
  await expect(panel.getByTestId('tumor-vs-slide')).toContainText(`${pct(measured.composition.tumor)} here`)
  await expect(panel.getByTestId('size')).toContainText(`${Math.round(measured.width_um)} × ${Math.round(measured.height_um)} µm`)

  await panel.getByRole('button', { name: 'Remove your box' }).click()
  await expect(box).toHaveCount(0)
})

test('grab the best box by its corner: it resizes freely and its numbers update before you let go', async ({ page, request }) => {
  const id = await uploadFromHome(page, fixture('slide'))
  await expect(regionBoxes(page)).toHaveCount(5, { timeout: 30_000 })
  const best = page.getByRole('button', { name: /^Region 1/ })
  const corner = (await best.getByTestId('handle-se').boundingBox())!
  const start = { x: corner.x + corner.width / 2, y: corner.y + corner.height / 2 }

  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(start.x + 150, start.y + 90, { steps: 8 })

  // Still holding the corner: the box is yours, and the panel already shows numbers for its current shape.
  const box = page.getByRole('group', { name: /^Your box/ })
  const panel = page.getByRole('region', { name: 'Region details' })
  await expect(panel.getByRole('heading', { name: 'Your box' })).toBeVisible()
  await expect(panel.getByTestId('size')).toBeVisible()
  const held = (await box.boundingBox())!
  const img = (await page.getByRole('img', { name: /uploaded slide/ }).boundingBox())!
  const width = (await (await request.get(`/api/jobs/${id}`)).json()).result.image.width
  const scale = img.width / width
  const q = new URLSearchParams({
    x: String((held.x - img.x) / scale),
    y: String((held.y - img.y) / scale),
    w: String(held.width / scale),
    h: String(held.height / scale),
  })
  const measured = await (await request.get(`/api/jobs/${id}/measure?${q}`)).json()
  await expect(panel.getByTestId('size')).toContainText(`${Math.round(measured.width_um)} × ${Math.round(measured.height_um)} µm`)
  await page.mouse.up()
  await expect(best).toBeVisible() // the suggestion stays, for comparison
})

test('error flow: a blank image ends in the error state, and "Try another image" returns to upload', async ({ page }) => {
  await uploadFromHome(page, fixture('blank'))
  await expect(page.getByText('No tissue found in this image.')).toHaveAttribute('role', 'alert', { timeout: 30_000 })
  await page.getByRole('link', { name: 'Try another image' }).click()
  await expect(page).toHaveURL(/\/upload$/)
  await expect(page.getByRole('heading', { name: 'New case' })).toBeVisible()
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
    const id = await uploadFromHome(page, fixture('slide'))
    await expect(regionBoxes(page)).toHaveCount(5, { timeout: 30_000 })
    await noHorizontalScroll()
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'New case' }).click()
    await expect(page).toHaveURL(/\/upload$/)
    await page.locator('input[type="file"]').setInputFiles(fixture('slide'))
    await noHorizontalScroll()
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Worklist' })).toBeVisible()
    await noHorizontalScroll()
    await page.goto(`/jobs/${id}/sheet`)
    await expect(page.getByRole('heading', { name: 'Sampling sheet' })).toBeVisible()
    await noHorizontalScroll()
  })
})
