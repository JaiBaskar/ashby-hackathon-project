import Worklist from '@/components/Worklist'
import { ResearchNotice } from '@/components/ui'
import type { JobList } from '@/lib/api'

export const metadata = { title: 'Worklist · Hotspot' }
export const dynamic = 'force-dynamic'

// Server side, like the job page: read the case list from FastAPI directly.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

export default async function WorklistPage() {
  const res = await fetch(`${apiUrl}/api/jobs`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`The analysis service answered ${res.status}.`)
  const list: JobList = await res.json()
  return (
    <main className="mx-auto max-w-[90rem] animate-enter px-4 py-8 sm:px-6">
      <Worklist initial={list} />
      <footer className="mt-12 border-t border-line pt-5">
        <ResearchNotice />
      </footer>
    </main>
  )
}
