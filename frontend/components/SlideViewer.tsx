'use client'

import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import type { Result } from '@/lib/api'
import { pct } from '@/lib/format'

// Box coordinates are in display-image pixels; the image is drawn at whatever width the layout gives it.
// Scale = rendered width / display width, re-measured on load, window resize and container resize.
function useScale(width: number) {
  const ref = useRef<HTMLImageElement>(null)
  const [scale, setScale] = useState(0)
  const measure = useCallback(() => {
    if (ref.current) setScale(ref.current.getBoundingClientRect().width / width)
  }, [width])

  useLayoutEffect(() => {
    measure()
    window.addEventListener('resize', measure)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    if (ref.current) observer?.observe(ref.current)
    return () => {
      window.removeEventListener('resize', measure)
      observer?.disconnect()
    }
  }, [measure])

  return { ref, scale, measure }
}

interface Props {
  result: Result
  selected: number
  onSelect: (rank: number) => void
  showHeatmap: boolean
}

export default function SlideViewer({ result, selected, onSelect, showHeatmap }: Props) {
  const { image } = result
  const { ref, scale, measure } = useScale(image.width)

  return (
    <div className="relative overflow-hidden rounded-lg bg-surface-sunken">
      {/* A per-job PNG from the API: plain <img> with its real size, so the boxes scale with it. */}
      <img
        ref={ref}
        src={image.url}
        width={image.width}
        height={image.height}
        alt="The uploaded slide, with the suggested sampling regions outlined"
        onLoad={measure}
        className="block h-auto w-full"
      />
      {showHeatmap && (
        <img
          data-testid="heatmap"
          src={result.heatmap_url}
          alt=""
          aria-hidden
          className="pointer-events-none absolute inset-0 h-full w-full animate-enter"
        />
      )}
      {result.regions.map((r) => {
        const isSelected = r.rank === selected
        return (
          <button
            key={r.rank}
            type="button"
            aria-pressed={isSelected}
            aria-label={`Region ${r.rank}${r.is_best ? ', best' : ''}: ${pct(r.composition.tumor)} tumor`}
            onClick={() => onSelect(r.rank)}
            style={{ left: `${r.x * scale}px`, top: `${r.y * scale}px`, width: `${r.w * scale}px`, height: `${r.h * scale}px` }}
            className={`group absolute cursor-pointer rounded-sm transition-[transform] duration-fast ease-standard hover:z-10 focus-visible:z-10 ${
              r.is_best ? 'region-box-best' : 'region-box'
            } ${isSelected ? 'z-10' : ''}`}
          >
            <span className="absolute -top-0.5 -left-0.5 flex -translate-x-px -translate-y-px items-center">
              <span
                data-testid="rank"
                className={`flex size-6 items-center justify-center rounded-sm text-xs font-bold tabular-nums transition-transform duration-fast ease-standard group-hover:scale-110 ${
                  isSelected ? 'bg-accent text-accent-ink' : 'bg-box-outline text-box-other'
                }`}
              >
                {r.rank}
              </span>
              {r.is_best && (
                <span className="rounded-r-sm bg-box-outline px-1.5 py-0.5 text-xs font-semibold text-box-other">Best</span>
              )}
            </span>
          </button>
        )
      })}
    </div>
  )
}
