'use client'

import { useEffect, useRef, useState } from 'react'
import { errorMessage, type MeasuredBox, type RegionsAtSize, type Result } from '@/lib/api'
import { readCase, useCase, useThreshold } from '@/lib/casebook'
import { boxLabel, pct } from '@/lib/format'
import { caseSummary } from '@/lib/summary'
import CaseBar from './CaseBar'
import CaseNotes from './CaseNotes'
import type { Rect } from './FreeBox'
import FreeBoxPanel from './FreeBoxPanel'
import RegionPanel from './RegionPanel'
import RegionTable, { regionRows, type Row } from './RegionTable'
import SlideStage, { zoomIn, zoomOut } from './SlideStage'
import ThresholdField from './ThresholdField'
import { ResearchNotice } from './ui'

// Box sizes the backend offers. Changing size re-ranks the job's stored tile scores (no new model run);
// each size is fetched once and kept, and the first size comes with the result.
function BoxSize({ sizes, value, loading, onChange }: { sizes: number[]; value: number; loading: boolean; onChange: (um: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Box size for suggestions" aria-busy={loading} className="flex items-center gap-2 text-sm">
      <span aria-hidden className="text-ink-muted">Suggest boxes of</span>
      <div className="inline-flex rounded-md border border-line-strong bg-surface p-0.5">
        {sizes.map((um) => (
          <label
            key={um}
            className={`relative inline-flex min-h-9 cursor-pointer items-center rounded-sm px-2.5 font-mono text-xs font-medium transition-colors duration-fast has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus has-[:disabled]:cursor-wait ${
              um === value ? 'bg-accent text-accent-ink' : 'text-ink hover:bg-surface-sunken'
            }`}
          >
            <input
              type="radio"
              name="box-size"
              value={um}
              checked={um === value}
              disabled={loading}
              onChange={() => onChange(um)}
              className="sr-only"
            />
            {boxLabel(um)}
          </label>
        ))}
      </div>
    </div>
  )
}

export default function Results({
  id,
  result: initial,
  meta,
  timeZone,
  nav,
}: {
  id?: string
  result: Result
  meta?: { created_at?: string | null; cancer_type?: string | null }
  timeZone?: string
  nav?: React.ReactNode
}) {
  const [entry, updateCase] = useCase(id)
  const [threshold, setThreshold] = useThreshold()
  const [zoom, setZoom] = useState(1)
  const [heatmapOpacity, setHeatmapOpacity] = useState(100)
  const cache = useRef(new Map<number, RegionsAtSize>())
  const [boxUm, setBoxUm] = useState(initial.box_um)
  const [loading, setLoading] = useState(false)
  const [sizeError, setSizeError] = useState<string | null>(null)
  const sized = boxUm === initial.box_um ? null : cache.current.get(boxUm)
  const result: Result = sized ? { ...initial, box_um: sized.box_um, regions: sized.regions, note: sized.note } : initial
  const [selected, setSelected] = useState<number | 'free'>(result.regions[0]?.rank ?? 0)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const region = result.regions.find((r) => r.rank === selected)
  const n = result.regions.length

  // The user's own box: drawn, adjusted from a suggestion, or placed from the keyboard. It's measured from the
  // job's stored tile scores; only the latest request's answer is shown.
  const [free, setFree] = useState<Rect | null>(null)
  const [drawing, setDrawing] = useState(false)
  const [measured, setMeasured] = useState<MeasuredBox | null>(null)
  const [measuring, setMeasuring] = useState(false)
  const [measureError, setMeasureError] = useState<string | null>(null)
  const freeRef = useRef<HTMLDivElement>(null)
  const focusFree = useRef(false)
  const latestRequest = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  // Live scoring: at most one request out at a time; while it's out, only the newest box waits to go next.
  const inFlight = useRef(false)
  const pending = useRef<Rect | null>(null)
  const drewNew = useRef(false) // this drawing gesture has already put a box on the slide

  useEffect(() => () => clearTimeout(timer.current), [])
  // Your box from last time on this computer comes back (after mount, so the server render matches).
  useEffect(() => {
    const saved = id ? readCase(id).box : null
    if (saved) {
      setFree(saved)
      measureLive(saved)
    }
    // once per case
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])
  useEffect(() => {
    if (id && measured && free) updateCase({ box: free })
  }, [id, measured, free, updateCase])
  useEffect(() => {
    if (focusFree.current && free) freeRef.current?.focus()
    focusFree.current = false
  }, [free])
  useEffect(() => {
    if (!drawing) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawing(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawing])

  async function measureNow(rect: Rect) {
    const id = ++latestRequest.current
    setMeasuring(true)
    const round = (v: number) => String(Number(v.toFixed(1)))
    const query = new URLSearchParams({ x: round(rect.x), y: round(rect.y), w: round(rect.w), h: round(rect.h) })
    try {
      const res = await fetch(`${initial.measure_url}?${query}`, { cache: 'no-store' })
      if (!res.ok) throw new Error(await errorMessage(res))
      const body: MeasuredBox = await res.json()
      if (id !== latestRequest.current) return
      setMeasured(body)
      setMeasureError(null)
    } catch (err) {
      if (id !== latestRequest.current) return
      setMeasured(null)
      setMeasureError(err instanceof TypeError ? "Couldn't reach the server. Check that it's running." : (err as Error).message)
    } finally {
      if (id === latestRequest.current) setMeasuring(false)
    }
  }

  async function pump() {
    while (pending.current && !inFlight.current) {
      const rect = pending.current
      pending.current = null
      inFlight.current = true
      try {
        await measureNow(rect)
      } finally {
        inFlight.current = false
      }
    }
  }

  function measureLive(rect: Rect) {
    pending.current = rect
    pump()
  }

  // Every change re-scores the box: pointer moves and releases right away (throttled to one request at a
  // time), arrow keys once they stop for 300 ms.
  function changeFree(rect: Rect, when: 'drag' | 'now' | 'soon') {
    if (selected !== 'free') {
      // a new box (drawn, or grabbed from a suggestion): don't show the previous box's numbers
      latestRequest.current++
      setMeasured(null)
      setMeasureError(null)
    }
    setFree(rect)
    setSelected('free')
    clearTimeout(timer.current)
    if (when === 'soon') timer.current = setTimeout(() => measureLive(rect), 300)
    else measureLive(rect)
  }

  function placeFree(rect: Rect, focus = false) {
    setDrawing(false)
    setMeasured(null)
    setMeasureError(null)
    focusFree.current = focus
    changeFree(rect, 'now')
  }

  function removeFree() {
    if (id) updateCase({ box: null })
    clearTimeout(timer.current)
    pending.current = null
    latestRequest.current++
    setFree(null)
    setMeasured(null)
    setMeasureError(null)
    setMeasuring(false)
    setSelected(result.regions[0]?.rank ?? 0)
  }

  // Pointer: switch to drawing mode. Keyboard (no pointer to drag with): place a box the size of the best
  // region in the middle of the image and focus it, so the arrow keys take over.
  function drawButton(e: React.MouseEvent) {
    if (drawing) return setDrawing(false)
    drewNew.current = false
    if (e.detail !== 0) return setDrawing(true)
    const { width, height } = result.image
    const w = result.regions[0]?.w ?? width / 4
    const h = result.regions[0]?.h ?? w
    placeFree({ x: (width - w) / 2, y: (height - h) / 2, w, h }, true)
  }

  async function copySummary(): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(caseSummary(result, threshold, entry.label, free ? measured : null))
      return true
    } catch {
      return false
    }
  }

  // Keyboard shortcuts (listed in the ? sheet). They stay out of the way while you type in a field.
  const keys = useRef<(e: KeyboardEvent) => void>(() => {})
  keys.current = (e: KeyboardEvent) => {
    const t = e.target as HTMLElement | null
    if (e.ctrlKey || e.metaKey || e.altKey || (t && (t.closest('input, textarea, select') || t.isContentEditable))) return
    const rank = Number(e.key)
    if (rank >= 1 && rank <= 9 && result.regions.some((r) => r.rank === rank)) setSelected(rank)
    else if (e.key === 'h' || e.key === 'H') setShowHeatmap((v) => !v)
    else if (e.key === 'd' || e.key === 'D') {
      drewNew.current = false
      setDrawing(true)
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && free) removeFree()
    else if (e.key === '+' || e.key === '=') setZoom(zoomIn)
    else if (e.key === '-' || e.key === '_') setZoom(zoomOut)
    else if (e.key === '0') setZoom(1)
    else if ((e.key === 'p' || e.key === 'P') && id) window.location.assign(`/jobs/${id}/sheet`)
    else return
    e.preventDefault()
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keys.current(e)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const rows: Row[] = regionRows(result.regions)
  if (free && measured) {
    rows.push({
      key: 'free',
      label: 'Yours',
      composition: measured.composition,
      score: measured.score,
      size: `${Math.round(measured.width_um)}×${Math.round(measured.height_um)}`,
      coverage: measured.tissue_coverage,
    })
  }

  function show(um: number, regions: RegionsAtSize['regions']) {
    setBoxUm(um)
    setSelected(regions[0]?.rank ?? 0)
  }

  async function changeBox(um: number) {
    setSizeError(null)
    const cached = um === initial.box_um ? initial : cache.current.get(um)
    if (cached) return show(um, cached.regions)
    setLoading(true)
    try {
      const res = await fetch(`${initial.regions_url}?box_um=${um}`, { cache: 'no-store' })
      if (!res.ok) throw new Error(await errorMessage(res))
      const next: RegionsAtSize = await res.json()
      cache.current.set(um, next)
      show(um, next.regions)
    } catch (err) {
      setSizeError(err instanceof TypeError ? "Couldn't reach the server. Check that it's running." : (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-[90rem] animate-enter px-4 py-6 sm:px-6 sm:py-8">
      <CaseBar
        id={id}
        result={result}
        label={entry.label}
        onLabel={(label) => updateCase({ label })}
        createdAt={meta?.created_at}
        cancerType={meta?.cancer_type}
        timeZone={timeZone}
        onCopy={copySummary}
        nav={nav}
      />

      {sizeError && (
        <p role="alert" className="mt-5 rounded-md border border-danger/40 bg-surface px-4 py-3 text-danger">
          {sizeError}
        </p>
      )}
      {result.note && <p className="mt-5 rounded-md border border-line bg-surface px-4 py-3 text-ink">{result.note}</p>}

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="min-w-0">
          <SlideStage
            zoom={zoom}
            onZoom={setZoom}
            drawing={drawing}
            onDraw={drawButton}
            showHeatmap={showHeatmap}
            onHeatmap={() => setShowHeatmap((v) => !v)}
            heatmapOpacity={heatmapOpacity}
            onHeatmapOpacity={setHeatmapOpacity}
            viewer={{
              result,
              selected: selected === 'free' ? -1 : selected,
              onSelect: setSelected,
              showHeatmap,
              free,
              freeSelected: selected === 'free',
              freeLabel: `Your box${measured ? `: ${pct(measured.composition.tumor)} tumor` : ''}`,
              freeRef,
              drawing,
              onDrawn: (rect) => {
                if (!rect) return free && drewNew.current && removeFree()
                setDrawing(false)
                changeFree(rect, 'now')
              },
              onSketch: (rect) => {
                drewNew.current = true
                changeFree(rect, 'drag')
              },
              onFreeSelect: () => setSelected('free'),
              onFreeChange: changeFree,
            }}
          />
          <p className="mt-2 text-sm text-ink-muted">
            {drawing
              ? 'Drag across the slide to draw your box. Escape cancels.'
              : 'Pick a box to see why it was chosen; drag its corners or edges to reshape it. Press ? for shortcuts.'}
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <h2 className="text-base font-semibold">
              Regions <span className="num ml-1 text-sm font-normal text-ink-muted">{n}</span>
            </h2>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <ThresholdField value={threshold} onChange={setThreshold} />
              <BoxSize sizes={initial.box_sizes_um} value={result.box_um} loading={loading} onChange={changeBox} />
            </div>
          </div>
          <div className="mt-3">
            <RegionTable rows={rows} selected={selected} threshold={threshold} onSelect={setSelected} />
          </div>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-4">
          {selected === 'free' && free ? (
            <FreeBoxPanel measured={measured} measuring={measuring} error={measureError} result={result} threshold={threshold} onRemove={removeFree} />
          ) : (
            region && (
              <RegionPanel
                region={region}
                result={result}
                threshold={threshold}
                onAdjust={() => placeFree({ x: region.x, y: region.y, w: region.w, h: region.h })}
              />
            )
          )}
          <CaseNotes entry={entry} onChange={updateCase} />
        </aside>
      </div>

      <footer className="mt-10 border-t border-line pt-5">
        <ResearchNotice />
      </footer>
    </main>
  )
}
