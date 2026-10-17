import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { FIXTURE_DIR } from './fixtures'

// Generate the synthetic fixtures (slide, blank, > 10 MB) with the committed backend script.
export default function globalSetup() {
  const python = process.env.PYTHON ?? '../.venv/bin/python'
  execFileSync(python, [path.join('..', 'backend', 'tests', 'fixtures', 'make_fixtures.py'), FIXTURE_DIR], {
    stdio: 'inherit',
  })
}
