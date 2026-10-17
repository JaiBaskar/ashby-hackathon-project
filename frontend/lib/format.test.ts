import { ORGAN_LABELS, settings } from './format'

test('every organ in config.yaml has a label', () => {
  expect(settings.organs.length).toBeGreaterThan(1)
  for (const organ of settings.organs) expect(ORGAN_LABELS[organ]).toBeTruthy()
  expect(settings.organs).toContain(settings.defaultOrgan)
})
