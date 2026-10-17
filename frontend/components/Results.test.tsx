import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, makeResult, region } from '@/test/fixtures'
import Results from './Results'

// jsdom has no layout: give the slide image a rendered width we control.
let renderedWidth = 1024
beforeEach(() => {
  renderedWidth = 1024
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    () => ({ width: renderedWidth, height: renderedWidth * 0.75, x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, toJSON() {} }) as DOMRect,
  )
})
afterEach(() => vi.restoreAllMocks())

const boxes = () => screen.getAllByRole('button', { name: /^Region \d/ })

test('draws exactly one box per region, with rank badges 1–5', () => {
  render(<Results result={makeResult()} />)
  expect(boxes()).toHaveLength(5)
  expect(boxes().map((b) => within(b).getByTestId('rank').textContent)).toEqual(['1', '2', '3', '4', '5'])
})

test('the best box uses the best style and the "Best" label; the others do not', () => {
  render(<Results result={makeResult()} />)
  const [best, ...others] = boxes()
  expect(best).toHaveClass('region-box-best')
  expect(within(best).getByText('Best')).toBeInTheDocument()
  for (const b of others) {
    expect(b).toHaveClass('region-box')
    expect(b).not.toHaveClass('region-box-best')
    expect(within(b).queryByText('Best')).not.toBeInTheDocument()
  }
})

test('boxes scale with the rendered image, also after a resize', () => {
  render(<Results result={makeResult()} />)
  // 2048 px wide result shown at 1024 px: region 3 at x = 800 is drawn at 400 px.
  expect(boxes()[2]).toHaveStyle({ left: '400px', top: '100px', width: '128px', height: '128px' })

  renderedWidth = 512
  act(() => {
    window.dispatchEvent(new Event('resize'))
  })
  expect(boxes()[2]).toHaveStyle({ left: '200px', top: '50px', width: '64px', height: '64px' })
})

test('the best region is selected at first; clicking another box switches the panel', async () => {
  render(<Results result={makeResult()} />)
  const panel = () => screen.getByRole('region', { name: /region details/i })
  expect(boxes()[0]).toHaveAttribute('aria-pressed', 'true')
  expect(within(panel()).getByRole('heading', { name: /region 1/i })).toBeInTheDocument()

  await userEvent.click(boxes()[2])
  expect(boxes()[2]).toHaveAttribute('aria-pressed', 'true')
  expect(boxes()[0]).toHaveAttribute('aria-pressed', 'false')
  expect(within(panel()).getByRole('heading', { name: /region 3/i })).toBeInTheDocument()

  await userEvent.click(boxes()[3])
  expect(within(panel()).getByRole('heading', { name: /region 4/i })).toBeInTheDocument()
})

test('pressing Enter on a box selects it', async () => {
  render(<Results result={makeResult()} />)
  boxes()[1].focus()
  await userEvent.keyboard('{Enter}')
  expect(boxes()[1]).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('heading', { name: /region 2/i })).toBeInTheDocument()
})

test('the detail panel shows score, composition, reasons, tumor vs. slide, size and coverage', async () => {
  const result = makeResult()
  render(<Results result={result} />)
  await userEvent.click(boxes()[2])
  const panel = within(screen.getByRole('region', { name: /region details/i }))
  const r = result.regions[2]

  expect(panel.getByText(r.score.toFixed(2))).toBeInTheDocument()
  const bar = within(panel.getByRole('list', { name: /cell composition/i }))
  const items = bar.getAllByRole('listitem')
  expect(items).toHaveLength(6)
  expect(items[0]).toHaveTextContent(`Tumor${Math.round(r.composition.tumor * 100)}%`)
  expect(items[5]).toHaveTextContent(`Fat / other${Math.round(r.composition.fat_other * 100)}%`)
  expect(panel.getByText('Estimated from tile classification, not individual cell counts')).toBeInTheDocument()
  for (const reason of r.reasons) expect(panel.getByText(reason)).toBeInTheDocument()
  expect(panel.getByTestId('tumor-vs-slide')).toHaveTextContent('51% here vs. 41% across the slide')
  expect(panel.getByTestId('size')).toHaveTextContent('512 µm')
  expect(panel.getByTestId('size')).not.toHaveTextContent(/estimated/i)
  expect(panel.getByTestId('coverage')).toHaveTextContent('95%')
})

test('size is labeled as estimated when the scale was estimated', () => {
  render(<Results result={makeResult({ image: { ...makeResult().image, mpp_estimated: true } })} />)
  expect(screen.getByTestId('size')).toHaveTextContent(/512 µm.*estimated/i)
})

test("shows the API's note when fewer than 5 regions came back", () => {
  const result = makeResult()
  const note = 'Only 2 regions are fully on tissue, so 2 are shown.'
  render(<Results result={{ ...result, regions: result.regions.slice(0, 2), note }} />)
  expect(boxes()).toHaveLength(2)
  expect(screen.getByText(note)).toBeInTheDocument()
})

