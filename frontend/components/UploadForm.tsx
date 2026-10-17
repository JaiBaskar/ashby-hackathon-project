'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useId, useState } from 'react'
import { errorMessage } from '@/lib/api'
import { ACCEPTED_EXTENSIONS, fileExtension, organLabel, settings } from '@/lib/format'
import { button } from './ui'

const PREVIEWABLE = ['.png', '.jpg', '.jpeg']

function problemWith(file: File): string | null {
  const ext = fileExtension(file.name)
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `“${ext || file.name}” files aren't supported. Upload a PNG, JPEG, TIFF or SVS image.`
  }
  if (file.size > settings.maxUploadMb * 1024 * 1024) {
    const mb = (file.size / 1024 / 1024).toFixed(0)
    return `This file is ${mb} MB, over the ${settings.maxUploadMb} MB limit. Try a smaller export of the slide.`
  }
  return null
}

export default function UploadForm() {
  const router = useRouter()
  const ids = { file: useId(), scale: useId(), hint: useId(), organ: useId(), organHint: useId() }
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [mpp, setMpp] = useState(String(settings.defaultMpp))
  const [organ, setOrgan] = useState(settings.defaultOrgan)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview])

  function choose(next: File | undefined) {
    if (!next) return
    const problem = problemWith(next)
    setError(problem)
    setFile(problem ? null : next)
    setPreview(!problem && PREVIEWABLE.includes(fileExtension(next.name)) ? URL.createObjectURL(next) : null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file || submitting) return
    const scale = mpp.trim()
    if (scale && !(Number(scale) > 0)) {
      setError('Enter an image scale above 0, or clear the field to use the default.')
      return
    }
    const body = new FormData()
    body.append('file', file)
    if (scale) body.append('mpp', scale)
    body.append('organ', organ)
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch('/api/jobs', { method: 'POST', body })
      if (!res.ok) throw new Error(await errorMessage(res))
      const { job_id } = await res.json()
      router.push(`/jobs/${job_id}`)
    } catch (err) {
      const message = err instanceof TypeError ? "Couldn't reach the server. Check that it's running, then try again." : (err as Error).message
      setError(message)
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-8" noValidate>
      <div
        data-testid="dropzone"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          choose(e.dataTransfer.files?.[0])
        }}
        className={`rounded-lg border-2 border-dashed p-5 transition-colors duration-fast ease-standard sm:p-8 ${
          dragging ? 'border-accent-strong bg-surface-sunken' : 'border-line-strong bg-surface'
        }`}
      >
        {file ? (
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            {preview ? (
              // A local blob preview: plain <img>, nothing for the image optimizer to do.
              <img src={preview} alt={`Preview of ${file.name}`} className="h-40 w-full rounded-md bg-surface-sunken object-contain sm:w-56" />
            ) : (
              <div className="flex h-40 w-full items-center justify-center rounded-md bg-surface-sunken px-4 text-center text-sm text-ink-muted sm:w-56">
                No preview for {fileExtension(file.name).slice(1).toUpperCase()} scans in the browser
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{file.name}</p>
              <p className="mt-1 text-sm text-ink-muted tabular-nums">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              <label htmlFor={ids.file} className={`${button.secondary} mt-4 cursor-pointer`}>
                Choose a different image
              </label>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center py-6 text-center">
            <p className="font-display text-lg">Drag a slide image here</p>
            <p className="mt-1 text-sm text-ink-muted">
              PNG, JPEG, TIFF or SVS, up to {settings.maxUploadMb} MB
            </p>
            <label htmlFor={ids.file} className={`${button.secondary} mt-5 cursor-pointer`}>
              Choose an image
            </label>
          </div>
        )}
        <input
          id={ids.file}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="sr-only"
          onChange={(e) => {
            choose(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>

      <div className="max-w-sm">
        <label htmlFor={ids.organ} className="block font-semibold">
          Organ
        </label>
        <p id={ids.organHint} className="mt-1 text-sm text-ink-muted">
          Where the sample came from. CONCH compares each tile with descriptions of that organ&apos;s tumor and normal
          tissue, which tells them apart much better than generic wording.
        </p>
        <select
          id={ids.organ}
          value={organ}
          onChange={(e) => setOrgan(e.target.value)}
          aria-describedby={ids.organHint}
          className="mt-3 h-11 w-56 rounded-md border border-line-strong bg-surface px-3 text-base text-ink"
        >
          {settings.organs.map((o) => (
            <option key={o} value={o}>
              {organLabel(o)}
            </option>
          ))}
        </select>
      </div>

      <div className="max-w-sm">
        <label htmlFor={ids.scale} className="block font-semibold">
          Image scale (µm/px) <span className="font-normal text-ink-muted">optional</span>
        </label>
        <p id={ids.hint} className="mt-1 text-sm text-ink-muted">
          Scans carry their own scale. For photos, enter it if you know it; otherwise {settings.defaultMpp} is assumed and
          sizes are marked as estimated.
        </p>
        <input
          id={ids.scale}
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          value={mpp}
          onChange={(e) => setMpp(e.target.value)}
          aria-describedby={ids.hint}
          className="mt-3 h-11 w-40 rounded-md border border-line-strong bg-surface px-3 text-base tabular-nums text-ink"
        />
      </div>

      {error && (
        <p role="alert" className="flex gap-2 rounded-md border border-danger/40 bg-surface px-4 py-3 text-danger">
          <span aria-hidden className="font-bold">!</span>
          {error}
        </p>
      )}

      <button type="submit" className={button.primary} disabled={!file || submitting}>
        {submitting && <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-accent-ink border-t-transparent" />}
        {submitting ? 'Uploading…' : 'Analyze slide'}
      </button>
    </form>
  )
}
