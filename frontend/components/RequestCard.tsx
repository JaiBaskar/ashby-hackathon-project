import Link from 'next/link'
import type { JobSummary } from '@/lib/api'
import RequestMeta from './RequestMeta'
import { DemoBadge } from './ui'

const STATUS = {
  done: { label: 'Done', className: 'text-accent-strong' },
  running: { label: 'Running', className: 'text-ink-muted' },
  error: { label: 'Failed', className: 'text-danger' },
} as const

// One past analysis. The whole card opens its full results page.
export default function RequestCard({ job, timeZone }: { job: JobSummary; timeZone?: string }) {
  const status = STATUS[job.status]
  return (
    <Link
      href={`/jobs/${job.id}`}
      className="flex h-full flex-col gap-4 rounded-md border border-line bg-surface p-5 transition-colors duration-fast ease-standard hover:border-line-strong hover:bg-surface-sunken"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-display text-lg text-ink">Analysis</span>
        <span className="flex items-center gap-2">
          <DemoBadge model={job.model} />
          <span className={`text-sm font-semibold ${status.className}`}>{status.label}</span>
        </span>
      </div>
      <RequestMeta createdAt={job.created_at} cancerType={job.cancer_type} timeZone={timeZone} />
    </Link>
  )
}
