import { render, screen } from '@testing-library/react'
import { jsonResponse } from '@/test/fixtures'
import WorklistPage from './page'

// The home page is the worklist, read from FastAPI on the server.
const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

const summary = (id: string, created_at: string) => ({ id, created_at, status: 'done', model: 'conch', cancer_type: null })

test('lists one row per case, in the order the API gives (newest first)', async () => {
  fetchMock.mockResolvedValue(
    jsonResponse({ store: 'postgres', jobs: [summary('b'.repeat(32), '2026-10-17T15:00:00Z'), summary('a'.repeat(32), '2026-10-17T14:00:00Z')] }),
  )
  render(await WorklistPage())
  expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/jobs$/)
  expect(screen.getByRole('heading', { level: 1, name: 'Worklist' })).toBeInTheDocument()
  const links = screen.getAllByRole('link', { name: /^Open case/ })
  expect(links.map((a) => a.getAttribute('href'))).toEqual([`/jobs/${'b'.repeat(32)}`, `/jobs/${'a'.repeat(32)}`])
  expect(screen.queryByText(/isn't saved/)).not.toBeInTheDocument()
})

test('with no cases, says so and offers a new case', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ store: 'postgres', jobs: [] }))
  render(await WorklistPage())
  expect(screen.getByText('No cases yet.')).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: /new case/i })[0]).toHaveAttribute('href', '/upload')
})

test('warns when the history is only kept in memory', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ store: 'memory', jobs: [] }))
  render(await WorklistPage())
  expect(screen.getByText(/isn't saved: no database is configured/)).toBeInTheDocument()
})

test('an API error is thrown to the error page', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: 'boom' }, 500))
  await expect(WorklistPage()).rejects.toThrow('500')
})

test('carries the research-use notice', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ store: 'postgres', jobs: [] }))
  render(await WorklistPage())
  expect(screen.getByText(/research prototype/i)).toBeInTheDocument()
})
