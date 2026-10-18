'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import type { JobList } from '@/lib/api'

// Previous / next case in worklist order (newest first), so a batch can be read without going back to the list.
export default function CaseNav({ id }: { id: string }) {
  const [ids, setIds] = useState<string[] | null>(null)
  useEffect(() => {
    let active = true
    fetch('/api/jobs', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((list: JobList | null) => active && list && setIds(list.jobs.map((j) => j.id)))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  const i = ids?.indexOf(id) ?? -1
  const prev = i > 0 ? ids![i - 1] : null
  const next = i >= 0 && i < ids!.length - 1 ? ids![i + 1] : null

  const keys = useRef<(e: KeyboardEvent) => void>(() => {})
  keys.current = (e) => {
    const t = e.target as HTMLElement | null
    if (e.ctrlKey || e.metaKey || e.altKey || (t && (t.closest('input, textarea, select') || t.isContentEditable))) return
    const to = e.key === 'j' || e.key === 'J' ? next : e.key === 'k' || e.key === 'K' ? prev : null
    if (to) window.location.assign(`/jobs/${to}`)
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keys.current(e)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!ids || i < 0 || ids.length < 2) return null
  const link = 'inline-flex size-11 items-center justify-center rounded-md border border-line-strong bg-surface text-ink hover:bg-surface-sunken'
  return (
    <div className="flex items-center gap-1.5">
      {prev ? (
        <Link href={`/jobs/${prev}`} aria-label="Previous case (K)" title="Previous case (K)" className={link}>
          ‹
        </Link>
      ) : (
        <span aria-hidden className={`${link} opacity-40`}>‹</span>
      )}
      <span className="num w-14 text-center text-xs text-ink-muted">
        {i + 1} / {ids.length}
      </span>
      {next ? (
        <Link href={`/jobs/${next}`} aria-label="Next case (J)" title="Next case (J)" className={link}>
          ›
        </Link>
      ) : (
        <span aria-hidden className={`${link} opacity-40`}>›</span>
      )}
    </div>
  )
}
