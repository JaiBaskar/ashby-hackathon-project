import type { MeasuredBox, Result } from '@/lib/api'
import { pct } from '@/lib/format'
import { CompositionSection, Reasons } from './RegionPanel'
import ThresholdVerdict from './ThresholdVerdict'
import { button } from './ui'

// Details for the user's own box: the same numbers as a suggested region, measured from the tile scores.
export default function FreeBoxPanel({
  measured,
  measuring,
  error,
  result,
  threshold,
  onRemove,
}: {
  measured: MeasuredBox | null
  measuring: boolean
  error: string | null
  result: Result
  threshold: number
  onRemove: () => void
}) {
  const estimated = result.image.mpp_estimated
  return (
    <section
      aria-label="Region details"
      aria-busy={measuring}
      className="animate-enter rounded-lg border border-line bg-surface p-4 sm:p-5"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">Your box</h2>
        {measured && !error && (
          <p className="text-right text-sm text-ink-muted">
            Score <span className="num text-lg font-semibold text-ink">{measured.score.toFixed(2)}</span>
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
          <ThresholdVerdict tumor={measured.composition.tumor} threshold={threshold} />
          <CompositionSection composition={measured.composition} />
          {measured.reasons.length > 0 && <Reasons reasons={measured.reasons} title="About this box" />}
          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-5 text-sm">
            <div className="col-span-2">
              <dt className="text-ink-muted">Tumor content</dt>
              <dd data-testid="tumor-vs-slide" className="num mt-0.5 font-semibold">
                {pct(measured.composition.tumor)} here vs. {pct(result.slide_composition.tumor)} across the slide
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Size</dt>
              <dd data-testid="size" className="num mt-0.5 font-semibold">
                {Math.round(measured.width_um)} × {Math.round(measured.height_um)} µm
                {estimated && <span className="block font-normal text-ink-muted">estimated scale</span>}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Tissue coverage</dt>
              <dd data-testid="coverage" className="num mt-0.5 font-semibold">
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
