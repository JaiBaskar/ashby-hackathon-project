'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { Result } from '@/lib/api'
import RegionPanel from './RegionPanel'
import SlideViewer from './SlideViewer'
import { button, DemoBadge, ResearchNotice } from './ui'

export default function Results({ result }: { result: Result }) {
  const [selected, setSelected] = useState(result.regions[0]?.rank ?? 0)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const region = result.regions.find((r) => r.rank === selected)
  const n = result.regions.length

  return (
    <main className="mx-auto max-w-6xl animate-enter px-4 py-8 sm:px-6 sm:py-12">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-xl font-normal">Suggested sampling sites</h1>
            <DemoBadge model={result.model} />
          </div>
          <p className="mt-1 text-ink-muted">
            {n} {n === 1 ? 'region' : 'regions'}, ranked by tumor content, necrosis and evenness ·{' '}
            <span className="tabular-nums">{result.tiles.count}</span> tiles analyzed
            {result.tiles.capped ? ' (sampled evenly)' : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={showHeatmap}
            onClick={() => setShowHeatmap((v) => !v)}
            className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-2 text-sm font-medium"
          >
            <span
              aria-hidden
              className={`relative h-5 w-9 rounded-full transition-colors duration-fast ${showHeatmap ? 'bg-accent-strong' : 'bg-line-strong'}`}
            >
              <span
                className={`absolute top-0.5 left-0.5 size-4 rounded-full bg-surface shadow-raised transition-transform duration-fast ease-standard ${
                  showHeatmap ? 'translate-x-4' : ''
                }`}
              />
            </span>
            Tumor heatmap
          </button>
          <Link href="/upload" className={button.secondary}>
            New analysis
          </Link>
        </div>
      </div>

      {result.note && (
        <p className="mt-6 rounded-md border border-line bg-surface px-4 py-3 text-ink">
          {result.note}
        </p>
      )}

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <SlideViewer result={result} selected={selected} onSelect={setSelected} showHeatmap={showHeatmap} />
          <p className="mt-2 text-sm text-ink-muted">Select a numbered box to see why it was chosen.</p>
        </div>
        <div className="lg:sticky lg:top-6">{region && <RegionPanel region={region} result={result} />}</div>
      </div>

      <footer className="mt-10 border-t border-line pt-5">
        <ResearchNotice />
      </footer>
    </main>
  )
}
