import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '@/test/fixtures'
import UploadForm from './UploadForm'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

const fetchMock = vi.fn()
beforeEach(() => {
  localStorage.clear()
  push.mockReset()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => vi.unstubAllGlobals())

const png = (bytes = 10, name = 'slide.png', type = 'image/png') => {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: bytes })
  return f
}

test('offers a file picker, a drop zone and the scale field with the config default', () => {
  render(<UploadForm />)
  expect(screen.getByLabelText(/choose an image/i)).toHaveAttribute('type', 'file')
  expect(screen.getByText(/drag a slide image here/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/image scale \(µm\/px\)/i)).toHaveValue(Number(process.env.DEFAULT_MPP))
})

test('picking an image shows a preview and its name', async () => {
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), png())
  expect(screen.getByRole('img', { name: /preview of slide.png/i })).toHaveAttribute('src', 'blob:preview')
})

test('dropping a file selects it', () => {
  render(<UploadForm />)
  fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [png()] } })
  expect(screen.getByText('slide.png')).toBeInTheDocument()
})

test('rejects an unsupported file inline, before uploading', async () => {
  render(<UploadForm />)
  fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [png(10, 'notes.pdf', 'application/pdf')] } })
  expect(screen.getByRole('alert')).toHaveTextContent(/\.pdf.*png, jpeg, tiff or svs/i)
  expect(screen.getByRole('button', { name: 'Analyze slide' })).toBeDisabled()
  expect(fetchMock).not.toHaveBeenCalled()
})

test('rejects a file over max_upload_mb inline, before uploading', () => {
  const max = Number(process.env.MAX_UPLOAD_MB)
  render(<UploadForm />)
  fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [png(max * 1024 * 1024 + 1)] } })
  expect(screen.getByRole('alert')).toHaveTextContent(new RegExp(`${max} MB`))
  expect(screen.getByRole('button', { name: 'Analyze slide' })).toBeDisabled()
  expect(fetchMock).not.toHaveBeenCalled()
})

test('uploads the file and the scale, then opens the job', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ job_id: 'abc' }))
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), png())
  const scale = screen.getByLabelText(/image scale/i)
  await userEvent.clear(scale)
  await userEvent.type(scale, '0.25')
  await userEvent.click(screen.getByRole('button', { name: 'Analyze slide' }))

  await waitFor(() => expect(push).toHaveBeenCalledWith('/jobs/abc'))
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/jobs')
  expect(init.method).toBe('POST')
  expect((init.body as FormData).get('file')).toBeInstanceOf(File)
  expect((init.body as FormData).get('mpp')).toBe('0.25')
})

test("shows the server's message when the upload is refused", async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: 'This image could not be read.' }, 400))
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), png())
  await userEvent.click(screen.getByRole('button', { name: 'Analyze slide' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This image could not be read.')
  expect(push).not.toHaveBeenCalled()
})

test('offers the organs from config.yaml, defaulting to the config default', () => {
  render(<UploadForm />)
  const select = screen.getByLabelText(/organ/i) as HTMLSelectElement
  expect([...select.options].map((o) => o.value)).toEqual(process.env.ORGANS!.split(','))
  expect([...select.options].map((o) => o.textContent)).toEqual([
    'Colon / rectum',
    'Lung',
    'Breast',
    'Pancreas',
    'Prostate',
    'Other / unknown',
  ])
  expect(select).toHaveValue(process.env.DEFAULT_ORGAN)
})

test('sends the chosen organ with the upload', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ job_id: 'abc' }))
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), png())
  await userEvent.selectOptions(screen.getByLabelText(/organ/i), 'lung')
  await userEvent.click(screen.getByRole('button', { name: 'Analyze slide' }))
  await waitFor(() => expect(push).toHaveBeenCalledWith('/jobs/abc'))
  expect((fetchMock.mock.calls[0][1].body as FormData).get('organ')).toBe('lung')
})

// --- several slides at once, remembered settings, local case labels ------------------------------------

test('several slides become several cases, sent one after another; you land on the worklist', async () => {
  localStorage.clear()
  let n = 0
  fetchMock.mockImplementation(async () => jsonResponse({ job_id: `job${++n}` }))
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), [png(10, 'a.png'), png(10, 'b.png'), png(10, 'c.png')])
  expect(screen.getAllByRole('textbox', { name: /case label for/i })).toHaveLength(3)
  await userEvent.type(screen.getByRole('textbox', { name: 'Case label for b.png' }), 'Block B2')
  await userEvent.click(screen.getByRole('button', { name: 'Analyze 3 slides' }))

  await waitFor(() => expect(push).toHaveBeenCalledWith('/'))
  expect(fetchMock).toHaveBeenCalledTimes(3)
  const bodies = fetchMock.mock.calls.map(([, init]) => init.body as FormData)
  expect(bodies.map((b) => (b.get('file') as File).name)).toEqual(['a.png', 'b.png', 'c.png'])
  // the label stays in this browser: only file, scale and organ are sent
  for (const b of bodies) expect([...b.keys()].sort()).toEqual(['file', 'mpp', 'organ'])
  expect(JSON.parse(localStorage.getItem('ssf.case.job2')!)).toMatchObject({ label: 'Block B2' })
  expect(localStorage.getItem('ssf.case.job1')).toBeNull()
})

test('one bad file among several is listed with its reason; the rest still go', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ job_id: 'abc' }))
  render(<UploadForm />)
  fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [png(10, 'a.png'), png(10, 'notes.pdf', 'application/pdf')] } })
  expect(screen.getByRole('alert')).toHaveTextContent(/notes\.pdf.*\.pdf/i)
  expect(screen.getByRole('button', { name: 'Analyze slide' })).toBeEnabled()
})

test('a slide can be taken off the list before sending', async () => {
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), [png(10, 'a.png'), png(10, 'b.png')])
  await userEvent.click(screen.getByRole('button', { name: 'Remove a.png' }))
  expect(screen.queryByText('a.png')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Analyze slide' })).toBeEnabled()
})

test('if one upload fails, the sent ones are marked and the failed one says why; nothing navigates', async () => {
  fetchMock
    .mockResolvedValueOnce(jsonResponse({ job_id: 'ok1' }))
    .mockResolvedValueOnce(jsonResponse({ detail: 'This image could not be read.' }, 400))
  render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), [png(10, 'a.png'), png(10, 'b.png')])
  await userEvent.click(screen.getByRole('button', { name: 'Analyze 2 slides' }))
  expect(await screen.findByText('This image could not be read.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /open a\.png/i })).toHaveAttribute('href', '/jobs/ok1')
  expect(push).not.toHaveBeenCalled()
})

test('organ and scale are remembered for the next upload', async () => {
  localStorage.clear()
  fetchMock.mockResolvedValue(jsonResponse({ job_id: 'abc' }))
  const { unmount } = render(<UploadForm />)
  await userEvent.upload(screen.getByLabelText(/choose an image/i), png())
  await userEvent.selectOptions(screen.getByLabelText(/organ/i), 'breast')
  const scale = screen.getByLabelText(/image scale/i)
  await userEvent.clear(scale)
  await userEvent.type(scale, '0.25')
  await userEvent.click(screen.getByRole('button', { name: 'Analyze slide' }))
  await waitFor(() => expect(push).toHaveBeenCalled())
  unmount()
  render(<UploadForm />)
  expect(screen.getByLabelText(/organ/i)).toHaveValue('breast')
  expect(screen.getByLabelText(/image scale/i)).toHaveValue(0.25)
})
