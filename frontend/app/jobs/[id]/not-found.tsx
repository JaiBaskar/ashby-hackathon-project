import Link from 'next/link'
import { button } from '@/components/ui'

export default function JobNotFound() {
  return (
    <main className="mx-auto max-w-xl animate-enter px-4 py-16 sm:px-6">
      <h1 className="font-display text-xl font-normal">We can&apos;t find this analysis</h1>
      <p className="mt-3 text-ink-muted">
        Analyses are kept in memory only, so they disappear when the server restarts. Upload the image again to get
        new results.
      </p>
      <Link href="/upload" className={`${button.primary} mt-8`}>
        Analyze a slide
      </Link>
    </main>
  )
}
