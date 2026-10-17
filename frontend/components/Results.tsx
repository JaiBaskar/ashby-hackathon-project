'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { errorMessage, type MeasuredBox, type RegionsAtSize, type Result } from '@/lib/api'
import { boxLabel, pct } from '@/lib/format'
import type { Rect } from './FreeBox'
import FreeBoxPanel from './FreeBoxPanel'
import RegionPanel from './RegionPanel'
import RequestMeta from './RequestMeta'
import SlideViewer from './SlideViewer'
import { button, DemoBadge, ResearchNotice } from './ui'

// Box sizes the backend offers. Changing size re-ranks the job's stored tile scores (no new model run);
// each size is fetched once and kept, and the first size comes with the result.
function BoxSize({ sizes, value, loading, onChange }: { sizes: number[]; value: number; loading: boolean; onChange: (um: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Box size" aria-busy={loading} className="flex items-center gap-2.5 text-sm font-medium">
      <span aria-hidden>Box size</span>
      <div className="inline-flex rounded-md border border-line-strong bg-surface p-0.5">
        {sizes.map((um) => (
          <label
            key={um}
            className={`relative inline-flex min-h-10 cursor-pointer items-center rounded-sm px-3 tabular-nums transition-colors duration-fast has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus has-[:disabled]:cursor-wait ${
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
  result: initial,
  meta,
  timeZone,
}: {
  result: Result
  meta?: { created_at?: string | null; cancer_type?: string | null }
  timeZone?: string
}) {
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

  useEffect(() => () => clearTimeout(timer.current), [])
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
    clearTimeout(timer.current)
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

  function changeFree(rect: Rect, when: 'drag' | 'now' | 'soon') {
    setFree(rect)
    setSelected('free')
    if (when === 'now') measureNow(rect)
    if (when === 'soon') {
      clearTimeout(timer.current)
      timer.current = setTimeout(() => measureNow(rect), 300)
    }
  }

  function placeFree(rect: Rect, focus = false) {
    setDrawing(false)
    setMeasured(null)
    setMeasureError(null)
    focusFree.current = focus
    changeFree(rect, 'now')
  }

  function removeFree() {
    clearTimeout(timer.current)
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
    if (e.detail !== 0) return setDrawing(true)
    const { width, height } = result.image
    const w = result.regions[0]?.w ?? width / 4
    const h = result.regions[0]?.h ?? w
    placeFree({ x: (width - w) / 2, y: (height - h) / 2, w, h }, true)
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
          <BoxSize sizes={initial.box_sizes_um} value={result.box_um} loading={loading} onChange={changeBox} />
          <button type="button" aria-pressed={drawing} onClick={drawButton} className={`${button.secondary} ${drawing ? 'border-accent-strong bg-surface-sunken' : ''}`}>
            Draw a box
          </button>
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

      {meta?.created_at && (
        <div className="mt-4">
          <RequestMeta createdAt={meta.created_at} cancerType={meta.cancer_type} timeZone={timeZone} />
        </div>
      )}

      {sizeError && (
        <p role="alert" className="mt-6 rounded-md border border-line bg-surface px-4 py-3 text-danger">
          {sizeError}
        </p>
      )}

      {result.note && (
        <p className="mt-6 rounded-md border border-line bg-surface px-4 py-3 text-ink">
          {result.note}
        </p>
      )}

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <SlideViewer
            result={result}
            selected={selected === 'free' ? -1 : selected}
            onSelect={setSelected}
            showHeatmap={showHeatmap}
            free={free}
            freeSelected={selected === 'free'}
            freeLabel={`Your box${measured ? `: ${pct(measured.composition.tumor)} tumor` : ''}`}
            freeRef={freeRef}
            drawing={drawing}
            onDrawn={(rect) => rect && placeFree(rect)}
            onFreeSelect={() => setSelected('free')}
            onFreeChange={changeFree}
          />
          <p className="mt-2 text-sm text-ink-muted">
            {drawing
              ? 'Drag across the slide to draw your box. Press Escape to cancel.'
              : 'Select a numbered box to see why it was chosen, or draw your own.'}
          </p>
        </div>
        <div className="lg:sticky lg:top-6">
          {selected === 'free' && free ? (
            <FreeBoxPanel measured={measured} measuring={measuring} error={measureError} result={result} onRemove={removeFree} />
          ) : (
            region && (
              <RegionPanel region={region} result={result} onAdjust={() => placeFree({ x: region.x, y: region.y, w: region.w, h: region.h })} />
            )
          )}
        </div>
      </div>

      <footer className="mt-10 border-t border-line pt-5">
        <ResearchNotice />
      </footer>
    </main>
  )
}
