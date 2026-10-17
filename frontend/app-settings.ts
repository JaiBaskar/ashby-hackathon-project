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
  return { maxUploadMb: num('max_upload_mb'), defaultMpp: num('default_mpp') }
}

// Names of the variables next.config's `env` (and the Vitest config) sets for the browser code.
export function settingsEnv(frontendDir: string): Record<string, string> {
  const s = readAppSettings(frontendDir)
  return { MAX_UPLOAD_MB: String(s.maxUploadMb), DEFAULT_MPP: String(s.defaultMpp) }
}
