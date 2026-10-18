'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { pct } from '@/lib/format'
import SlideViewer from './SlideViewer'
import { button } from './ui'

export const ZOOMS = [1, 1.5, 2, 3, 4, 6, 8]
export const zoomIn = (z: number) => ZOOMS.find((v) => v > z) ?? z
export const zoomOut = (z: number) => [...ZOOMS].reverse().find((v) => v < z) ?? z

type ViewerProps = React.ComponentProps<typeof SlideViewer>

// The overlays' colors per band (lightest to darkest), top opacity and band count: the same as the backend's
// (HEATMAP_RAMP, HEATMAP_MAX_ALPHA, HEATMAP_BANDS in regions.py), so each shade on the key is exactly a shade on
// the slide. Tumor's scale is stretched over each slide's own range; necrosis uses one fixed scale (NECROSIS_RANGE).
export const HEATMAP_KEYS = {
  tumor: { label: 'Tumor', ramp: ['251 146 60', '234 108 18', '194 75 10', '140 50 8'], scale: 'scaled to this slide' },
  necrosis: { label: 'Necrosis', ramp: ['96 165 250', '37 99 235', '29 63 190', '23 37 120'], scale: 'same scale on every slide' },
} as const
const HEATMAP_MAX_ALPHA = 0.65
const HEATMAP_BANDS = 4

// One overlay's key: its color scale (backend heatmap_range / necrosis_heatmap_range) split into bands that darken
// as the probability rises, each shown over a slide-glass background with its probability limits underneath. Below
// the low end the slide is left clear; the top band also covers everything above the high end. Cases saved before
// ranges existed have none and get a plain description.
function HeatmapKey({ kind, range, opacity }: { kind: keyof typeof HEATMAP_KEYS; range?: { low: number; high: number } | null; opacity: number }) {
  const { label, ramp, scale } = HEATMAP_KEYS[kind]
  const name = label.toLowerCase()
  if (!range) {
    return (
      <p data-testid={`${kind}-key`} className="text-xs text-stage-muted">
        {label} heatmap: darker color = more {name}
      </p>
    )
  }
  const stops = Array.from({ length: HEATMAP_BANDS + 1 }, (_, i) => range.low + ((range.high - range.low) * i) / HEATMAP_BANDS)
  return (
    <figure data-testid={`${kind}-key`} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stage-muted">
      <figcaption className="w-24 font-semibold text-stage-ink">{label} probability</figcaption>
      <div
        role="img"
        aria-label={`${label} key: clear below ${pct(range.low)}, then ${HEATMAP_BANDS} shades, each darker, up to ${pct(range.high)} and above`}
        className="w-[min(18rem,100%)]"
      >
        <div className="flex gap-px overflow-hidden rounded-sm border border-stage-line bg-slide-glass">
          {stops.slice(1).map((_, i) => (
            <span
              key={i}
              data-testid={`${kind}-band`}
              className="h-3 flex-1"
              style={{ background: `rgb(${ramp[i]} / ${(HEATMAP_MAX_ALPHA * opacity * (i + 1)) / HEATMAP_BANDS})` }}
            />
          ))}
        </div>
        <div aria-hidden className="relative mt-0.5 h-4">
          {stops.map((v, i) => (
            <span
              key={i}
              className="num absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full"
              style={{ left: `${(i / HEATMAP_BANDS) * 100}%` }}
            >
              {pct(v)}
              {i === HEATMAP_BANDS && '+'}
            </span>
          ))}
        </div>
      </div>
      <span>
        darker = more {name}; {scale}; clear below {pct(range.low)}
      </span>
    </figure>
  )
}

// A toolbar switch for one overlay; its track takes the overlay's tint when on.
function HeatmapSwitch({ kind, on, onToggle }: { kind: keyof typeof HEATMAP_KEYS; on: boolean; onToggle: () => void }) {
  const { label, ramp } = HEATMAP_KEYS[kind]
  return (
    <button type="button" role="switch" aria-checked={on} onClick={onToggle} className={button.stage}>
      <span
        aria-hidden
        className={`relative h-4 w-7 rounded-full transition-colors duration-fast ${on ? '' : 'bg-stage-line'}`}
        style={on ? { background: `rgb(${ramp[1]})` } : undefined}
      >
        <span className={`absolute top-0.5 left-0.5 size-3 rounded-full bg-stage-ink transition-transform duration-fast ease-standard ${on ? 'translate-x-3' : ''}`} />
      </span>
      {label} heatmap
    </button>
  )
}

const VIEWPORT_VH = 0.78 // the viewport's max-h-[78vh] below, as a fraction of the window

// The slide width (px) at which the whole slide fits in the viewport: its full width, or less for a slide
// tall enough that its full width would overflow the viewport's max height. Null until measured.
function useFitWidth(viewport: React.RefObject<HTMLDivElement | null>, aspect: number) {
  const [fit, setFit] = useState<number | null>(null)
  useLayoutEffect(() => {
    const v = viewport.current
    if (!v) return
    const measure = () => {
      const pad = getComputedStyle(v)
      const w = v.clientWidth - parseFloat(pad.paddingLeft) - parseFloat(pad.paddingRight)
      const h = window.innerHeight * VIEWPORT_VH - parseFloat(pad.paddingTop) - parseFloat(pad.paddingBottom)
      setFit(w > 0 && h > 0 ? Math.floor(Math.min(w, h * aspect)) : null)
    }
    measure()
    window.addEventListener('resize', measure)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(v)
    return () => {
      window.removeEventListener('resize', measure)
      observer?.disconnect()
    }
  }, [viewport, aspect])
  return fit
}

// The dark "scope" the slide sits on: a toolbar, then a scrollable viewport. At 100% (Fit) the whole slide
// fits in the viewport; zooming makes it bigger and you scroll (or trackpad-pan) around it. Boxes and
// drawing keep working because they measure the image as it's drawn.
export default function SlideStage({
  viewer,
  zoom,
  onZoom,
  drawing,
  onDraw,
  showHeatmap,
  onHeatmap,
  showNecrosis,
  onNecrosis,
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
  showNecrosis: boolean
  onNecrosis: () => void
  heatmapOpacity: number
  onHeatmapOpacity: (v: number) => void
}) {
  const viewport = useRef<HTMLDivElement>(null)
  const anchor = useRef<{ fx: number; fy: number; mx: number; my: number } | null>(null)
  const latestZoom = useRef(zoom)
  const { image } = viewer.result
  const fit = useFitWidth(viewport, image.width / image.height)
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
        <HeatmapSwitch kind="tumor" on={showHeatmap} onToggle={onHeatmap} />
        {viewer.result.necrosis_heatmap_url && <HeatmapSwitch kind="necrosis" on={showNecrosis} onToggle={onNecrosis} />}
        {(showHeatmap || showNecrosis) && (
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
              className="w-24 accent-stage-ink"
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
        <div data-testid="stage-canvas" style={{ width: fit ? `${Math.round(zoom * fit)}px` : `${zoom * 100}%` }} className="relative mx-auto">
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
      </div>
      {(showHeatmap || showNecrosis) && (
        <div className="space-y-2 border-t border-stage-line px-3 py-2.5">
          {showHeatmap && <HeatmapKey kind="tumor" range={viewer.result.heatmap_range} opacity={heatmapOpacity / 100} />}
          {showNecrosis && <HeatmapKey kind="necrosis" range={viewer.result.necrosis_heatmap_range} opacity={heatmapOpacity / 100} />}
        </div>
      )}
    </section>
  )
}
