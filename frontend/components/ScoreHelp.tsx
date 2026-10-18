'use client'

import { useId, useState } from 'react'
import { settings } from '@/lib/format'

// A "?" next to a score that explains how it's calculated (backend/project/regions.py region_score).
// Opens on hover, keyboard focus or tap; closes on leave, blur or Escape. Weights come from config.yaml.
export default function ScoreHelp() {
  const [open, setOpen] = useState(false)
  const id = useId()
  const { necrosis, variation } = settings.scoreWeights

  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label="How the score is calculated"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false)
        }}
        className="relative inline-flex size-5 cursor-help items-center justify-center rounded-full border border-line-strong font-sans text-xs font-semibold text-ink-muted transition-colors duration-fast hover:border-ink-muted hover:text-ink after:absolute after:-inset-3 after:content-['']"
      >
        <span aria-hidden>?</span>
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute top-full right-0 z-30 mt-2 block w-72 max-w-[calc(100vw-2rem)] rounded-md border border-line-strong bg-surface p-3 text-left font-sans text-sm font-normal text-ink shadow-overlay"
        >
          <span className="block font-semibold">
            Score = tumor − {necrosis} × necrosis − {variation} × unevenness
          </span>
          <span className="mt-2 block text-ink-muted">
            Tumor and necrosis are the average share of each across the box's tiles, as CONCH scored them. Unevenness
            is how much tumor varies from tile to tile (its standard deviation), so an evenly tumor-rich box beats one
            that mixes rich and empty patches. Higher is better. It ranks regions; it isn't a percentage.
          </span>
        </span>
      )}
    </span>
  )
}
