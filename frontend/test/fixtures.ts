import type { Composition, JobStatus, Region, Result } from '@/lib/api'

const comp = (tumor: number, necrosis: number): Composition => {
  const rest = 1 - tumor - necrosis
  return { tumor, stroma: rest * 0.5, immune: rest * 0.2, necrosis, normal: rest * 0.2, fat_other: rest * 0.1 }
}

function region(rank: number, x: number, y: number, tumor: number, necrosis: number, reasons: string[]): Region {
  return {
    rank,
    is_best: rank === 1,
    x,
    y,
    w: 256,
    h: 256,
    score: Number((tumor - necrosis - 0.02).toFixed(2)),
    tissue_coverage: 0.98 - rank * 0.01,
    tumor_std: 0.04 + rank * 0.01,
    composition: comp(tumor, necrosis),
    size_um: 512,
    reasons,
  }
}

// A 2048×1536 display image with five regions; region 3 sits at x = 800.
export function makeResult(overrides: Partial<Result> = {}): Result {
  return {
    model: 'fake',
    image: { url: '/api/jobs/abc/display.png', width: 2048, height: 1536, mpp: 0.5, mpp_estimated: false },
    heatmap_url: '/api/jobs/abc/heatmap.png',
    tiles: { count: 412, capped: false },
    slide_composition: comp(0.41, 0.05),
    regions: [
      region(1, 1200, 300, 0.62, 0.03, ['Highest tumor content of all candidates (62%)', 'Low necrosis (3%), which favors good DNA yield']),
      region(2, 300, 900, 0.54, 0.04, ['Tumor content is 8 points lower than the best region']),
      region(3, 800, 200, 0.51, 0.02, ['Tumor content is 11 points lower than the best region', 'Fully on tissue (96% coverage)']),
      region(4, 1500, 1000, 0.47, 0.06, ['Tumor content is 15 points lower than the best region']),
      region(5, 100, 100, 0.44, 0.02, ['Tumor content is 18 points lower than the best region']),
    ],
    note: null,
    ...overrides,
  }
}

export function makeStatus(overrides: Partial<JobStatus> = {}): JobStatus {
  return { status: 'running', step: 'tiling', progress: 0.15, model: 'fake', result: null, error: null, ...overrides }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}
