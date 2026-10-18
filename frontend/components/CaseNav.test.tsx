import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '@/test/fixtures'
import CaseNav from './CaseNav'

const id = (c: string) => c.repeat(32)
const summary = (c: string) => ({ id: id(c), created_at: '2026-10-17T14:05:00Z', status: 'done', model: 'conch', cancer_type: null })

const fetchMock = vi.fn()
const assign = vi.fn()
beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(jsonResponse({ store: 'postgres', jobs: ['a', 'b', 'c'].map(summary) }))
  vi.stubGlobal('fetch', fetchMock)
  assign.mockReset()
  vi.stubGlobal('location', { ...window.location, assign })
})
afterEach(() => vi.unstubAllGlobals())

test('links to the cases before and after this one, in worklist order', async () => {
  render(<CaseNav id={id('b')} />)
  expect(await screen.findByText('2 / 3')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /previous case/i })).toHaveAttribute('href', `/jobs/${id('a')}`)
  expect(screen.getByRole('link', { name: /next case/i })).toHaveAttribute('href', `/jobs/${id('c')}`)
})

test('J goes to the next case and K to the previous one', async () => {
  render(<CaseNav id={id('b')} />)
  await screen.findByText('2 / 3')
  await userEvent.keyboard('j')
  expect(assign).toHaveBeenLastCalledWith(`/jobs/${id('c')}`)
  await userEvent.keyboard('k')
  expect(assign).toHaveBeenLastCalledWith(`/jobs/${id('a')}`)
})

test('at the ends of the list there is nothing to go to', async () => {
  render(<CaseNav id={id('a')} />)
  await screen.findByText('1 / 3')
  expect(screen.queryByRole('link', { name: /previous case/i })).not.toBeInTheDocument()
  await userEvent.keyboard('k')
  expect(assign).not.toHaveBeenCalled()
})

test('renders nothing if the list cannot be read', async () => {
  fetchMock.mockRejectedValue(new TypeError('offline'))
  const { container } = render(<CaseNav id={id('a')} />)
  await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})
