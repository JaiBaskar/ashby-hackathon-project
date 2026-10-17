import { jsonResponse, makeStatus } from '@/test/fixtures'
import JobPage from './page'

const notFound = vi.fn(() => {
  throw new Error('NEXT_NOT_FOUND')
})
vi.mock('next/navigation', () => ({ notFound: () => notFound(), useRouter: () => ({ push: vi.fn() }) }))

const fetchMock = vi.fn()
beforeEach(() => {
  notFound.mockClear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

const params = (id: string) => ({ params: Promise.resolve({ id }) })

test("an unknown job id (the API's 404) renders the not-found page", async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: 'No analysis with this id.' }, 404))
  await expect(JobPage(params('nope'))).rejects.toThrow('NEXT_NOT_FOUND')
  expect(notFound).toHaveBeenCalled()
})

test('a known job id renders the job view with its current status', async () => {
  fetchMock.mockResolvedValue(jsonResponse(makeStatus()))
  const page = await JobPage(params('abc'))
  expect(page.props).toMatchObject({ id: 'abc', initial: makeStatus() })
  expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/jobs\/abc$/)
})
