'use client'

import { useEffect, useState } from 'react'
import { errorMessage, type JobStatus } from '@/lib/api'
import Analyzing from './Analyzing'
import CaseNav from './CaseNav'
import Results from './Results'

const POLL_MS = 1000
const MAX_NETWORK_FAILURES = 5

// Polls the job until it's done or failed. A finished job (e.g. after a reload) renders straight away.
export default function JobView({ id, initial }: { id: string; initial: JobStatus }) {
  const [status, setStatus] = useState(initial)
  const finished = status.status === 'done' || status.status === 'error'

  useEffect(() => {
    if (finished) return
    let failures = 0
    let timer: ReturnType<typeof setTimeout>
    let active = true

    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${id}`, { cache: 'no-store' })
        if (!active) return
        if (!res.ok) {
          const error = await errorMessage(res)
          if (active) setStatus((s) => ({ ...s, status: 'error', error }))
          return
        }
        const next: JobStatus = await res.json()
        if (!active) return
        failures = 0
        setStatus(next)
        if (next.status === 'done' || next.status === 'error') return
      } catch {
        if (++failures >= MAX_NETWORK_FAILURES) {
          if (active)
            setStatus((s) => ({ ...s, status: 'error', error: "Lost contact with the server. Check that it's running." }))
          return
        }
      }
      if (active) timer = setTimeout(poll, POLL_MS)
    }

    timer = setTimeout(poll, POLL_MS)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [id, finished])

  if (status.status === 'done' && status.result) return <Results id={id} key={status.result.regions_url} result={status.result} meta={status} nav={<CaseNav id={id} />} />
  return <Analyzing id={id} status={status} />
}
