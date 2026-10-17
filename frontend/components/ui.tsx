// Shared bits of chrome. Styles use design tokens only (DESIGN.md).

export const button = {
  primary:
    'inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-accent px-5 text-base font-semibold text-accent-ink shadow-raised transition-[filter,transform] duration-fast ease-standard hover:brightness-105 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none',
  secondary:
    'inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-line-strong bg-surface px-4 text-base font-medium text-ink transition-colors duration-fast ease-standard hover:bg-surface-sunken',
}

export function DemoBadge({ model }: { model: string }) {
  if (model !== 'fake') return null
  return (
    <span
      title="Scores come from a color-based stand-in, not CONCH. Use them to try the app, not to choose a site."
      className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface-sunken px-2.5 py-0.5 text-xs font-semibold tracking-wide text-ink-muted"
    >
      <span aria-hidden className="size-1.5 rounded-full bg-ink-muted" />
      Demo model
    </span>
  )
}

export function ResearchNotice() {
  return (
    <p className="text-sm text-ink-muted">
      Research prototype, not for clinical use. Suggestions are estimates from a tile classifier.
    </p>
  )
}
