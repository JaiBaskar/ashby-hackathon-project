'use client'

import { useEffect, useId, useState } from 'react'

// The lab's minimum tumor fraction for sequencing. Kept as typed while you edit; saved once it's 1–100.
export default function ThresholdField({ value, onChange }: { value: number; onChange: (pct: number) => void }) {
  const id = useId()
  const [draft, setDraft] = useState(String(value))
  useEffect(() => setDraft(String(value)), [value])
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={id} className="text-ink-muted">
        Minimum tumor for sequencing
      </label>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={1}
        max={100}
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value)
          const n = Number(e.target.value)
          if (e.target.value !== '' && n >= 1 && n <= 100) onChange(n)
        }}
        onBlur={() => setDraft(String(value))}
        className="num h-9 w-16 rounded-sm border border-line-strong bg-surface px-2 text-right text-ink"
      />
      <span aria-hidden className="text-ink-muted">%</span>
    </div>
  )
}
