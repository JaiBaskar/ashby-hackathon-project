import type { MeasuredBox, Result } from './api'
import { meets } from './casebook'
import { organLabel, pct } from './format'

// A plain-text summary for the pathology report or LIS. Every number is as shown on screen.
export function caseSummary(result: Result, threshold: number, label: string, yours: MeasuredBox | null): string {
  const verdict = (tumor: number) => `${meets(tumor, threshold) ? 'meets' : 'below'} ${threshold}%`
  const lines = [
    `Case ${label.trim() || '(no label)'}${result.organ ? ` · ${organLabel(result.organ)}` : ''}`,
    `Suggested sampling regions (minimum tumor ${threshold}% for sequencing):`,
    ...result.regions.map(
      (r) =>
        `Region ${r.rank}${r.is_best ? ' (best)' : ''}: tumor ${pct(r.composition.tumor)}, necrosis ${pct(r.composition.necrosis)}, ` +
        `${r.size_um == null ? 'size unknown' : `${Math.round(r.size_um)} µm`}, ${verdict(r.composition.tumor)}`,
    ),
  ]
  if (yours) {
    lines.push(
      `Pathologist's box: tumor ${pct(yours.composition.tumor)}, necrosis ${pct(yours.composition.necrosis)}, ` +
        `${Math.round(yours.width_um)} × ${Math.round(yours.height_um)} µm, ${verdict(yours.composition.tumor)}`,
    )
  }
  if (result.image.mpp_estimated) lines.push('Sizes use an estimated image scale.')
  lines.push('Estimates from a tile classifier (research prototype, not for clinical use).')
  return lines.join('\n')
}
