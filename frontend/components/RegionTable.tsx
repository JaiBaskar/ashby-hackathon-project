'use client'

import { useState } from 'react'
import type { Composition, Region } from '@/lib/api'
import { meets } from '@/lib/casebook'
import { pct } from '@/lib/format'

export interface Row {
  key: number | 'free'
  label: string
  composition: Composition
  score: number
  size: string
  coverage: number
}

type Column = 'rank' | 'tumor' | 'necrosis' | 'score' | 'coverage'
const COLUMNS: { key: Column; label: string; title: string }[] = [
  { key: 'rank', label: 'Rank', title: 'Rank' },
  { key: 'tumor', label: 'Tumor', title: 'Tumor fraction' },
  { key: 'necrosis', label: 'Necrosis', title: 'Necrosis fraction' },
  { key: 'score', label: 'Score', title: 'Ranking score: tumor − necrosis − ½ × unevenness' },
]

export function regionRows(regions: Region[]): Row[] {
  return regions.map((r) => ({
    key: r.rank,
    label: String(r.rank),
    composition: r.composition,
    score: r.score,
    size: r.size_um == null ? '—' : `${Math.round(r.size_um)}`,
    coverage: r.tissue_coverage,
  }))
}

const value = (row: Row, col: Column) =>
  col === 'rank' ? (row.key === 'free' ? Infinity : row.key) : col === 'score' ? row.score : col === 'coverage' ? row.coverage : row.composition[col]

// Every region side by side, like an instrument printout. A row selects its box on the slide.
export default function RegionTable({
  rows,
  selected,
  threshold,
  onSelect,
}: {
  rows: Row[]
  selected: number | 'free'
  threshold: number
  onSelect: (key: number | 'free') => void
}) {
  const [sort, setSort] = useState<{ col: Column; dir: 1 | -1 }>({ col: 'rank', dir: 1 })
  const sorted = [...rows].sort((a, b) => (value(a, sort.col) - value(b, sort.col)) * sort.dir || value(a, 'rank') - value(b, 'rank'))

  function sortBy(col: Column) {
    // Rank, necrosis: low first. Tumor, score, coverage: high first. Clicking again flips it.
    const natural: 1 | -1 = col === 'rank' || col === 'necrosis' ? 1 : -1
    setSort((s) => (s.col === col ? { col, dir: (s.dir * -1) as 1 | -1 } : { col, dir: natural }))
  }

  const header = (key: Column, label: string, title: string, className = '') => (
    <th
      key={key}
      scope="col"
      aria-sort={sort.col === key ? (sort.dir === 1 ? 'ascending' : 'descending') : undefined}
      className={`px-3 py-2 font-medium ${className}`}
    >
      <button type="button" title={title} onClick={() => sortBy(key)} className="inline-flex items-center gap-1 rounded-sm hover:text-ink">
        {label}
        <span aria-hidden className={`text-[10px] ${sort.col === key ? 'opacity-100' : 'opacity-0'}`}>
          {sort.dir === 1 ? '▲' : '▼'}
        </span>
      </button>
    </th>
  )

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table aria-label="Regions" className="w-full min-w-[34rem] border-collapse text-left text-sm">
        <thead className="border-b border-line text-xs uppercase tracking-wide text-ink-muted">
          <tr>
            {COLUMNS.map((c) => header(c.key, c.label, c.title, c.key === 'rank' ? '' : 'text-right'))}
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Size µm
            </th>
            {header('coverage', 'Tissue', 'Share of the box on tissue', 'text-right')}
            <th scope="col" className="px-3 py-2 text-right font-medium" title={`Minimum tumor fraction for sequencing: ${threshold}%`}>
              Seq.
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const isSelected = row.key === selected
            const ok = meets(row.composition.tumor, threshold)
            return (
              <tr
                key={row.key}
                aria-selected={isSelected}
                aria-label={row.key === 'free' ? 'Yours' : undefined}
                onClick={() => onSelect(row.key)}
                className={`cursor-pointer border-b border-line last:border-0 transition-colors duration-fast ${
                  isSelected ? 'bg-accent/10' : 'hover:bg-surface-sunken'
                }`}
              >
                <th scope="row" className="relative px-3 py-2 font-mono font-semibold">
                  {isSelected && <span aria-hidden className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-accent" />}
                  <button
                    type="button"
                    aria-label={row.key === 'free' ? 'Select your box' : `Select region ${row.key}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelect(row.key)
                    }}
                    className="rounded-sm"
                  >
                    {row.label}
                  </button>
                </th>
                <td className="num px-3 py-2 text-right font-semibold">{pct(row.composition.tumor)}</td>
                <td className="num px-3 py-2 text-right">{pct(row.composition.necrosis)}</td>
                <td className="num px-3 py-2 text-right">{row.score.toFixed(2)}</td>
                <td className="num px-3 py-2 text-right text-ink-muted">{row.size}</td>
                <td className="num px-3 py-2 text-right text-ink-muted">{pct(row.coverage)}</td>
                <td data-testid="meets" className={`num px-3 py-2 text-right font-semibold ${ok ? 'text-ok' : 'text-warn'}`}>
                  {ok ? '≥' : '<'} {threshold}%
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
