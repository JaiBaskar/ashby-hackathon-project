// Types for the FastAPI responses (backend/project/api.py, implementation-steps.md §4).

export const CLASSES = ['tumor', 'stroma', 'immune', 'necrosis', 'normal', 'fat_other'] as const
export type TissueClass = (typeof CLASSES)[number]
export type Composition = Record<TissueClass, number>

export const STEPS = ['finding_tissue', 'tiling', 'analyzing', 'ranking'] as const
export type Step = (typeof STEPS)[number]

export interface Region {
  rank: number
  is_best: boolean
  x: number
  y: number
  w: number
  h: number
  score: number
  tissue_coverage: number
  tumor_std: number
  composition: Composition
  size_um: number | null
  reasons: string[]
}

export interface Result {
  model: string
  image: { url: string; width: number; height: number; mpp: number | null; mpp_estimated: boolean }
  heatmap_url: string
  tiles: { count: number; capped: boolean }
  slide_composition: Composition
  regions: Region[]
  note: string | null
}

export interface JobStatus {
  status: 'queued' | 'running' | 'done' | 'error'
  step: Step | null
  progress: number
  model: string
  result?: Result | null
  error?: string | null
  created_at?: string | null
  cancer_type?: string | null // most likely cancer type; null until a classifier exists
}

// GET /api/jobs: every analysis request, newest first. store is 'memory' when no database is configured.
export interface JobSummary {
  id: string
  created_at: string
  status: 'running' | 'done' | 'error'
  model: string
  cancer_type: string | null
}

export interface JobList {
  store: 'postgres' | 'memory'
  jobs: JobSummary[]
}

// FastAPI errors come back as { detail: "..." }. Fall back to a plain sentence, never a raw object.
export async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
  } catch {}
  return `The server answered ${res.status}. Try again in a moment.`
}
