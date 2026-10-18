import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { writeCase } from '@/lib/casebook'
import { jsonResponse, makeMeasured, makeResult } from '@/test/fixtures'
import SamplingSheet from './SamplingSheet'

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
})
afterEach(() => vi.unstubAllGlobals())

test('a print-ready sheet: case label, notes, every region with its verdict, and sign-off lines', () => {
  writeCase('abc', { label: 'S26-0412 A1', notes: 'Avoid the cautery edge' })
  render(<SamplingSheet id="abc" result={makeResult()} createdAt="2026-10-17T14:05:00+00:00" timeZone="UTC" />)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sampling sheet')
  expect(screen.getByTestId('sheet-label')).toHaveTextContent('S26-0412 A1')
  expect(screen.getByText('Avoid the cautery edge')).toBeInTheDocument()
  const table = screen.getByRole('table', { name: /regions/i })
  expect(within(table).getAllByRole('row')).toHaveLength(6) // header + 5 regions
  expect(within(table).getAllByRole('row')[1]).toHaveTextContent(/1.*62%.*3%.*512.*≥ 20%/)
  expect(screen.getByText(/marked by/i)).toBeInTheDocument()
  expect(screen.getByText(/cut by/i)).toBeInTheDocument()
  expect(screen.getByText(/research prototype/i)).toBeInTheDocument()
})

test('without your own box, the instruction is the best region', () => {
  render(<SamplingSheet id="abc" result={makeResult()} />)
  expect(screen.getByTestId('sheet-instruction')).toHaveTextContent('Macrodissect region 1')
  expect(screen.getByTestId('sheet-instruction')).toHaveTextContent('62% tumor')
  expect(fetchMock).not.toHaveBeenCalled()
})

test("with your own box, it's measured and becomes the instruction", async () => {
  writeCase('abc', { box: { x: 200, y: 200, w: 400, h: 300 } })
  render(<SamplingSheet id="abc" result={makeResult()} />)
  expect(await screen.findByText(/macrodissect the pathologist's box/i)).toBeInTheDocument()
  expect(screen.getByTestId('sheet-instruction')).toHaveTextContent('44% tumor')
  expect(screen.getByTestId('sheet-instruction')).toHaveTextContent('200 × 150 µm')
  expect(String(fetchMock.mock.calls[0][0])).toBe('/api/jobs/abc/measure?x=200&y=200&w=400&h=300')
  expect(screen.getByTestId('sheet-yours')).toHaveStyle({ left: '9.765625%', top: '13.020833333333334%' })
})

test('the threshold on the sheet is the one set in this browser', () => {
  localStorage.setItem('ssf.threshold', '50')
  render(<SamplingSheet id="abc" result={makeResult()} />)
  const rows = within(screen.getByRole('table', { name: /regions/i })).getAllByRole('row')
  expect(rows[4]).toHaveTextContent('< 50%')
})

test('a 1 mm scale bar is drawn from the image scale', () => {
  // fixture: 256 display px = 512 µm, so 1 mm = 500 display px of a 2048 px image
  render(<SamplingSheet id="abc" result={makeResult()} />)
  expect(screen.getByTestId('scale-bar')).toHaveStyle({ width: '24.4140625%' })
  expect(screen.getByTestId('scale-bar')).toHaveTextContent('1 mm')
})

test('Print opens the browser print dialog', async () => {
  const print = vi.fn()
  vi.stubGlobal('print', print)
  render(<SamplingSheet id="abc" result={makeResult()} />)
  await userEvent.click(screen.getByRole('button', { name: /print/i }))
  expect(print).toHaveBeenCalled()
})
