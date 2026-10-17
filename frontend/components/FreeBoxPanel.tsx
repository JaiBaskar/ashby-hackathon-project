import type { MeasuredBox, Result } from '@/lib/api'
import { pct } from '@/lib/format'
import { CompositionSection, Reasons } from './RegionPanel'
import { button } from './ui'

// Details for the user's own box: the same numbers as a suggested region, measured from the tile scores.
export default function FreeBoxPanel({
  measured,
  measuring,
  error,
  result,
  onRemove,
}: {
  measured: MeasuredBox | null
  measuring: boolean
  error: string | null
  result: Result
  onRemove: () => void
}) {
  const estimated = result.image.mpp_estimated
  return (
    <section
      aria-label="Region details"
      aria-busy={measuring}
      className="animate-enter rounded-lg border border-line bg-surface p-5 shadow-overlay sm:p-6"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-display text-xl font-normal">Your box</h2>
        {measured && !error && (
          <p className="text-right text-sm text-ink-muted">
            Score <span className="font-display text-lg text-ink tabular-nums">{measured.score.toFixed(2)}</span>
          </p>
        )}
      </div>
      <p className="mt-1 text-sm text-ink-muted">Drag it to move, drag a handle to resize. Arrow keys move it; Shift + arrow keys resize it.</p>

      {error ? (
        <p role="alert" className="mt-6 text-danger">
          {error}
        </p>
      ) : measured ? (
        <>
          <CompositionSection composition={measured.composition} />
          {measured.reasons.length > 0 && <Reasons reasons={measured.reasons} title="About this box" />}
          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-5 text-sm">
            <div className="col-span-2">
              <dt className="text-ink-muted">Tumor content</dt>
              <dd data-testid="tumor-vs-slide" className="mt-0.5 font-semibold tabular-nums">
                {pct(measured.composition.tumor)} here vs. {pct(result.slide_composition.tumor)} across the slide
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Size</dt>
              <dd data-testid="size" className="mt-0.5 font-semibold tabular-nums">
                {Math.round(measured.width_um)} × {Math.round(measured.height_um)} µm
                {estimated && <span className="block font-normal text-ink-muted">estimated scale</span>}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Tissue coverage</dt>
              <dd data-testid="coverage" className="mt-0.5 font-semibold tabular-nums">
                {pct(measured.tissue_coverage)}
              </dd>
            </div>
          </dl>
        </>
      ) : (
        <p className="mt-6 text-ink-muted">Measuring…</p>
      )}

      <button type="button" onClick={onRemove} className={`${button.secondary} mt-5 w-full`}>
        Remove your box
      </button>
    </section>
  )
}
