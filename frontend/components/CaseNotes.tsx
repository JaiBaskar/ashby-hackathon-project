'use client'

import { useId } from 'react'
import type { CaseEntry } from '@/lib/casebook'

// Notes and the reviewed tick for one case. Like the label, they stay in this browser.
export default function CaseNotes({ entry, onChange }: { entry: CaseEntry; onChange: (patch: Partial<CaseEntry>) => void }) {
  const id = useId()
  return (
    <section aria-labelledby={`${id}-h`} className="rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id={`${id}-h`} className="text-sm font-semibold">
          Notes
        </h2>
        <label className="flex min-h-9 cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={entry.reviewed}
            onChange={(e) => onChange({ reviewed: e.target.checked })}
            className="size-4 accent-accent"
          />
          Reviewed
        </label>
      </div>
      <label htmlFor={`${id}-notes`} className="sr-only">
        Notes
      </label>
      <textarea
        id={`${id}-notes`}
        value={entry.notes}
        onChange={(e) => onChange({ notes: e.target.value })}
        rows={3}
        placeholder="e.g. avoid the cautery edge; block A3 preferred"
        className="mt-2 w-full resize-y rounded-sm border border-line-strong bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-muted"
      />
      <p className="mt-1 text-xs text-ink-muted">Stays on this computer. Never sent to the server.</p>
    </section>
  )
}
