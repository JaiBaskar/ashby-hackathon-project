import { render, screen } from '@testing-library/react'
import { jsonResponse } from '@/test/fixtures'
import HistoryPage from './page'

const fetchMock = vi.fn()
beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

const summary = (id: string, created_at: string) => ({ id, created_at, status: 'done', model: 'conch', cancer_type: null })

test('lists one card per request, in the order the API gives (newest first)', async () => {
  fetchMock.mockResolvedValue(
    jsonResponse({ store: 'postgres', jobs: [summary('b'.repeat(32), '2026-10-17T15:00:00Z'), summary('a'.repeat(32), '2026-10-17T14:00:00Z')] }),
  )
  render(await HistoryPage())
  expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/jobs$/)
  const links = screen.getAllByRole('link', { name: /Analysis/ })
  expect(links.map((a) => a.getAttribute('href'))).toEqual([`/jobs/${'b'.repeat(32)}`, `/jobs/${'a'.repeat(32)}`])
  expect(screen.queryByText(/isn't saved/)).not.toBeInTheDocument()
})

test('with no requests, says so and links to the upload page', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ store: 'postgres', jobs: [] }))
  render(await HistoryPage())
  expect(screen.getByText('No analyses yet.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Analyze a slide' })).toHaveAttribute('href', '/upload')
})

test('warns when history is only kept in memory', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ store: 'memory', jobs: [] }))
  render(await HistoryPage())
  expect(screen.getByText(/History isn't saved: no database is configured/)).toBeInTheDocument()
})

test('an API error is thrown to the error page', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: 'boom' }, 500))
  await expect(HistoryPage()).rejects.toThrow('500')
})
