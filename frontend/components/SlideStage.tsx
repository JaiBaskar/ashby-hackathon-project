'use client'

import { useEffect, useLayoutEffect, useRef } from 'react'
import { pct } from '@/lib/format'
import SlideViewer from './SlideViewer'
import { button } from './ui'

export const ZOOMS = [1, 1.5, 2, 3, 4, 6, 8]
export const zoomIn = (z: number) => ZOOMS.find((v) => v > z) ?? z
export const zoomOut = (z: number) => [...ZOOMS].reverse().find((v) => v < z) ?? z

type ViewerProps = React.ComponentProps<typeof SlideViewer>

// The overlay's color scale runs over this slide's own tumor-probability range (backend heatmap_range), so the
// legend gives the numbers. Cases saved before ranges existed have none and get the plain description.
function HeatmapLegend({ range }: { range?: { low: number; high: number } | null }) {
  if (!range) return <span data-testid="heatmap-legend" className="flex items-center gap-2">Heatmap: brighter amber = more tumor</span>
  return (
    <span data-testid="heatmap-legend" className="flex items-center gap-2">
      Tumor probability <span className="num">{pct(range.low)}</span>
      {/* Same amber and top opacity as the backend overlay (HEATMAP_RGB, HEATMAP_MAX_ALPHA in regions.py). */}
      <span
        className="inline-block h-2 w-16 rounded-full border border-stage-line"
        style={{ background: 'linear-gradient(to right, rgba(255, 196, 0, 0), rgba(255, 196, 0, 0.65))' }}
      />
      <span className="num">{pct(range.high)}</span> · scaled to this slide
    </span>
  )
}

