import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { JobSummary } from '@/lib/api'
import { writeCase } from '@/lib/casebook'
import { jsonResponse } from '@/test/fixtures'
import Worklist from './Worklist'

const id = (c: string) => c.repeat(32)
const job = (c: string, overrides: Partial<JobSummary> = {}): JobSummary => ({
  id: id(c),
  created_at: '2026-10-17T14:05:00+00:00',
  status: 'done',
  model: 'conch',
  cancer_type: null,
  organ: 'colon',
  best_tumor: 0.62,
  best_necrosis: 0.03,
  n_regions: 5,
  progress: 1,
  best_box: [100, 50, 256, 256],
  image_size: [2048, 1536],
  ...overrides,
})

const JOBS = [
  job('a', { organ: 'breast', best_tumor: 0.41 }),
  job('b', { best_tumor: 0.12 }),
  job('c', { status: 'running', progress: 0.45, best_tumor: null, best_necrosis: null, n_regions: null, best_box: null, image_size: null }),
  job('d', { status: 'error', best_tumor: null, n_regions: null, best_box: null }),
]

const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const rows = () => screen.getAllByRole('listitem')
const caseIds = () => rows().map((r) => within(r).getByRole('link').getAttribute('href')!.slice(-32, -31))

test('each row shows the label from this browser, organ, best tumor %, sequencing verdict and status', () => {
  writeCase(id('a'), { label: 'S26-0412 A1' })
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} timeZone="UTC" />)
  const [a, b, c, d] = rows()
  expect(within(a).getByRole('link', { name: /Open case S26-0412 A1/ })).toHaveAttribute('href', `/jobs/${id('a')}`)
  expect(a).toHaveTextContent('Breast')
  expect(a).toHaveTextContent('41%')
  expect(within(a).getByTestId('seq')).toHaveTextContent('≥ 20%')
  expect(within(b).getByTestId('seq')).toHaveTextContent('< 20%')
  expect(within(b).getByRole('link')).toHaveAccessibleName(/Open case aaaa|Open case bbbbbb/i)
  expect(within(c).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '45')
  expect(d).toHaveTextContent('Failed')
  const time = within(a).getByText('Oct 17, 2026, 2:05 PM')
  expect(time.tagName).toBe('TIME')
})

test('a summary line counts the cases', () => {
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  expect(screen.getByTestId('worklist-counts')).toHaveTextContent('4 cases · 1 running · 1 ready for sequencing')
})

test('search matches the local label or the case id', async () => {
  writeCase(id('b'), { label: 'Block B7' })
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  await userEvent.type(screen.getByRole('searchbox', { name: /search/i }), 'b7')
  expect(caseIds()).toEqual(['b'])
  await userEvent.clear(screen.getByRole('searchbox', { name: /search/i }))
  await userEvent.type(screen.getByRole('searchbox', { name: /search/i }), 'cccc')
  expect(caseIds()).toEqual(['c'])
})

test('filters by status, organ and sequencing verdict', async () => {
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /status/i }), 'running')
  expect(caseIds()).toEqual(['c'])
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /status/i }), 'all')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /organ/i }), 'breast')
  expect(caseIds()).toEqual(['a'])
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /organ/i }), 'all')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: /sequencing/i }), 'below')
  expect(caseIds()).toEqual(['b'])
})

test('the reviewed tick is saved in this browser, and reviewed cases can be hidden', async () => {
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  await userEvent.click(within(rows()[1]).getByRole('checkbox', { name: /reviewed/i }))
  expect(JSON.parse(localStorage.getItem(`ssf.case.${id('b')}`)!)).toMatchObject({ reviewed: true })
  await userEvent.click(screen.getByRole('checkbox', { name: /hide reviewed/i }))
  expect(caseIds()).toEqual(['a', 'c', 'd'])
})

test('the thumbnail is the slide with its best box drawn on it', () => {
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  const thumb = within(rows()[0]).getByTestId('thumb')
  expect(thumb.querySelector('img')).toHaveAttribute('src', `/api/jobs/${id('a')}/display.png`)
  // best box at (100, 50) 256 px on a 2048 × 1536 image → percentages of the thumbnail
  expect(within(thumb).getByTestId('thumb-box')).toHaveStyle({ left: '4.8828125%', top: '3.2552083333333335%', width: '12.5%' })
  expect(within(rows()[2]).queryByTestId('thumb-box')).not.toBeInTheDocument()
})

test('while a case is running, the list refreshes itself until it is done', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  fetchMock.mockResolvedValue(jsonResponse({ store: 'postgres', jobs: [job('c', { status: 'done', best_tumor: 0.5 })] }))
  render(<Worklist initial={{ store: 'postgres', jobs: [JOBS[2]] }} />)
  await act(() => vi.advanceTimersByTimeAsync(2100))
  expect(fetchMock).toHaveBeenCalledWith('/api/jobs', expect.anything())
  expect(rows()[0]).toHaveTextContent('50%')
  const calls = fetchMock.mock.calls.length
  await act(() => vi.advanceTimersByTimeAsync(5000))
  expect(fetchMock.mock.calls.length).toBe(calls) // nothing running any more
})

test('an empty filter result says so', async () => {
  render(<Worklist initial={{ store: 'postgres', jobs: JOBS }} />)
  await userEvent.type(screen.getByRole('searchbox', { name: /search/i }), 'zzz')
  expect(screen.getByText(/no cases match/i)).toBeInTheDocument()
})
