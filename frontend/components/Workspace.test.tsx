import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, makeMeasured, makeResult } from '@/test/fixtures'
import Results from './Results'

// The results workspace around the slide: threshold, region table, zoom, heatmap opacity, shortcuts,
// copy summary and the local-only case label and notes.
const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  fetchMock.mockImplementation(async (url: string) => {
    const q = new URL(url, 'http://x').searchParams
    const [x, y, w, h] = ['x', 'y', 'w', 'h'].map((k) => Number(q.get(k)))
    return jsonResponse(makeMeasured(x, y, w, h))
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    () => ({ width: 1024, height: 768, x: 0, y: 0, top: 0, left: 0, right: 1024, bottom: 768, toJSON() {} }) as DOMRect,
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const boxes = () => screen.getAllByRole('button', { name: /^Region \d/ })
const table = () => screen.getByRole('table', { name: /regions/i })
const rows = () => within(table()).getAllByRole('row').slice(1) // minus the header row
const inspector = () => within(screen.getByRole('region', { name: /region details/i }))

// --- sequencing threshold -----------------------------------------------------------------------------

test('every region says whether it meets the minimum tumor fraction (20% by default)', () => {
  // fixture tumor fractions: 62, 54, 51, 47, 44%
  render(<Results result={makeResult()} />)
  expect(rows().map((r) => within(r).getByTestId('meets').textContent)).toEqual(['≥ 20%', '≥ 20%', '≥ 20%', '≥ 20%', '≥ 20%'])
  expect(inspector().getByTestId('threshold-verdict')).toHaveTextContent('Meets the 20% minimum')
})

test('raising the minimum flags the regions below it, and the setting is remembered', async () => {
  const { unmount } = render(<Results result={makeResult()} />)
  const input = screen.getByRole('spinbutton', { name: /minimum tumor/i })
  await userEvent.clear(input)
  await userEvent.type(input, '50')
  expect(rows().map((r) => within(r).getByTestId('meets').textContent)).toEqual(['≥ 50%', '≥ 50%', '≥ 50%', '< 50%', '< 50%'])
  await userEvent.click(within(rows()[4]).getByRole('button', { name: 'Select region 5' }))
  expect(inspector().getByTestId('threshold-verdict')).toHaveTextContent('Below the 50% minimum')
  unmount()
  render(<Results result={makeResult()} />)
  expect(screen.getByRole('spinbutton', { name: /minimum tumor/i })).toHaveValue(50)
})

// --- region table -------------------------------------------------------------------------------------

test('the table lists every region with its numbers, and clicking a row selects that box', async () => {
  render(<Results result={makeResult()} />)
  expect(rows()).toHaveLength(5)
  expect(rows()[2]).toHaveTextContent(/^3.*51%.*2%.*0\.47.*512.*95%/)
  await userEvent.click(rows()[2])
  expect(boxes()[2]).toHaveAttribute('aria-pressed', 'true')
  expect(rows()[2]).toHaveAttribute('aria-selected', 'true')
  expect(inspector().getByRole('heading', { name: /region 3/i })).toBeInTheDocument()
})

test('the table sorts by a column and back', async () => {
  render(<Results result={makeResult()} />)
  const rank = () => rows().map((r) => r.querySelector('th')!.textContent)
  await userEvent.click(within(table()).getByRole('button', { name: /necrosis/i }))
  expect(rank()).toEqual(['3', '5', '1', '2', '4']) // necrosis 2, 2, 3, 4, 6%, low first
  expect(within(table()).getByRole('columnheader', { name: /necrosis/i })).toHaveAttribute('aria-sort', 'ascending')
  await userEvent.click(within(table()).getByRole('button', { name: /necrosis/i }))
  expect(rank()).toEqual(['4', '2', '1', '3', '5'])
  await userEvent.click(within(table()).getByRole('button', { name: /rank/i }))
  expect(rank()).toEqual(['1', '2', '3', '4', '5'])
})

test('your own box gets a row too', async () => {
  render(<Results result={makeResult()} />)
  await userEvent.click(screen.getByRole('button', { name: /^Region 2/ }))
  await userEvent.click(inspector().getByRole('button', { name: 'Adjust this box' }))
  const yours = await within(table()).findByRole('row', { name: /yours/i })
  expect(yours).toHaveAttribute('aria-selected', 'true')
  expect(yours).toHaveTextContent('44%')
})

// --- zoom and heatmap -----------------------------------------------------------------------------------

test('zoom buttons enlarge the slide inside the stage, and Fit puts it back', async () => {
  render(<Results result={makeResult()} />)
  const canvas = screen.getByTestId('stage-canvas')
  expect(canvas).toHaveStyle({ width: '100%' })
  await userEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
  await userEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
  expect(canvas).toHaveStyle({ width: '200%' })
  expect(screen.getByTestId('zoom-level')).toHaveTextContent('200%')
  await userEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
  expect(canvas).toHaveStyle({ width: '150%' })
  await userEvent.click(screen.getByRole('button', { name: 'Fit' }))
  expect(canvas).toHaveStyle({ width: '100%' })
  expect(screen.getByRole('button', { name: 'Zoom out' })).toBeDisabled()
})

test('the heatmap has an opacity slider while it is on', async () => {
  render(<Results result={makeResult()} />)
  expect(screen.queryByRole('slider', { name: /heatmap opacity/i })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('switch', { name: /tumor heatmap/i }))
  const slider = screen.getByRole('slider', { name: /heatmap opacity/i })
  fireEvent.change(slider, { target: { value: '30' } })
  expect(screen.getByTestId('heatmap')).toHaveStyle({ opacity: '0.3' })
})

// --- keyboard shortcuts ---------------------------------------------------------------------------------

test('number keys select regions, H toggles the heatmap, D starts drawing, Escape stops', async () => {
  render(<Results result={makeResult()} />)
  await userEvent.keyboard('4')
  expect(boxes()[3]).toHaveAttribute('aria-pressed', 'true')
  await userEvent.keyboard('h')
  expect(screen.getByTestId('heatmap')).toBeInTheDocument()
  await userEvent.keyboard('d')
  expect(screen.getByRole('button', { name: 'Draw a box' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.keyboard('{Escape}')
  expect(screen.getByRole('button', { name: 'Draw a box' })).toHaveAttribute('aria-pressed', 'false')
  await userEvent.keyboard('+')
  expect(screen.getByTestId('zoom-level')).toHaveTextContent('150%')
  await userEvent.keyboard('0')
  expect(screen.getByTestId('zoom-level')).toHaveTextContent('100%')
})

test('shortcuts stay out of the way while typing in a field', async () => {
  render(<Results result={makeResult()} />)
  await userEvent.click(screen.getByRole('textbox', { name: /notes/i }))
  await userEvent.keyboard('4h')
  expect(boxes()[0]).toHaveAttribute('aria-pressed', 'true')
  expect(screen.queryByTestId('heatmap')).not.toBeInTheDocument()
})

test('Delete removes your box', async () => {
  render(<Results result={makeResult()} />)
  await userEvent.click(inspector().getByRole('button', { name: 'Adjust this box' }))
  expect(screen.getByRole('group', { name: /your box/i })).toBeInTheDocument()
  await act(async () => {
    ;(document.activeElement as HTMLElement | null)?.blur()
  })
  await userEvent.keyboard('{Delete}')
  expect(screen.queryByRole('group', { name: /your box/i })).not.toBeInTheDocument()
})

// --- copy summary -----------------------------------------------------------------------------------------

test('Copy summary puts a plain-text summary on the clipboard', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
  render(<Results result={makeResult()} />)
  await userEvent.type(screen.getByRole('textbox', { name: /case label/i }), 'B3')
  await userEvent.click(screen.getByRole('button', { name: /copy summary/i }))
  const text = writeText.mock.calls[0][0] as string
  expect(text).toMatch(/^Case B3/)
  expect(text).toContain('Region 1 (best): tumor 62%, necrosis 3%, 512 µm, meets 20%')
  expect(text).toContain('Region 5: tumor 44%, necrosis 2%, 512 µm, meets 20%')
  expect(text).toMatch(/research prototype/i)
  expect(await screen.findByText('Copied')).toBeInTheDocument()
})

// --- case label and notes stay in the browser ----------------------------------------------------------

test('the case label and notes are saved in this browser only, never sent to the server', async () => {
  const { unmount } = render(<Results id="abc" result={makeResult()} />)
  await userEvent.type(screen.getByRole('textbox', { name: /case label/i }), 'S26-0412 A1')
  await userEvent.type(screen.getByRole('textbox', { name: /notes/i }), 'Avoid the cautery edge')
  expect(screen.getAllByText(/stays on this computer/i).length).toBeGreaterThan(0)
  for (const [url, init] of fetchMock.mock.calls) {
    expect(String(url) + JSON.stringify(init ?? {})).not.toMatch(/S26|cautery/)
  }
  unmount()
  render(<Results id="abc" result={makeResult()} />)
  expect(screen.getByRole('textbox', { name: /case label/i })).toHaveValue('S26-0412 A1')
  expect(screen.getByRole('textbox', { name: /notes/i })).toHaveValue('Avoid the cautery edge')
})

test('a case can be marked reviewed', async () => {
  render(<Results id="abc" result={makeResult()} />)
  const reviewed = screen.getByRole('checkbox', { name: /reviewed/i })
  await userEvent.click(reviewed)
  expect(reviewed).toBeChecked()
  expect(JSON.parse(localStorage.getItem('ssf.case.abc')!)).toMatchObject({ reviewed: true })
})

test('the sampling sheet is one click away', () => {
  render(<Results id="abc" result={makeResult()} />)
  expect(screen.getByRole('link', { name: /sampling sheet/i })).toHaveAttribute('href', '/jobs/abc/sheet')
})