test('the Demo model badge shows for the fake model only', () => {
  const { rerender } = render(<Results result={makeResult({ model: 'fake' })} />)
  expect(screen.getByText('Demo model')).toBeInTheDocument()
  rerender(<Results result={makeResult({ model: 'conch' })} />)
  expect(screen.queryByText('Demo model')).not.toBeInTheDocument()
})

test('carries the research-use notice and a "New analysis" button', () => {
  render(<Results result={makeResult()} />)
  expect(screen.getByText(/research prototype.*not for clinical use/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'New analysis' })).toHaveAttribute('href', '/upload')
})

test('the heatmap toggle shows and hides the tumor overlay', () => {
  render(<Results result={makeResult()} />)
  expect(screen.queryByTestId('heatmap')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('switch', { name: /tumor heatmap/i }))
  expect(screen.getByTestId('heatmap')).toHaveAttribute('src', '/api/jobs/abc/heatmap.png')
  fireEvent.click(screen.getByRole('switch', { name: /tumor heatmap/i }))
  expect(screen.queryByTestId('heatmap')).not.toBeInTheDocument()
})

test('shows when the request was created and the cancer type, when given', () => {
  render(<Results result={makeResult()} meta={{ created_at: '2026-10-17T14:05:00+00:00', cancer_type: null }} timeZone="UTC" />)
  expect(screen.getByText('Oct 17, 2026, 2:05 PM').tagName).toBe('TIME')
  expect(screen.getByText('Cancer type').nextElementSibling).toHaveTextContent('Not identified yet')
})

describe('box size', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  const sizes = () => within(screen.getByRole('radiogroup', { name: /box size/i })).getAllByRole('radio')
  const bigRegions = () => [
    region(1, 400, 400, 0.48, 0.03, ['Highest overall score of all candidates (0.43)'], 512),
    region(2, 1200, 600, 0.4, 0.05, ['Tumor content is 8 points lower than the best region'], 512),
  ]

  test('offers the sizes from the result, in mm, with the current one checked', () => {
    render(<Results result={makeResult()} />)
    expect(sizes().map((r) => r.closest('label')?.textContent)).toEqual(['0.5 mm', '1 mm', '2 mm'])
    expect(screen.getByRole('radio', { name: '0.5 mm' })).toBeChecked()
  })

  test('picking another size re-ranks through the API and redraws the boxes', async () => {
    const note = 'Only 2 non-overlapping 8×8-tile regions are at least 90% on tissue, so 2 are shown instead of 5.'
    fetchMock.mockResolvedValueOnce(jsonResponse({ box_um: 1024, regions: bigRegions(), note }))
    render(<Results result={makeResult()} />)
    await userEvent.click(boxes()[2])

    await userEvent.click(screen.getByRole('radio', { name: '1 mm' }))
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs/abc/regions?box_um=1024', expect.anything())
    expect(await screen.findByText(note)).toBeInTheDocument()
    expect(boxes()).toHaveLength(2)
    expect(screen.getByRole('radio', { name: '1 mm' })).toBeChecked()
    // the selection goes back to the new best region, and the panel shows the new size
    expect(boxes()[0]).toHaveAttribute('aria-pressed', 'true')
    const panel = within(screen.getByRole('region', { name: /region details/i }))
    expect(panel.getByRole('heading', { name: /region 1/i })).toBeInTheDocument()
    expect(panel.getByTestId('size')).toHaveTextContent('1024 µm')
    expect(boxes()[0]).toHaveStyle({ width: '256px', height: '256px' }) // 512 display px at half scale
  })

  test('going back to the original size uses the first result without a request', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ box_um: 1024, regions: bigRegions(), note: null }))
    render(<Results result={makeResult()} />)
    await userEvent.click(screen.getByRole('radio', { name: '1 mm' }))
    await screen.findByRole('radio', { name: '1 mm', checked: true })
    await userEvent.click(screen.getByRole('radio', { name: '0.5 mm' }))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(boxes()).toHaveLength(5)
  })

  test('a failed re-rank keeps the current boxes and says why', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'No analysis with this id. It may have expired.' }, 404))
    render(<Results result={makeResult()} />)
    await userEvent.click(screen.getByRole('radio', { name: '2 mm' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No analysis with this id. It may have expired.')
    expect(boxes()).toHaveLength(5)
    expect(screen.getByRole('radio', { name: '0.5 mm' })).toBeChecked()
  })

  test('the size picker is disabled while a re-rank is loading', async () => {
    let finish: (r: Response) => void = () => {}
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => (finish = resolve)))
    render(<Results result={makeResult()} />)
    await userEvent.click(screen.getByRole('radio', { name: '1 mm' }))
    expect(screen.getByRole('radiogroup', { name: /box size/i })).toHaveAttribute('aria-busy', 'true')
    for (const r of sizes()) expect(r).toBeDisabled()
    await act(async () => finish(jsonResponse({ box_um: 1024, regions: bigRegions(), note: null })))
    expect(screen.getByRole('radiogroup', { name: /box size/i })).toHaveAttribute('aria-busy', 'false')
    expect(boxes()).toHaveLength(2)
  })
})
