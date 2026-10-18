import { readFileSync } from 'node:fs'
import path from 'node:path'

// The few config.yaml values the frontend needs. Read by next.config.ts (build/dev) and vitest.config.mts
// (tests), so both see the same numbers. Node-only: the browser gets them through next.config's `env`.
export function readAppSettings(frontendDir: string) {
  const config = readFileSync(path.join(frontendDir, '..', 'config.yaml'), 'utf8')
  const num = (key: string) => {
    const v = Number(new RegExp(`^${key}:\\s*([\\d.]+)`, 'm').exec(config)?.[1])
    if (!v) throw new Error(`config.yaml needs ${key}`)
    return v
  }
  const organs = /^organs:\s*\[([^\]]*)\]/m.exec(config)?.[1].split(',').map((o) => o.trim()).filter(Boolean)
  const defaultOrgan = /^default_organ:\s*(\S+)/m.exec(config)?.[1]
  if (!organs?.length || !defaultOrgan) throw new Error('config.yaml needs organs and default_organ')
  // The ranking score's weights, for the "how is the score calculated" help (backend/project/regions.py).
  const weightsBlock = /^weights:\s*\n((?:[ \t]+\S.*\n?)+)/m.exec(config)?.[1] ?? ''
  const weight = (key: string) => {
    const v = Number(new RegExp(`^\\s+${key}:\\s*([\\d.]+)`, 'm').exec(weightsBlock)?.[1])
    if (Number.isNaN(v) || !weightsBlock.includes(key)) throw new Error(`config.yaml needs weights.${key}`)
    return v
  }
  const scoreWeights = { necrosis: weight('necrosis'), variation: weight('variation') }
  return { maxUploadMb: num('max_upload_mb'), defaultMpp: num('default_mpp'), organs, defaultOrgan, scoreWeights }
}

// Names of the variables next.config's `env` (and the Vitest config) sets for the browser code.
export function settingsEnv(frontendDir: string): Record<string, string> {
  const s = readAppSettings(frontendDir)
  return {
    MAX_UPLOAD_MB: String(s.maxUploadMb),
    DEFAULT_MPP: String(s.defaultMpp),
    ORGANS: s.organs.join(','),
    DEFAULT_ORGAN: s.defaultOrgan,
    SCORE_WEIGHT_NECROSIS: String(s.scoreWeights.necrosis),
    SCORE_WEIGHT_VARIATION: String(s.scoreWeights.variation),
  }
}
