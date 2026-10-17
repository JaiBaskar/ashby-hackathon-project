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
  organs: (process.env.ORGANS ?? '').split(',').filter(Boolean),
  defaultOrgan: process.env.DEFAULT_ORGAN ?? '',
}

// Display names for config.yaml's organs. The backend picks that organ's CONCH prompts.
export const ORGAN_LABELS: Record<string, string> = {
  colon: 'Colon / rectum',
  lung: 'Lung',
  breast: 'Breast',
  pancreas: 'Pancreas',
  prostate: 'Prostate',
  other: 'Other / unknown',
}

export const organLabel = (organ: string) => ORGAN_LABELS[organ] ?? organ
