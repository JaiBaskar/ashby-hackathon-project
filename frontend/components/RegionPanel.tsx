import { CLASSES, type Composition, type Region, type Result } from '@/lib/api'
import { CLASS_LABELS, pct } from '@/lib/format'
import ScoreHelp from './ScoreHelp'
import ThresholdVerdict from './ThresholdVerdict'
import { button } from './ui'

// Token-backed swatch classes per tissue class (DESIGN.md, "Tissue classes").
const SWATCH: Record<(typeof CLASSES)[number], string> = {
  tumor: 'bg-class-tumor',
  stroma: 'bg-class-stroma',
  immune: 'bg-class-immune',
  necrosis: 'bg-class-necrosis',
  normal: 'bg-class-normal',
  fat_other: 'bg-class-fat-other',
}

export function CompositionSection({ composition }: { composition: Composition }) {
  return (
    <>
      <h3 className="mt-6 text-sm font-semibold">Cell composition</h3>
      <div aria-hidden className="mt-2 flex h-3 overflow-hidden rounded-full bg-surface-sunken">
        {CLASSES.map((c) => (
          <div key={c} className={SWATCH[c]} style={{ width: `${composition[c] * 100}%` }} />
        ))}
      </div>
      <ul aria-label="Cell composition" className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
        {CLASSES.map((c) => (
          <li key={c} className="flex items-center gap-2">
            <span aria-hidden className={`size-2.5 shrink-0 rounded-sm ${SWATCH[c]}`} />
            <span className="flex-1 text-ink-muted">{CLASS_LABELS[c]}</span>
            <span className="tabular-nums">{pct(composition[c])}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-ink-muted">Estimated from tile classification, not individual cell counts</p>
    </>
  )
}

export function Reasons({ reasons, title = 'Why this region' }: { reasons: string[]; title?: string }) {
  return (
    <>
      <h3 className="mt-6 text-sm font-semibold">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {reasons.map((reason) => (
          <li key={reason} className="relative pl-4 before:absolute before:top-2.5 before:left-0 before:size-1.5 before:rounded-full before:bg-accent-strong">
            {reason}
          </li>
        ))}
      </ul>
    </>
  )
}

export default function RegionPanel({
  region,
  result,
  threshold,
  onAdjust,
}: {
  region: Region
  result: Result
  threshold: number
  onAdjust?: () => void
}) {
  const estimated = result.image.mpp_estimated
  return (
    <section
      aria-label="Region details"
      key={region.rank}
      className="animate-enter rounded-lg border border-line bg-surface p-4 sm:p-5"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          Region {region.rank}
          {region.is_best && (
            <span className="rounded-sm bg-accent px-1.5 py-0.5 font-sans text-xs font-semibold text-accent-ink">Best</span>
          )}
        </h2>
        <p className="flex items-center gap-1.5 text-right text-sm text-ink-muted">
          Score <span className="num text-lg font-semibold text-ink">{region.score.toFixed(2)}</span>
          <ScoreHelp />
        </p>
      </div>

      <ThresholdVerdict tumor={region.composition.tumor} threshold={threshold} />
      <CompositionSection composition={region.composition} />
      <Reasons reasons={region.reasons} />

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-5 text-sm">
        <div className="col-span-2">
          <dt className="text-ink-muted">Tumor content</dt>
          <dd data-testid="tumor-vs-slide" className="num mt-0.5 font-semibold">
            {pct(region.composition.tumor)} here vs. {pct(result.slide_composition.tumor)} across the slide
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Size</dt>
          <dd data-testid="size" className="num mt-0.5 font-semibold">
            {region.size_um == null ? 'Unknown' : `${Math.round(region.size_um)} µm square`}
            {region.size_um != null && estimated && <span className="block font-normal text-ink-muted">estimated scale</span>}
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Tissue coverage</dt>
          <dd data-testid="coverage" className="num mt-0.5 font-semibold">
            {pct(region.tissue_coverage)}
          </dd>
        </div>
      </dl>
      {onAdjust && (
        <button type="button" onClick={onAdjust} className={`${button.secondary} mt-5 w-full`}>
          Adjust this box
        </button>
      )}
    </section>
  )
}
