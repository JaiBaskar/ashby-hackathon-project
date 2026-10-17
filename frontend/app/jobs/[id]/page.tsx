import { notFound } from 'next/navigation'
import JobView from '@/components/JobView'
import type { JobStatus } from '@/lib/api'

export const metadata = { title: 'Analysis · Sampling-site finder' }

// Server side, so a results URL survives a reload: fetch the job's current state from FastAPI directly.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const res = await fetch(`${apiUrl}/api/jobs/${encodeURIComponent(id)}`, { cache: 'no-store' })
  if (res.status === 404) notFound()
  if (!res.ok) throw new Error(`The analysis service answered ${res.status}.`)
  const initial: JobStatus = await res.json()
  return <JobView id={id} initial={initial} />
}
