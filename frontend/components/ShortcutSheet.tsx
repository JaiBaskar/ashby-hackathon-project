'use client'

import { useEffect, useRef, useState } from 'react'

export const SHORTCUTS: [string[], string][] = [
  [['1', '–', '9'], 'Select a region'],
  [['H'], 'Toggle the tumor heatmap'],
  [['N'], 'Toggle the necrosis heatmap'],
  [['D'], 'Draw your own box'],
  [['←', '→', '↑', '↓'], 'Move your box (Shift: resize it)'],
  [['Del'], 'Remove your box'],
  [['+', '−', '0'], 'Zoom in, out, fit'],
  [['J'], 'Next case'],
  [['K'], 'Previous case'],
  [['P'], 'Open the sampling sheet'],
  [['Esc'], 'Stop drawing, close this sheet'],
  [['?'], 'Show these shortcuts'],
]

// The ? sheet. Lives in the header, so it works on every page.
export default function ShortcutSheet() {
  const dialog = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (e.key !== '?' || e.ctrlKey || e.metaKey || (t && (t.closest('input, textarea, select') || t.isContentEditable))) return
      e.preventDefault()
      setOpen(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // While open: Escape closes it from anywhere, and focus starts on its Close button.
  useEffect(() => {
    if (!open) return
    dialog.current?.querySelector('button')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
        className="inline-flex size-9 items-center justify-center rounded-sm border border-stage-line font-mono text-sm text-stage-muted transition-colors duration-fast hover:text-stage-ink"
      >
        ?
      </button>
      {open && (
        <div aria-hidden className="fixed inset-0 z-40 bg-stage/60" onClick={() => setOpen(false)} />
      )}
      {open && (
        <dialog
          ref={dialog}
          open
          aria-modal="true"
          aria-label="Keyboard shortcuts"
          className="fixed inset-0 z-50 m-auto h-fit w-[min(28rem,calc(100vw-2rem))] animate-enter rounded-lg border border-line bg-surface p-0 text-ink shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-line px-5 py-3">
            <h2 className="font-semibold">Keyboard shortcuts</h2>
            <button type="button" onClick={() => setOpen(false)} className="rounded-sm px-2 text-sm text-ink-muted hover:text-ink">
              Close
            </button>
          </div>
          <dl className="grid grid-cols-[auto_1fr] items-center gap-x-5 gap-y-2.5 px-5 py-4 text-sm">
            {SHORTCUTS.map(([keys, what]) => (
              <div key={what} className="contents">
                <dt className="flex gap-1">
                  {keys.map((k) =>
                    k === '–' ? (
                      <span key={k} className="text-ink-muted">–</span>
                    ) : (
                      <kbd key={k} className="min-w-6 rounded-sm border border-line-strong bg-surface-sunken px-1.5 py-0.5 text-center font-mono text-xs">
                        {k}
                      </kbd>
                    ),
                  )}
                </dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </dialog>
      )}
    </>
  )
}
