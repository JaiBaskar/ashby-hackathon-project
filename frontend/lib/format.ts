import type { TissueClass } from './api'

export const CLASS_LABELS: Record<TissueClass, string> = {
  tumor: 'Tumor',
  stroma: 'Stroma',
  immune: 'Immune',
  necrosis: 'Necrosis',
  normal: 'Normal',
  fat_other: 'Fat / other',
}

export const STEP_LABELS = {
  finding_tissue: 'Finding tissue',
  tiling: 'Tiling',
  analyzing: 'Analyzing with CONCH',
  ranking: 'Ranking regions',
} as const

// One rounding rule for every percentage on screen, matching the backend's reasons.
export const pct = (fraction: number) => `${Math.round(fraction * 100)}%`

export const ACCEPTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.svs']

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot < 0 ? '' : name.slice(dot).toLowerCase()
}

// Settings from config.yaml, inlined by next.config.ts `env` (and the Vitest config in tests).
export const settings = {
  maxUploadMb: Number(process.env.MAX_UPLOAD_MB),
  defaultMpp: Number(process.env.DEFAULT_MPP),
}

// Box sizes come in µm (multiples of the 128 µm tile); people pick punches in mm. 512 µm reads as "0.5 mm".
export const boxLabel = (um: number) => `${Number((um / 1000).toFixed(1))} mm`
