'use client'

import Link from 'next/link'
import { useId, useState } from 'react'
import type { Result } from '@/lib/api'
import { formatCreated, organLabel } from '@/lib/format'
import { button, Chip, DemoBadge } from './ui'

// The strip above the workspace: which case this is, and what you can do with it.
export default function CaseBar({
  id,
  result,
  label,
  onLabel,
  createdAt,
  cancerType,
  timeZone,
  onCopy,
  nav,
}: {
  id?: string
  result: Result
  label: string
  onLabel: (label: string) => void
  createdAt?: string | null
  cancerType?: string | null
  timeZone?: string
  onCopy: () => Promise<boolean>
  nav?: React.ReactNode
}) {
  const field = useId()
  const [copied, setCopied] = useState<'idle' | 'ok' | 'failed'>('idle')

  async function copy() {
    const ok = await onCopy()
    setCopied(ok ? 'ok' : 'failed')
    setTimeout(() => setCopied('idle'), 1800)
  }

  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <Link href="/" className="text-sm font-medium text-accent-strong hover:underline">
          ← Worklist
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-xl font-semibold tracking-tight">
            <span className="mr-2 text-ink-muted">Case</span>
            <input
              id={field}
              aria-label="Case label"
              value={label}
              onChange={(e) => onLabel(e.target.value)}
              placeholder="add a label"
              spellCheck={false}
              size={Math.max(10, label.length + 1)}
              title="Stays on this computer. Never sent to the server."
              className="rounded-sm border border-dashed border-line-strong bg-transparent px-2 py-0.5 font-mono text-lg font-medium text-ink placeholder:font-sans placeholder:text-base placeholder:font-normal placeholder:text-ink-muted hover:border-ink-muted focus:border-solid"
            />
          </h1>
          {result.organ && <Chip>Organ: {organLabel(result.organ)}</Chip>}
          {cancerType && <Chip tone="eosin">{cancerType}</Chip>}
          <DemoBadge model={result.model} />
        </div>
        <p className="mt-2 text-sm text-ink-muted">
          {createdAt && (
            <>
              <time dateTime={createdAt} className="num" suppressHydrationWarning>
                {formatCreated(createdAt, timeZone)}
              </time>
              {' · '}
            </>
          )}
          <span className="num">{result.tiles.count}</span> tiles scored{result.tiles.capped ? ' (sampled evenly)' : ''} · label stays on
          this computer
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {nav}
        <button type="button" onClick={copy} className={button.secondary} aria-live="polite">
          {copied === 'ok' ? 'Copied' : copied === 'failed' ? 'Copy failed' : 'Copy summary'}
        </button>
        {id && (
          <Link href={`/jobs/${id}/sheet`} className={button.primary}>
            Sampling sheet
          </Link>
        )}
      </div>
    </div>
  )
}
