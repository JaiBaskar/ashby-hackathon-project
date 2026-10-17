'use client'

import Link from 'next/link'
import { button } from '@/components/ui'

// Shown when a page fails to render, e.g. the analysis service is down when a job page loads.
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto max-w-xl animate-enter px-4 py-16 sm:px-6">
      <h1 className="font-display text-xl font-normal">Something went wrong</h1>
      <p role="alert" className="mt-3 text-ink-muted">
        The analysis service didn&apos;t answer. Check that it&apos;s running, then try again.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <button type="button" onClick={reset} className={button.primary}>
          Try again
        </button>
        <Link href="/" className={button.secondary}>
          Home
        </Link>
      </div>
    </main>
  )
}
