import { cancerTypeLabel, formatCreated } from '@/lib/format'

// The two facts every request shows: its most likely cancer type and when it was created.
export default function RequestMeta({
  createdAt,
  cancerType,
  timeZone,
}: {
  createdAt: string
  cancerType: string | null | undefined
  timeZone?: string
}) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      <dt className="text-ink-muted">Cancer type</dt>
      <dd className={cancerType ? 'font-semibold text-ink' : 'text-ink-muted'}>{cancerTypeLabel(cancerType)}</dd>
      <dt className="text-ink-muted">Created</dt>
      <dd>
        <time dateTime={createdAt} className="tabular-nums" suppressHydrationWarning>
          {formatCreated(createdAt, timeZone)}
        </time>
      </dd>
    </dl>
  )
}
