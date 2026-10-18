import Link from 'next/link'
import { notFound } from 'next/navigation'
import SamplingSheet from '@/components/SamplingSheet'
import { button } from '@/components/ui'
import type { JobStatus } from '@/lib/api'

export const metadata = { title: 'Sampling sheet · Hotspot' }

const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

export default async function SheetPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const res = await fetch(`${apiUrl}/api/jobs/${encodeURIComponent(id)}`, { cache: 'no-store' })
  if (res.status === 404) notFound()
  if (!res.ok) throw new Error(`The analysis service answered ${res.status}.`)
  const job: JobStatus = await res.json()
  if (job.status !== 'done' || !job.result) {
    return (
      <main className="mx-auto max-w-xl px-4 py-16 sm:px-6">
        <h1 className="text-xl font-semibold tracking-tight">This case isn&apos;t finished yet</h1>
        <p className="mt-2 text-ink-muted">The sampling sheet is ready once the analysis is done.</p>
        <Link href={`/jobs/${id}`} className={`${button.primary} mt-6`}>
          Back to the case
        </Link>
      </main>
    )
  }
  return <SamplingSheet id={id} result={job.result} createdAt={job.created_at} />
}
