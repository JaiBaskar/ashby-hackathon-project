import Link from 'next/link'
import { type JobStatus, STEPS } from '@/lib/api'
import { STEP_LABELS } from '@/lib/format'
import { button, DemoBadge } from './ui'

export default function Analyzing({ status }: { status: JobStatus }) {
  if (status.status === 'error') {
    return (
      <section className="mx-auto max-w-xl animate-enter px-4 py-16 sm:px-6">
        <h1 className="font-display text-xl font-normal">We couldn&apos;t analyze this image</h1>
        <p role="alert" className="mt-4 text-lg text-danger">
          {status.error ?? 'Something went wrong during the analysis.'}
        </p>
        <p className="mt-2 text-ink-muted">Nothing was saved. Pick another image and start again.</p>
        <Link href="/upload" className={`${button.primary} mt-8`}>
          Try another image
        </Link>
      </section>
    )
  }

  const current = status.step ? STEPS.indexOf(status.step) : 0
  const percent = Math.round(status.progress * 100)

  return (
    <section className="mx-auto max-w-xl animate-enter px-4 py-16 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-xl font-normal">Analyzing your slide</h1>
        <DemoBadge model={status.model} />
      </div>
      <p className="mt-2 text-ink-muted">This usually takes under a minute. You can keep this page open or come back to its link.</p>

      <div
        role="progressbar"
        aria-label="Analysis progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-8 h-1.5 overflow-hidden rounded-full bg-surface-sunken"
      >
        <div className="h-full rounded-full bg-accent transition-[width] duration-slow ease-standard" style={{ width: `${percent}%` }} />
      </div>

      <ol aria-label="Analysis steps" className="mt-8 space-y-1">
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
                className={`flex size-6 shrink-0 items-center justify-center rounded-full border-2 text-xs ${
                  state === 'done'
                    ? 'border-accent-strong bg-accent-strong text-surface'
                    : state === 'current'
                      ? 'animate-pulse border-accent-strong'
                      : 'border-line-strong'
                }`}
              >
                {state === 'done' ? '✓' : ''}
              </span>
              <span>{STEP_LABELS[step]}</span>
              {state === 'done' && <span className="sr-only">, done</span>}
            </li>
          )
        })}
      </ol>
      <p aria-live="polite" className="sr-only">
        Step {current + 1} of {STEPS.length}: {STEP_LABELS[STEPS[current]]}
      </p>
    </section>
  )
}
