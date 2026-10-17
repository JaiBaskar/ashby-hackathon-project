import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '@/test/fixtures'
import UploadForm from './UploadForm'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

const fetchMock = vi.fn()
beforeEach(() => {
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
