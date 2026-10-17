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

// "Oct 17, 2026, 2:05 PM" in the viewer's time zone (or a fixed one, for tests).
export function formatCreated(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone }).format(new Date(iso))
}

export function cancerTypeLabel(type: string | null | undefined): string {
  if (!type) return 'Not identified yet'
  return type.charAt(0).toUpperCase() + type.slice(1).replaceAll('_', ' ')
}
