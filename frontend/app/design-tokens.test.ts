import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { contrastRatio } from '@/lib/contrast'

// Reads the design tokens straight from globals.css, so the test checks what the app actually ships.
const css = readFileSync(path.join(__dirname, 'globals.css'), 'utf8')

// Text of the `{ ... }` block that opens right after `header` (handles nested braces).
function blockAfter(header: string): string {
  const start = css.indexOf(header)
  if (start < 0) throw new Error(`globals.css has no "${header}" block`)
  const open = css.indexOf('{', start)
  let depth = 0
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++
    if (css[i] === '}' && --depth === 0) return css.slice(open + 1, i)
  }
  throw new Error(`unclosed block after "${header}"`)
}

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

const light = tokens(blockAfter('@theme static'))
const dark = { ...light, ...tokens(blockAfter('@media (prefers-color-scheme: dark)')) }

function color(t: Record<string, string>, name: string): string {
  const v = t[`--color-${name}`]
  if (!v || !/^#[0-9a-f]{6}$/i.test(v)) throw new Error(`--color-${name} must be a 6-digit hex, got ${v}`)
  return v
}

// The two stains a box is drawn over (implementation-steps.md, Phase 5).
const TISSUE = { eosin: '#E8B4C8', hematoxylin: '#6B4C9A' }

// A box is two strokes: a black outer outline and a colored inner stroke. Against each tissue color,
// at least one of the two layers must reach 3:1 (WCAG non-text contrast).
describe.each([
  ['best', 'box-best'],
  ['other', 'box-other'],
])('the %s box', (_, inner) => {
  describe.each(Object.entries(TISSUE))('over %s', (_, tissue) => {
    test.each([
      ['light', light],
      ['dark', dark],
    ])('reaches 3:1 in %s mode', (_, t) => {
      const layers = [color(t, 'box-outline'), color(t, inner)]
      const best = Math.max(...layers.map((c) => contrastRatio(c, tissue)))
      expect(best).toBeGreaterThanOrEqual(3)
    })
  })
})

test('the two box styles have different inner colors', () => {
  expect(color(light, 'box-best').toLowerCase()).not.toBe(color(light, 'box-other').toLowerCase())
})

test('the best box stands out without color: a thicker stroke', () => {
  const px = (name: string) => parseFloat(light[`--box-stroke-${name}`])
  expect(px('best')).toBeGreaterThan(px('other'))
})

// Text and control contrast for the app chrome, in both themes.
describe.each([
  ['light', light],
  ['dark', dark],
])('%s mode', (_, t) => {
  test.each([
    ['ink', 'canvas'],
    ['ink', 'surface'],
    ['ink-muted', 'canvas'],
    ['ink-muted', 'surface'],
    ['accent-ink', 'accent'],
    ['accent-strong', 'surface'],
    ['danger', 'surface'],
  ])('%s on %s is at least 4.5:1', (fg, bg) => {
    expect(contrastRatio(color(t, fg), color(t, bg))).toBeGreaterThanOrEqual(4.5)
  })

  test('the focus ring reaches 3:1 on the canvas', () => {
    expect(contrastRatio(color(t, 'focus'), color(t, 'canvas'))).toBeGreaterThanOrEqual(3)
  })
})

test('dark mode redefines every chrome color', () => {
  const darkOnly = tokens(blockAfter('@media (prefers-color-scheme: dark)'))
  for (const name of ['canvas', 'surface', 'ink', 'ink-muted', 'line', 'accent', 'accent-strong', 'focus']) {
    expect(darkOnly[`--color-${name}`], name).toBeDefined()
  }
})

// Components use tokens only: no hex colors outside globals.css.
test('no one-off hex colors in components', () => {
  const root = path.join(__dirname, '..')
  const offenders: string[] = []
  for (const dir of ['app', 'components']) {
    let files: string[]
    try {
      files = readdirSync(path.join(root, dir), { recursive: true }) as string[]
    } catch {
      continue
    }
    for (const f of files) {
      if (!/\.(tsx?|css)$/.test(f) || /\.test\.tsx?$/.test(f) || f.endsWith('globals.css')) continue
      const text = readFileSync(path.join(root, dir, f), 'utf8')
      if (/#[0-9a-f]{3,8}\b/i.test(text)) offenders.push(`${dir}/${f}`)
    }
  }
  expect(offenders).toEqual([])
})
