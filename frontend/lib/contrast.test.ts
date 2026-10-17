import { contrastRatio, relativeLuminance } from './contrast'

// Hand-computed with the WCAG 2.x formulas (sRGB → linear, L = 0.2126 R + 0.7152 G + 0.0722 B,
// ratio = (L1 + 0.05) / (L2 + 0.05)).
test('black on white is 21:1', () => {
  expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 6)
  expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21, 6)
})

test('a color against itself is 1:1', () => {
  expect(contrastRatio('#6B4C9A', '#6B4C9A')).toBeCloseTo(1, 6)
})

test('eosin pink and hematoxylin purple luminances match the hand calculation', () => {
  // Pink #E8B4C8: 0.2126·0.80694 + 0.7152·0.45641 + 0.0722·0.57758 = 0.5397
  expect(relativeLuminance('#E8B4C8')).toBeCloseTo(0.5397, 3)
  // Purple #6B4C9A: about 0.106 (implementation-steps.md, Phase 5)
  expect(relativeLuminance('#6B4C9A')).toBeCloseTo(0.106, 2)
})

test('only near-black clears 3:1 on hematoxylin purple', () => {
  // (0.1065 + 0.05) / 0.05 = 3.13
  expect(contrastRatio('#000000', '#6B4C9A')).toBeCloseTo(3.13, 2)
  // #0A0A0A: 10/255 = 0.0392 < 0.04045, so linear = 0.0392 / 12.92 = 0.00304;
  // (0.1065 + 0.05) / (0.00304 + 0.05) = 2.95
  expect(contrastRatio('#0A0A0A', '#6B4C9A')).toBeCloseTo(2.95, 2)
})

test('3-digit hex is expanded', () => {
  expect(contrastRatio('#000', '#fff')).toBeCloseTo(21, 6)
})

test('a malformed color throws', () => {
  expect(() => relativeLuminance('red')).toThrow()
})
