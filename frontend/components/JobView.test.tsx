import { act, render, screen } from '@testing-library/react'
import { jsonResponse, makeResult, makeStatus } from '@/test/fixtures'
import JobView from './JobView'

const fetchMock = vi.fn()
beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: 1024 } as DOMRect)
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const tick = () => act(() => vi.advanceTimersByTimeAsync(1000))

test('polls a running job until it is done, then shows the results', async () => {
  fetchMock
    .mockResolvedValueOnce(jsonResponse(makeStatus({ step: 'analyzing', progress: 0.5 })))
    .mockResolvedValueOnce(jsonResponse(makeStatus({ status: 'done', step: 'ranking', progress: 1, result: makeResult() })))
  render(<JobView id="abc" initial={makeStatus()} />)
  expect(screen.getByText('Tiling').closest('li')).toHaveAttribute('aria-current', 'step')

  await tick()
  expect(fetchMock).toHaveBeenCalledWith('/api/jobs/abc', expect.anything())
  expect(screen.getByText('Analyzing with CONCH').closest('li')).toHaveAttribute('aria-current', 'step')

  await tick()
  expect(screen.getAllByRole('button', { name: /^Region \d/ })).toHaveLength(5)

  await tick()
  expect(fetchMock).toHaveBeenCalledTimes(2) // stops polling once done
})

test('a finished job (e.g. after a reload) shows results without polling', async () => {
  render(<JobView id="abc" initial={makeStatus({ status: 'done', progress: 1, result: makeResult() })} />)
  expect(screen.getAllByRole('button', { name: /^Region \d/ })).toHaveLength(5)
  await tick()
  expect(fetchMock).not.toHaveBeenCalled()
})

test('a job that fails shows the error state', async () => {
  fetchMock.mockResolvedValueOnce(jsonResponse(makeStatus({ status: 'error', error: 'No tissue found in this image.' })))
  render(<JobView id="abc" initial={makeStatus()} />)
  await tick()
  expect(screen.getByRole('alert')).toHaveTextContent('No tissue found in this image.')
  expect(screen.getByRole('link', { name: 'Try another image' })).toBeInTheDocument()
})

test('a job that disappears (server restart) shows its message instead of spinning', async () => {
  fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'No analysis with this id. It may have expired.' }, 404))
  render(<JobView id="abc" initial={makeStatus()} />)
  await tick()
  expect(screen.getByRole('alert')).toHaveTextContent('No analysis with this id. It may have expired.')
})