// The dark "scope" the slide sits on: a toolbar, then a scrollable viewport. Zooming makes the slide
// wider than the viewport and you scroll (or trackpad-pan) around it; boxes and drawing keep working
// because they measure the image as it's drawn.
export default function SlideStage({
  viewer,
  zoom,
  onZoom,
  drawing,
  onDraw,
  showHeatmap,
  onHeatmap,
  heatmapOpacity,
  onHeatmapOpacity,
}: {
  viewer: ViewerProps
  zoom: number
  onZoom: (z: number) => void
  drawing: boolean
  onDraw: (e: React.MouseEvent) => void
  showHeatmap: boolean
  onHeatmap: () => void
  heatmapOpacity: number
  onHeatmapOpacity: (v: number) => void
}) {
  const viewport = useRef<HTMLDivElement>(null)
  const anchor = useRef<{ fx: number; fy: number; mx: number; my: number } | null>(null)
  const latestZoom = useRef(zoom)
  useEffect(() => void (latestZoom.current = zoom))

  // Keep the point under the pointer (or the middle of the view) in place while zooming.
  function zoomAround(next: number, mx?: number, my?: number) {
    const v = viewport.current
    if (v && next !== latestZoom.current) {
      const x = mx ?? v.clientWidth / 2
      const y = my ?? v.clientHeight / 2
      anchor.current = { fx: (v.scrollLeft + x) / (v.scrollWidth || 1), fy: (v.scrollTop + y) / (v.scrollHeight || 1), mx: x, my: y }
    }
    onZoom(next)
  }
  useLayoutEffect(() => {
    const v = viewport.current
    const a = anchor.current
    if (!v || !a) return
    v.scrollLeft = a.fx * v.scrollWidth - a.mx
    v.scrollTop = a.fy * v.scrollHeight - a.my
    anchor.current = null
  }, [zoom])

  // Ctrl/⌘ + scroll (and trackpad pinch, which arrives as ctrl + wheel) zooms. React's wheel listener is
  // passive, so this one is attached by hand to be able to stop the page from zooming instead.
  useEffect(() => {
    const v = viewport.current
    if (!v) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const box = v.getBoundingClientRect()
      const z = latestZoom.current
      zoomAround(e.deltaY < 0 ? zoomIn(z) : zoomOut(z), e.clientX - box.left, e.clientY - box.top)
    }
    v.addEventListener('wheel', onWheel, { passive: false })
    return () => v.removeEventListener('wheel', onWheel)
    // zoomAround only reads refs and calls onZoom, which is stable enough for a listener re-bound per render
  })

  return (
    <section aria-label="Slide" className="on-stage overflow-hidden rounded-lg bg-stage text-stage-ink">
      <div role="toolbar" aria-label="Slide tools" className="flex flex-wrap items-center gap-1 border-b border-stage-line px-2 py-1.5">
        <button type="button" aria-pressed={drawing} onClick={onDraw} className={`${button.stage} ${drawing ? 'bg-stage-line' : ''}`}>
          <svg aria-hidden viewBox="0 0 16 16" className="size-4 fill-none stroke-current" strokeWidth="1.5" strokeDasharray="2.5 1.5">
            <rect x="2.5" y="3.5" width="11" height="9" rx="1" />
          </svg>
          Draw a box
        </button>
        <span aria-hidden className="mx-1 h-5 w-px bg-stage-line" />
        <button type="button" role="switch" aria-checked={showHeatmap} onClick={onHeatmap} className={button.stage}>
          <span aria-hidden className={`relative h-4 w-7 rounded-full transition-colors duration-fast ${showHeatmap ? 'bg-box-best' : 'bg-stage-line'}`}>
            <span className={`absolute top-0.5 left-0.5 size-3 rounded-full bg-stage-ink transition-transform duration-fast ease-standard ${showHeatmap ? 'translate-x-3' : ''}`} />
          </span>
          Tumor heatmap
        </button>
        {showHeatmap && (
          <label className="flex items-center gap-2 px-2 text-xs text-stage-muted">
            <span className="sr-only">Heatmap opacity</span>
            <input
              type="range"
              min={10}
              max={100}
              step={5}
              value={heatmapOpacity}
              aria-label="Heatmap opacity"
              onChange={(e) => onHeatmapOpacity(Number(e.target.value))}
              className="w-24 accent-box-best"
            />
            <span className="num w-9">{heatmapOpacity}%</span>
          </label>
        )}
        <div className="ml-auto flex items-center gap-0.5">
          <button type="button" aria-label="Zoom out" disabled={zoom <= ZOOMS[0]} onClick={() => zoomAround(zoomOut(zoom))} className={`${button.stage} w-9 px-0 text-lg`}>
            −
          </button>
          <span data-testid="zoom-level" className="num w-12 text-center text-xs text-stage-muted">
            {Math.round(zoom * 100)}%
          </span>
          <button type="button" aria-label="Zoom in" disabled={zoom >= ZOOMS.at(-1)!} onClick={() => zoomAround(zoomIn(zoom))} className={`${button.stage} w-9 px-0 text-lg`}>
            +
          </button>
          <button type="button" onClick={() => zoomAround(1)} disabled={zoom === 1} className={`${button.stage} text-xs`}>
            Fit
          </button>
        </div>
      </div>
      <div ref={viewport} data-testid="stage-viewport" className="relative max-h-[78vh] overflow-auto overscroll-contain p-3 sm:p-4">
        <div data-testid="stage-canvas" style={{ width: `${zoom * 100}%` }} className="relative">
          <SlideViewer {...viewer} heatmapOpacity={heatmapOpacity / 100} />
        </div>
      </div>
      <div aria-hidden className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-stage-line px-3 py-2 text-xs text-stage-muted">
        <span className="flex items-center gap-2">
          <span className="region-box-best inline-block size-3.5 rounded-[2px]" /> Best region
        </span>
        <span className="flex items-center gap-2">
          <span className="region-box inline-block size-3.5 rounded-[2px]" /> Other suggestions
        </span>
        <span className="flex items-center gap-2">
          <span className="free-box inline-block size-3.5 rounded-[2px]" /> Your box
        </span>
        {showHeatmap && <HeatmapLegend range={viewer.result.heatmap_range} />}
      </div>
    </section>
  )
}
