// Shared bits of chrome. Styles use design tokens only (DESIGN.md).

const base =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-[background-color,border-color,color,transform] duration-fast ease-standard active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50'

export const button = {
  primary: `${base} bg-accent text-accent-ink shadow-raised hover:bg-accent-strong`,
  secondary: `${base} border border-line-strong bg-surface text-ink hover:border-ink-muted hover:bg-surface-sunken`,
  quiet: `${base} text-ink-muted hover:bg-surface-sunken hover:text-ink`,
  // On the dark stage and its toolbar.
  stage: `${base} min-h-9 px-3 text-stage-ink hover:bg-stage-line aria-pressed:bg-stage-line aria-pressed:text-stage-ink`,
}

// A small frosted chip, like the label end of a glass slide. Mono, because it carries codes and states.
export function Chip({ children, tone = 'plain', title }: { children: React.ReactNode; tone?: 'plain' | 'ok' | 'warn' | 'eosin'; title?: string }) {
  const tones = {
    plain: 'border-line-strong text-ink-muted',
    ok: 'border-ok/40 bg-ok/10 text-ok',
    warn: 'border-warn/40 bg-warn/10 text-warn',
    eosin: 'border-eosin/40 bg-eosin/10 text-eosin-strong',
  }
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-xs font-medium uppercase tracking-wide whitespace-nowrap ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function DemoBadge({ model }: { model: string }) {
  if (model !== 'fake') return null
  return (
    <Chip title="Scores come from a color-based stand-in, not CONCH. Use them to try the app, not to choose a site.">
      Demo model
    </Chip>
  )
}

export function ResearchNotice() {
  return (
    <p className="text-sm text-ink-muted">
      Research prototype, not for clinical use. Every number here is an estimate from a tile classifier, and a
      pathologist makes the call.
    </p>
  )
}
