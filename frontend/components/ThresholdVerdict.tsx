import { meets } from '@/lib/casebook'

// Whether a box holds enough tumor for the lab's sequencing minimum, in words and color.
export default function ThresholdVerdict({ tumor, threshold }: { tumor: number; threshold: number }) {
  const ok = meets(tumor, threshold)
  return (
    <p
      data-testid="threshold-verdict"
      className={`mt-4 flex items-center gap-2 rounded-sm border px-3 py-2 text-sm font-semibold ${
        ok ? 'border-ok/40 bg-ok/10 text-ok' : 'border-warn/40 bg-warn/10 text-warn'
      }`}
    >
      <span aria-hidden className="font-mono">{ok ? '✓' : '!'}</span>
      {ok ? `Meets the ${threshold}% minimum for sequencing` : `Below the ${threshold}% minimum for sequencing`}
    </p>
  )
}
