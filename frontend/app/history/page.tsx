import Link from 'next/link'
import RequestCard from '@/components/RequestCard'
import { button, ResearchNotice } from '@/components/ui'
import type { JobList } from '@/lib/api'

export const metadata = { title: 'History · Sampling-site finder' }
export const dynamic = 'force-dynamic'

// Server side, like the job page: read the request history from FastAPI directly.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

export default async function HistoryPage() {
  const res = await fetch(`${apiUrl}/api/jobs`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`The analysis service answered ${res.status}.`)
  const { store, jobs }: JobList = await res.json()

  return (
    <main className="mx-auto max-w-6xl animate-enter px-4 py-8 sm:px-6 sm:py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-normal">History</h1>
          <p className="mt-1 text-ink-muted">Every analysis you've run, newest first.</p>
        </div>
        <Link href="/upload" className={button.secondary}>
          New analysis
        </Link>
      </div>

      {store === 'memory' && (
        <p className="mt-6 rounded-md border border-line bg-surface px-4 py-3 text-ink">
          History isn't saved: no database is configured, so this list empties when the server restarts.
        </p>
      )}

      {jobs.length === 0 ? (
        <div className="mt-10 rounded-md border border-line bg-surface px-6 py-10 text-center">
          <p className="text-lg">No analyses yet.</p>
          <Link href="/upload" className={`${button.primary} mt-5`}>
            Analyze a slide
          </Link>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <li key={job.id}>
              <RequestCard job={job} />
            </li>
          ))}
        </ul>
      )}

      <footer className="mt-10 border-t border-line pt-5">
        <ResearchNotice />
      </footer>
    </main>
  )
}
