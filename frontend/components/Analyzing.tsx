'use client'

import Link from 'next/link'
import { useState } from 'react'
import { type JobStatus, STEPS } from '@/lib/api'
import { STEP_LABELS } from '@/lib/format'
import { button, DemoBadge } from './ui'

const COLS = 12
const ROWS = 8
// Where the "analyzing" step sits in the job's progress (backend/project/api.py run_job).
const ANALYZE_FROM = 0.2
const ANALYZE_TO = 0.9

// How many preview tiles are lit: none before scoring starts, all once ranking begins.
function litTiles(status: JobStatus): number {
  const step = status.step ? STEPS.indexOf(status.step) : 0
  if (step < STEPS.indexOf('analyzing')) return 0
  if (step > STEPS.indexOf('analyzing')) return COLS * ROWS
  const f = Math.min(1, Math.max(0, (status.progress - ANALYZE_FROM) / (ANALYZE_TO - ANALYZE_FROM)))
  return Math.round(f * COLS * ROWS)
}

export default function Analyzing({ id, status }: { id?: string; status: JobStatus }) {
  const [imageFailed, setImageFailed] = useState(false)
  if (status.status === 'error') {
    return (
      <section className="mx-auto max-w-xl animate-enter px-4 py-16 sm:px-6">
        <h1 className="text-xl font-semibold tracking-tight">This slide couldn&apos;t be analyzed</h1>
        <p role="alert" className="mt-4 text-lg text-danger">
          {status.error ?? 'Something went wrong during the analysis.'}
        </p>
        <p className="mt-2 text-ink-muted">Nothing was saved. Pick another image and start again.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/upload" className={button.primary}>
            Try another image
          </Link>
          <Link href="/" className={button.secondary}>
            Back to the worklist
          </Link>
        </div>
      </section>
    )
  }

  const current = status.step ? STEPS.indexOf(status.step) : 0
  const percent = Math.round(status.progress * 100)
  const lit = litTiles(status)
  const haveImage = Boolean(id) && current >= STEPS.indexOf('tiling') && !imageFailed

  return (
    <section className="mx-auto grid max-w-[90rem] animate-enter items-start gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="on-stage relative overflow-hidden rounded-lg bg-stage p-4 text-stage-ink">
        {haveImage ? (
          <div className="relative mx-auto w-fit">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`/api/jobs/${id}/display.png`}
              alt="Your slide, being analyzed"
              onError={() => setImageFailed(true)}
              className="block max-h-[70vh] w-auto max-w-full rounded-sm"
            />
            {/* Tiles light up as they are scored: a picture of progress, not of the real tile grid. */}
            <div aria-hidden className="absolute inset-0 grid" style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)`, gridTemplateRows: `repeat(${ROWS}, 1fr)` }}>
              {Array.from({ length: COLS * ROWS }, (_, i) => (
                <span
                  key={i}
                  data-testid="preview-tile"
                  data-lit={i < lit}
                  className={`border-[0.5px] transition-colors duration-slow ${i < lit ? 'border-transparent bg-transparent' : 'border-stage/40 bg-stage/55'}`}
                />
              ))}
            </div>
            <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
              <span className="absolute inset-x-0 top-0 h-8 animate-sweep border-b border-box-best/70 bg-box-best/10" />
            </div>
          </div>
        ) : (
          <div className="grid aspect-[4/3] place-items-center text-center">
            <div>
              <span aria-hidden className="mx-auto block size-8 animate-spin rounded-full border-2 border-stage-line border-t-box-best" />
              <p className="mt-4 text-stage-muted">Looking for tissue…</p>
            </div>
          </div>
        )}
      </div>

      <div className="lg:pt-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Analyzing your slide</h1>
          <DemoBadge model={status.model} />
        </div>
        <p className="mt-2 text-ink-muted">Usually under a minute. You can leave this page: the case keeps running on the worklist.</p>

        <div
          role="progressbar"
          aria-label="Analysis progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="mt-6 h-1 overflow-hidden rounded-full bg-surface-sunken"
        >
          <div className="h-full rounded-full bg-accent transition-[width] duration-slow ease-standard" style={{ width: `${percent}%` }} />
        </div>
        <p className="num mt-2 text-right text-xs text-ink-muted">{percent}%</p>

        <ol aria-label="Analysis steps" className="mt-4 space-y-1">
          {STEPS.map((step, i) => {
            const state = i < current ? 'done' : i === current ? 'current' : 'todo'
            return (
              <li
                key={step}
                aria-current={state === 'current' ? 'step' : undefined}
                className={`flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors duration-base ${
                  state === 'current' ? 'bg-surface font-semibold text-ink shadow-raised' : state === 'done' ? 'text-ink' : 'text-ink-muted'
                }`}
              >
                <span
                  aria-hidden
                  className={`flex size-5 shrink-0 items-center justify-center rounded-sm border text-[10px] ${
                    state === 'done' ? 'border-accent bg-accent text-accent-ink' : state === 'current' ? 'animate-pulse border-accent-strong' : 'border-line-strong'
                  }`}
                >
                  {state === 'done' ? '✓' : ''}
                </span>
                <span>{STEP_LABELS[step]}</span>
                <span className="num ml-auto text-xs text-ink-muted">{i + 1}/4</span>
                {state === 'done' && <span className="sr-only">, done</span>}
              </li>
            )
          })}
        </ol>
        <p aria-live="polite" className="sr-only">
          Step {current + 1} of {STEPS.length}: {STEP_LABELS[STEPS[current]]}
        </p>
        <Link href="/" className={`${button.quiet} mt-6 px-0`}>
          ← Back to the worklist
        </Link>
      </div>
    </section>
  )
}
