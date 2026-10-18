'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useId, useRef, useState } from 'react'
import { errorMessage } from '@/lib/api'
import { writeCase } from '@/lib/casebook'
import { ACCEPTED_EXTENSIONS, fileExtension, organLabel, settings } from '@/lib/format'
import { button } from './ui'

const PREVIEWABLE = ['.png', '.jpg', '.jpeg']
const REMEMBER = 'ssf.upload' // organ and scale from the last upload, in this browser

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

interface Item {
  key: number
  file: File
  preview: string | null
  label: string
  state: 'ready' | 'sending' | 'sent' | 'failed'
  jobId?: string
  error?: string
}

// One or more slides; each becomes its own case. Organ and scale apply to all of them.
export default function UploadForm() {
  const router = useRouter()
  const ids = { file: useId(), scale: useId(), hint: useId(), organ: useId(), organHint: useId() }
  const [items, setItems] = useState<Item[]>([])
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([])
  const [mpp, setMpp] = useState(String(settings.defaultMpp))
  const [organ, setOrgan] = useState(settings.defaultOrgan)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const nextKey = useRef(0)
  const previews = useRef<string[]>([])

  // Last time's organ and scale, after mount so the server render matches.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(REMEMBER) ?? 'null')
      if (saved?.organ && settings.organs.includes(saved.organ)) setOrgan(saved.organ)
      if (typeof saved?.mpp === 'string') setMpp(saved.mpp)
    } catch {}
  }, [])
  useEffect(() => () => previews.current.forEach((p) => URL.revokeObjectURL(p)), [])

  function add(files: FileList | File[] | null | undefined) {
    const list = [...(files ?? [])]
    if (!list.length) return
    const bad: { name: string; reason: string }[] = []
    const good: Item[] = []
    for (const file of list) {
      const problem = problemWith(file)
      if (problem) {
        bad.push({ name: file.name, reason: problem })
        continue
      }
      const preview = PREVIEWABLE.includes(fileExtension(file.name)) ? URL.createObjectURL(file) : null
      if (preview) previews.current.push(preview)
      good.push({ key: nextKey.current++, file, preview, label: '', state: 'ready' })
    }
    setRejected(bad)
    setItems((current) => [...current.filter((i) => i.state !== 'sent'), ...good])
  }

  const update = (key: number, patch: Partial<Item>) => setItems((cur) => cur.map((i) => (i.key === key ? { ...i, ...patch } : i)))
  const toSend = items.filter((i) => i.state === 'ready' || i.state === 'failed')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!toSend.length || submitting) return
    const scale = mpp.trim()
    if (scale && !(Number(scale) > 0)) {
      setError('Enter an image scale above 0, or clear the field to use the default.')
      return
    }
    try {
      localStorage.setItem(REMEMBER, JSON.stringify({ organ, mpp: scale }))
    } catch {}
    setSubmitting(true)
    setError(null)
    const sent: string[] = []
    let failed = false
    // One after another: the server analyzes each in the background, so this only waits for the uploads.
    for (const item of toSend) {
      update(item.key, { state: 'sending', error: undefined })
      const body = new FormData()
      body.append('file', item.file)
      if (scale) body.append('mpp', scale)
      body.append('organ', organ)
      try {
        const res = await fetch('/api/jobs', { method: 'POST', body })
        if (!res.ok) throw new Error(await errorMessage(res))
        const { job_id } = await res.json()
        if (item.label.trim()) writeCase(job_id, { label: item.label.trim() })
        update(item.key, { state: 'sent', jobId: job_id })
        sent.push(job_id)
      } catch (err) {
        failed = true
        const message = err instanceof TypeError ? "Couldn't reach the server. Check that it's running, then try again." : (err as Error).message
        update(item.key, { state: 'failed', error: message })
      }
    }
    setSubmitting(false)
    if (failed) return
    router.push(sent.length === 1 && toSend.length === items.length && items.length === 1 ? `/jobs/${sent[0]}` : '/')
  }

  const n = toSend.length
  const sending = items.findIndex((i) => i.state === 'sending')
  return (
    <form onSubmit={submit} noValidate className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="min-w-0 space-y-4">
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
            add(e.dataTransfer.files)
          }}
          className={`on-stage relative overflow-hidden rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors duration-fast ${
            dragging ? 'border-box-best bg-stage-raised' : 'border-stage-line bg-stage'
          } text-stage-ink`}
        >
          <svg aria-hidden viewBox="0 0 120 48" className="mx-auto h-12 w-32">
            <rect x="1" y="1" width="118" height="46" rx="3" className="fill-stage-raised stroke-stage-muted" strokeWidth="1.5" />
            <rect x="4" y="4" width="28" height="40" rx="2" className="fill-eosin" />
            <path d="M48 28c0-7 6-12 14-12 6 0 8 4 13 4 6 0 11 3 11 8 0 6-6 9-12 9-5 0-7-2-12-2-6 0-14 0-14-7Z" className="fill-class-stroma" />
            <circle cx="64" cy="25" r="5" className="fill-class-tumor" />
          </svg>
          <p className="mt-4 text-lg font-semibold">Drag a slide image here, or several</p>
          <p className="mt-1 text-sm text-stage-muted">
            Scans (SVS, TIFF) or photos (PNG, JPEG), up to <span className="num">{settings.maxUploadMb}</span> MB each. Each slide
            becomes a case.
          </p>
          <label htmlFor={ids.file} className={`${button.primary} mt-5 cursor-pointer`}>
            Choose an image or several
          </label>
          <input
            id={ids.file}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(',')}
            className="sr-only"
            onChange={(e) => {
              add(e.target.files)
              e.target.value = ''
            }}
          />
        </div>

        {rejected.length > 0 && (
          <div role="alert" className="rounded-md border border-danger/40 bg-surface px-4 py-3 text-sm text-danger">
            {rejected.map((r) => (
              <p key={r.name}>
                <span className="font-mono">{r.name}</span>: {r.reason}
              </p>
            ))}
          </div>
        )}

        {items.length > 0 && (
          <ul aria-label="Slides to analyze" className="divide-y divide-line rounded-lg border border-line bg-surface">
            {items.map((item) => (
              <li key={item.key} className="grid animate-enter grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 p-3">
                <div className="flex h-12 items-center justify-center overflow-hidden rounded-sm bg-stage">
                  {item.preview ? (
                    // A local blob preview: plain <img>, nothing for the image optimizer to do.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={item.preview} alt={`Preview of ${item.file.name}`} className="h-full w-full object-contain" />
                  ) : (
                    <span className="font-mono text-[10px] text-stage-muted">{fileExtension(item.file.name).slice(1).toUpperCase()}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.file.name}</p>
                  <p className="num text-xs text-ink-muted">{(item.file.size / 1024 / 1024).toFixed(1)} MB</p>
                  <label className="mt-1.5 flex items-center gap-2 text-xs text-ink-muted">
                    <span className="sr-only">Case label for {item.file.name}</span>
                    <input
                      value={item.label}
                      onChange={(e) => update(item.key, { label: e.target.value })}
                      disabled={item.state === 'sending' || item.state === 'sent'}
                      aria-label={`Case label for ${item.file.name}`}
                      placeholder="Case label, optional"
                      spellCheck={false}
                      className="h-8 w-full max-w-64 rounded-sm border border-line-strong bg-canvas px-2 font-mono text-sm text-ink placeholder:font-sans placeholder:text-xs placeholder:text-ink-muted"
                    />
                  </label>
                  <p className="mt-1 text-[11px] text-ink-muted">Labels stay on this computer.</p>
                  {item.state === 'failed' && (
                    <p role="alert" className="mt-1 text-sm text-danger">
                      {item.error}
                    </p>
                  )}
                </div>
                <div className="text-right text-sm">
                  {item.state === 'sent' ? (
                    <Link href={`/jobs/${item.jobId}`} aria-label={`Open ${item.file.name}`} className="font-medium text-ok hover:underline">
                      Sent ✓
                    </Link>
                  ) : item.state === 'sending' ? (
                    <span className="inline-block size-4 animate-spin rounded-full border-2 border-accent border-t-transparent" aria-label="Sending" />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setItems((cur) => cur.filter((i) => i.key !== item.key))}
                      aria-label={`Remove ${item.file.name}`}
                      className="rounded-sm px-2 py-1 text-ink-muted hover:bg-surface-sunken hover:text-ink"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <aside className="space-y-6 rounded-lg border border-line bg-surface p-5 lg:sticky lg:top-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">For every slide</h2>
        <div>
          <label htmlFor={ids.organ} className="block font-semibold">
            Organ
          </label>
          <p id={ids.organHint} className="mt-1 text-sm text-ink-muted">
            Picks the tissue descriptions CONCH compares each tile with. The right organ separates tumor from normal much better.
          </p>
          <select
            id={ids.organ}
            value={organ}
            onChange={(e) => setOrgan(e.target.value)}
            aria-describedby={ids.organHint}
            className="mt-3 h-10 w-full rounded-sm border border-line-strong bg-canvas px-3 text-base text-ink"
          >
            {settings.organs.map((o) => (
              <option key={o} value={o}>
                {organLabel(o)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={ids.scale} className="block font-semibold">
            Image scale (µm/px) <span className="font-normal text-ink-muted">optional</span>
          </label>
          <p id={ids.hint} className="mt-1 text-sm text-ink-muted">
            Scans carry their own. For photos, enter it if you know it; otherwise <span className="num">{settings.defaultMpp}</span> is
            assumed and sizes are marked as estimated.
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
            className="num mt-3 h-10 w-32 rounded-sm border border-line-strong bg-canvas px-3 text-base text-ink"
          />
        </div>

        {error && (
          <p role="alert" className="flex gap-2 rounded-md border border-danger/40 bg-surface px-3 py-2 text-sm text-danger">
            <span aria-hidden className="font-bold">!</span>
            {error}
          </p>
        )}

        <button type="submit" className={`${button.primary} w-full`} disabled={!n || submitting}>
          {submitting && <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-accent-ink border-t-transparent" />}
          {submitting ? `Sending ${sending + 1} of ${items.length}…` : n > 1 ? `Analyze ${n} slides` : 'Analyze slide'}
        </button>
        <p className="text-xs text-ink-muted">
          Images are deleted from the server once analyzed. Case labels stay on this computer and are never sent.
        </p>
      </aside>
    </form>
  )
}
