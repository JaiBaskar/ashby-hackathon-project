'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { errorMessage, type MeasuredBox, type Result } from '@/lib/api'
import { meets, useCase, useThreshold } from '@/lib/casebook'
import { formatCreated, organLabel, pct } from '@/lib/format'
import { button, ResearchNotice } from './ui'

const percent = (v: number, of: number) => `${(v / of) * 100}%`

// One page for the histotech: where to cut, with the numbers behind it and lines to sign.
// Case label, notes and the pathologist's box come from this browser (lib/casebook.ts).
export default function SamplingSheet({
  id,
  result,
  createdAt,
  timeZone,
}: {
  id: string
  result: Result
  createdAt?: string | null
  timeZone?: string
}) {
  const [entry] = useCase(id)
  const [threshold] = useThreshold()
  const [yours, setYours] = useState<MeasuredBox | null>(null)
  const [error, setError] = useState<string | null>(null)
  const box = entry.box
  const { width, height } = result.image

  useEffect(() => {
    if (!box) return setYours(null)
    let active = true
    const q = new URLSearchParams({ x: String(box.x), y: String(box.y), w: String(box.w), h: String(box.h) })
    fetch(`${result.measure_url}?${q}`, { cache: 'no-store' })
      .then(async (r) => (r.ok ? r.json() : Promise.reject(new Error(await errorMessage(r)))))
      .then((m: MeasuredBox) => active && setYours(m))
      .catch((e: Error) => active && setError(e.message))
    return () => {
      active = false
    }
  }, [box, result.measure_url])

  const best = result.regions[0]
  // 1 mm in display pixels, from any region's known size.
  const sized = result.regions.find((r) => r.size_um)
  const mmPx = sized ? (sized.w / sized.size_um!) * 1000 : null
  const verdict = (tumor: number) => (meets(tumor, threshold) ? `≥ ${threshold}%` : `< ${threshold}%`)

  return (
    <main className="mx-auto max-w-4xl animate-enter px-4 py-8 sm:px-6 print:max-w-none print:p-0">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href={`/jobs/${id}`} className="text-sm font-medium text-accent-strong hover:underline">
          ← Back to the case
        </Link>
        <button type="button" onClick={() => window.print()} className={button.primary}>
          Print or save as PDF
        </button>
      </div>

      <article className="rounded-lg border border-line bg-surface p-6 sm:p-8 print:border-0 print:p-0">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-ink pb-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Sampling sheet</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {result.organ ? `${organLabel(result.organ)} · ` : ''}
              {createdAt && (
                <time dateTime={createdAt} className="num" suppressHydrationWarning>
                  analyzed {formatCreated(createdAt, timeZone)}
                </time>
              )}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-ink-muted">Case</p>
            <p data-testid="sheet-label" className="font-mono text-lg font-semibold">
              {entry.label || <span className="text-ink-muted">{id.slice(0, 8)}</span>}
            </p>
          </div>
        </header>

        <p
          data-testid="sheet-instruction"
          className="mt-5 rounded-sm border-l-4 border-box-best bg-surface-sunken px-4 py-3 text-base"
        >
          {box ? (
            yours ? (
              <>
                <strong>Macrodissect the pathologist&apos;s box</strong> (dashed):{' '}
                <span className="num">{pct(yours.composition.tumor)}</span> tumor,{' '}
                <span className="num">
                  {Math.round(yours.width_um)} × {Math.round(yours.height_um)} µm
                </span>
                , {verdict(yours.composition.tumor)} minimum.
              </>
            ) : (
              <span className="text-ink-muted">{error ?? 'Measuring the pathologist’s box…'}</span>
            )
          ) : best ? (
            <>
              <strong>Macrodissect region {best.rank}</strong>: <span className="num">{pct(best.composition.tumor)}</span> tumor,{' '}
              <span className="num">{best.size_um == null ? '' : `${Math.round(best.size_um)} µm square`}</span>,{' '}
              {verdict(best.composition.tumor)} minimum.
            </>
          ) : (
            'No region fits on this slide; choose the area by eye.'
          )}
        </p>

        <figure className="mt-5">
          <div className="relative mx-auto w-full overflow-hidden rounded-sm bg-stage print:bg-transparent">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={result.image.url} alt="The slide with the regions to sample" width={width} height={height} className="block h-auto w-full" />
            {result.regions.map((r) => (
              <span
                key={r.rank}
                className={`absolute ${r.is_best ? 'region-box-best' : 'region-box'}`}
                style={{ left: percent(r.x, width), top: percent(r.y, height), width: percent(r.w, width), height: percent(r.h, height) }}
              >
                <span className="absolute -top-0.5 -left-0.5 flex size-5 items-center justify-center bg-box-outline font-mono text-[10px] font-semibold text-box-other">
                  {r.rank}
                </span>
              </span>
            ))}
            {box && (
              <span
                data-testid="sheet-yours"
                className="free-box absolute"
                style={{ left: percent(box.x, width), top: percent(box.y, height), width: percent(box.w, width), height: percent(box.h, height) }}
              />
            )}
            {mmPx && (
              <div className="absolute right-3 bottom-3 text-right">
                <div data-testid="scale-bar" style={{ width: percent(mmPx, width) }} className="ml-auto text-center">
                  <span className="mb-1 inline-block rounded-[2px] bg-box-outline px-1 font-mono text-[10px] font-semibold text-box-other">1 mm</span>
                  <span aria-hidden className="block h-1.5 border-x-2 border-b-2 border-box-outline" />
                </div>
              </div>
            )}
          </div>
          <figcaption className="mt-2 text-xs text-ink-muted">
            Solid boxes: suggested regions, numbered by rank (thick teal = best). Dashed: the pathologist&apos;s own box.
            {result.image.mpp_estimated && ' Sizes use an estimated image scale.'}
          </figcaption>
        </figure>

        <div className="mt-6 overflow-x-auto print:overflow-visible">
        <table aria-label="Regions" className="w-full min-w-[30rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-ink text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-1.5 pr-3 font-medium">Region</th>
              <th className="py-1.5 pr-3 text-right font-medium">Tumor</th>
              <th className="py-1.5 pr-3 text-right font-medium">Necrosis</th>
              <th className="py-1.5 pr-3 text-right font-medium">Size µm</th>
              <th className="py-1.5 pr-3 text-right font-medium">Tissue</th>
              <th className="py-1.5 text-right font-medium">Sequencing</th>
            </tr>
          </thead>
          <tbody>
            {result.regions.map((r) => (
              <tr key={r.rank} className="border-b border-line">
                <td className="num py-1.5 pr-3 font-semibold">
                  {r.rank}
                  {r.is_best ? ' (best)' : ''}
                </td>
                <td className="num py-1.5 pr-3 text-right">{pct(r.composition.tumor)}</td>
                <td className="num py-1.5 pr-3 text-right">{pct(r.composition.necrosis)}</td>
                <td className="num py-1.5 pr-3 text-right">{r.size_um == null ? '—' : Math.round(r.size_um)}</td>
                <td className="num py-1.5 pr-3 text-right">{pct(r.tissue_coverage)}</td>
                <td className="num py-1.5 text-right">{verdict(r.composition.tumor)}</td>
              </tr>
            ))}
            {yours && (
              <tr className="border-b border-line">
                <td className="py-1.5 pr-3 font-semibold">Pathologist&apos;s box</td>
                <td className="num py-1.5 pr-3 text-right">{pct(yours.composition.tumor)}</td>
                <td className="num py-1.5 pr-3 text-right">{pct(yours.composition.necrosis)}</td>
                <td className="num py-1.5 pr-3 text-right">
                  {Math.round(yours.width_um)}×{Math.round(yours.height_um)}
                </td>
                <td className="num py-1.5 pr-3 text-right">{pct(yours.tissue_coverage)}</td>
                <td className="num py-1.5 text-right">{verdict(yours.composition.tumor)}</td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Minimum tumor fraction for sequencing: <span className="num">{threshold}%</span>. Fractions are estimated from tile
          classification, not cell counts.
        </p>

        {entry.notes && (
          <section className="mt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Notes</h2>
            <p className="mt-1 whitespace-pre-wrap">{entry.notes}</p>
          </section>
        )}

        <dl className="mt-10 grid grid-cols-2 gap-x-8 gap-y-8 text-sm">
          {['Marked by', 'Date', 'Cut by', 'Date'].map((what, i) => (
            <div key={i} className="border-b border-ink pb-1">
              <dt className="text-ink-muted">{what}</dt>
              <dd className="h-6" />
            </div>
          ))}
        </dl>

        <footer className="mt-8 border-t border-line pt-3">
          <ResearchNotice />
        </footer>
      </article>
    </main>
  )
}
