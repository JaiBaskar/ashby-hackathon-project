import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { readAppSettings } from './app-settings'

// A Windows checkout (git core.autocrlf) gives config.yaml CRLF line endings; the parser must read it the same.
test('reads config.yaml with Windows (CRLF) line endings', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'cfg-'))
  const frontend = path.join(root, 'frontend')
  mkdirSync(frontend)
  const lf = readFileSync(path.join(__dirname, '..', 'config.yaml'), 'utf8').replace(/\r\n/g, '\n')
  writeFileSync(path.join(root, 'config.yaml'), lf.replace(/\n/g, '\r\n'))
  const crlf = readAppSettings(frontend)
  writeFileSync(path.join(root, 'config.yaml'), lf)
  expect(crlf).toEqual(readAppSettings(frontend))
  expect(crlf.scoreWeights).toEqual({ necrosis: 1.0, variation: 0.5 })
})
