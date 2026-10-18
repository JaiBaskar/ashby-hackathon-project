'use client'

import Link from 'next/link'
import { useEffect, useId, useMemo, useState } from 'react'
import type { JobList, JobSummary } from '@/lib/api'
import { meets, useCasebook, useThreshold, writeCase } from '@/lib/casebook'
import { formatCreated, organLabel, pct } from '@/lib/format'
import { button, Chip, DemoBadge } from './ui'

const POLL_MS = 2000
type Status = 'all' | JobSummary['status']
type Seq = 'all' | 'meets' | 'below'

// The pathologist's list of cases: what's running, what's ready for sequencing, what still needs a look.
export default function Worklist({ initial, timeZone }: { initial: JobList; timeZone?: string }) {
  const [list, setList] = useState(initial)
  const caseOf = useCasebook()
  const [threshold] = useThreshold()
  const ids = { search: useId(), status: useId(), organ: useId(), seq: useId() }
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>('all')
  const [organ, setOrgan] = useState('all')
  const [seq, setSeq] = useState<Seq>('all')
  const [hideReviewed, setHideReviewed] = useState(false)

  // Running cases update themselves; the list stops asking once nothing is running.
  const running = list.jobs.some((j) => j.status === 'running')
  useEffect(() => {
    if (!running) return
    let active = true
    const timer = setInterval(async () => {
      try {
        const res = await fetch('/api/jobs', { cache: 'no-store' })
        if (res.ok && active) setList(await res.json())
      } catch {}
    }, POLL_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [running])

  const organs = useMemo(() => [...new Set(list.jobs.map((j) => j.organ).filter(Boolean))] as string[], [list])
  const shown = list.jobs.filter((j) => {
    const c = caseOf(j.id)
    const q = query.trim().toLowerCase()
    if (q && !c.label.toLowerCase().includes(q) && !j.id.includes(q)) return false
    if (status !== 'all' && j.status !== status) return false
    if (organ !== 'all' && j.organ !== organ) return false
    if (seq !== 'all') {
      if (j.best_tumor == null) return false
      if (meets(j.best_tumor, threshold) !== (seq === 'meets')) return false
    }
    return !(hideReviewed && c.reviewed)
  })
  const ready = list.jobs.filter((j) => j.best_tumor != null && meets(j.best_tumor, threshold)).length
  const nRunning = list.jobs.filter((j) => j.status === 'running').length

  const select = 'h-9 rounded-sm border border-line-strong bg-surface px-2 text-sm text-ink'
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Worklist</h1>
          <p data-testid="worklist-counts" className="num mt-1 text-sm text-ink-muted">
            {list.jobs.length} {list.jobs.length === 1 ? 'case' : 'cases'} · {nRunning} running · {ready} ready for sequencing
          </p>
        </div>
        <Link href="/upload" className={button.primary}>
          + New case
        </Link>
      </div>

      {list.store === 'memory' && (
        <p className="mt-5 rounded-md border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-ink">
          This list isn&apos;t saved: no database is configured, so it empties when the server restarts. Labels, notes and
          reviewed ticks are kept in this browser either way.
        </p>
      )}

      {list.jobs.length === 0 ? (
        <EmptyBench />
      ) : (
        <>
          <div role="search" className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3 border-y border-line py-3">
            <label htmlFor={ids.search} className="sr-only">
              Search cases
            </label>
            <input
              id={ids.search}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search label or ID"
              className="h-9 w-56 rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-muted"
            />
            <Filter id={ids.status} label="Status" value={status} onChange={(v) => setStatus(v as Status)} className={select}>
              <option value="all">All</option>
              <option value="running">Running</option>
              <option value="done">Done</option>
              <option value="error">Failed</option>
            </Filter>
            <Filter id={ids.organ} label="Organ" value={organ} onChange={setOrgan} className={select}>
              <option value="all">All</option>
              {organs.map((o) => (
                <option key={o} value={o}>
                  {organLabel(o)}
                </option>
              ))}
            </Filter>
            <Filter id={ids.seq} label="Sequencing" value={seq} onChange={(v) => setSeq(v as Seq)} className={select}>
              <option value="all">All</option>
              <option value="meets">≥ {threshold}% tumor</option>
              <option value="below">Below {threshold}%</option>
            </Filter>
            <label className="flex items-center gap-2 text-sm text-ink-muted">
              <input type="checkbox" checked={hideReviewed} onChange={(e) => setHideReviewed(e.target.checked)} className="size-4 accent-accent" />
              Hide reviewed
            </label>
          </div>

          {shown.length === 0 ? (
            <p className="mt-8 text-ink-muted">No cases match these filters.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line">
              {shown.map((j, i) => (
                <CaseRow key={j.id} job={j} label={caseOf(j.id).label} reviewed={caseOf(j.id).reviewed} threshold={threshold} timeZone={timeZone} index={i} />
              ))}
            </ul>
          )}
        </>
      )}
    </>
  )
}

function Filter({
  id,
  label,
  value,
  onChange,
  className,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  className: string
  children: React.ReactNode
}) {
  return (
    <span className="flex items-center gap-2 text-sm">
      <label htmlFor={id} className="text-ink-muted">
        {label}
      </label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={className}>
        {children}
      </select>
    </span>
  )
}

const STATUS = {
  done: { label: 'Done', className: 'text-ink-muted' },
  running: { label: 'Running', className: 'text-accent-strong' },
  error: { label: 'Failed', className: 'text-danger' },
} as const

function CaseRow({
  job,
  label,
  reviewed,
  threshold,
  timeZone,
  index,
}: {
  job: JobSummary
  label: string
  reviewed: boolean
  threshold: number
  timeZone?: string
  index: number
}) {
  const short = job.id.slice(0, 8)
  const ok = job.best_tumor != null && meets(job.best_tumor, threshold)
  return (
    <li
      style={{ animationDelay: `${Math.min(index, 12) * 30}ms` }}
      className={`group relative grid animate-enter grid-cols-[5.5rem_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 py-3 sm:grid-cols-[7rem_minmax(0,1.4fr)_minmax(0,1fr)_6rem_auto] ${
        reviewed ? 'opacity-70' : ''
      }`}
    >
      <Thumb job={job} />
      <div className="min-w-0">
        <Link
          href={`/jobs/${job.id}`}
          aria-label={`Open case ${label || short}`}
          className="block truncate font-mono text-base font-medium text-ink after:absolute after:inset-0 after:content-[''] hover:text-accent-strong"
        >
          {label || <span className="text-ink-muted">{short}…</span>}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          {job.organ && <Chip>{organLabel(job.organ)}</Chip>}
          {job.cancer_type && <Chip tone="eosin">{job.cancer_type}</Chip>}
          <DemoBadge model={job.model} />
          <time dateTime={job.created_at} className="num" suppressHydrationWarning>
            {formatCreated(job.created_at, timeZone)}
          </time>
        </div>
      </div>
      <div className="col-start-2 sm:col-start-auto">
        {job.status === 'running' ? (
          <div>
            <span className={`text-sm font-semibold ${STATUS.running.className}`}>Running</span>
            <div
              role="progressbar"
              aria-label="Analysis progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round((job.progress ?? 0) * 100)}
              className="mt-1.5 h-1 w-32 overflow-hidden rounded-full bg-surface-sunken"
            >
              <div className="h-full bg-accent transition-[width] duration-slow" style={{ width: `${(job.progress ?? 0) * 100}%` }} />
            </div>
          </div>
        ) : job.status === 'error' ? (
          <span className={`text-sm font-semibold ${STATUS.error.className}`}>Failed</span>
        ) : job.best_tumor != null ? (
          <div className="flex items-baseline gap-3">
            <span className="num text-xl font-semibold text-ink">{pct(job.best_tumor)}</span>
            <span className="text-xs text-ink-muted">
              tumor, best region
              {job.best_necrosis != null && (
                <>
                  <br />
                  <span className="num">{pct(job.best_necrosis)}</span> necrosis
                </>
              )}
            </span>
          </div>
        ) : (
          <span className="text-sm text-ink-muted">No region fits</span>
        )}
      </div>
      <div className="hidden sm:block">
        {job.best_tumor != null && (
          <span data-testid="seq">
            <Chip tone={ok ? 'ok' : 'warn'}>
              {ok ? '≥' : '<'} {threshold}%
            </Chip>
          </span>
        )}
      </div>
      <label className="relative z-10 row-span-2 flex min-h-11 cursor-pointer items-center gap-2 justify-self-end text-xs text-ink-muted sm:row-span-1">
        <input
          type="checkbox"
          checked={reviewed}
          onChange={(e) => writeCase(job.id, { reviewed: e.target.checked })}
          aria-label={`Reviewed: ${label || short}`}
          className="size-4 accent-accent"
        />
        <span aria-hidden>Reviewed</span>
      </label>
    </li>
  )
}

// The slide as a small glass slide: the image, with region 1 marked in the same marker ink as on the stage.
function Thumb({ job }: { job: JobSummary }) {
  const [w, h] = job.image_size ?? [4, 3]
  const box = job.best_box
  return (
    <div data-testid="thumb" className="relative row-span-2 flex aspect-[7/3] items-center overflow-hidden rounded-sm bg-stage p-1 sm:row-span-1">
      <span aria-hidden className="h-full w-3 shrink-0 rounded-[2px] bg-eosin/80" />
      <div className="relative ml-1 h-full flex-1">
        {job.status !== 'error' && (
          <div className="relative mx-auto h-full" style={{ aspectRatio: `${w} / ${h}` }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/jobs/${job.id}/display.png`} alt="" loading="lazy" className="h-full w-full object-contain" />
            {box && (
              <span
                data-testid="thumb-box"
                className="absolute border border-box-best"
                style={{ left: `${(box[0] / w) * 100}%`, top: `${(box[1] / h) * 100}%`, width: `${(box[2] / w) * 100}%`, height: `${(box[3] / h) * 100}%` }}
              />
            )}
            {job.status === 'running' && <span aria-hidden className="absolute inset-x-0 top-0 h-1/3 animate-sweep bg-box-best/20" />}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyBench() {
  return (
    <div className="mt-10 grid place-items-center rounded-lg border border-dashed border-line-strong px-6 py-14 text-center">
      <svg aria-hidden viewBox="0 0 120 48" className="h-12 w-32">
        <rect x="1" y="1" width="118" height="46" rx="3" className="fill-surface stroke-line-strong" strokeWidth="1.5" />
        <rect x="4" y="4" width="28" height="40" rx="2" className="fill-eosin/70" />
        <rect x="56" y="14" width="30" height="20" rx="1" className="fill-none stroke-ink-muted" strokeWidth="1.5" strokeDasharray="3 2" />
      </svg>
      <p className="mt-5 text-lg font-semibold">No cases yet.</p>
      <p className="mt-1 max-w-sm text-sm text-ink-muted">
        Start with a scan or a photo of an H&amp;E slide. Each slide becomes a case on this list.
      </p>
      <Link href="/upload" className={`${button.primary} mt-6`}>
        + New case
      </Link>
    </div>
  )
}
