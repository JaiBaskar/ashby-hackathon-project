import { render, screen, within } from '@testing-library/react'
import { makeStatus } from '@/test/fixtures'
import Analyzing from './Analyzing'

test('shows the four steps in order and highlights the current one', () => {
  render(<Analyzing status={makeStatus({ step: 'analyzing', progress: 0.5 })} />)
  const steps = within(screen.getByRole('list', { name: /analysis steps/i })).getAllByRole('listitem')
  expect(steps.map((s) => s.textContent)).toEqual([
    expect.stringContaining('Finding tissue'),
    expect.stringContaining('Tiling'),
    expect.stringContaining('Analyzing with CONCH'),
    expect.stringContaining('Ranking regions'),
  ])
  expect(steps[2]).toHaveAttribute('aria-current', 'step')
  expect(steps.filter((s) => s.hasAttribute('aria-current'))).toHaveLength(1)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
})

test('a queued job highlights the first step', () => {
  render(<Analyzing status={makeStatus({ status: 'queued', step: null, progress: 0 })} />)
  expect(screen.getAllByRole('listitem')[0]).toHaveAttribute('aria-current', 'step')
})

test('the error state explains what happened and offers "Try another image"', () => {
  render(<Analyzing status={makeStatus({ status: 'error', error: 'No tissue found in this image.' })} />)
  expect(screen.getByRole('alert')).toHaveTextContent('No tissue found in this image.')
  expect(screen.getByRole('link', { name: 'Try another image' })).toHaveAttribute('href', '/upload')
})

test('shows the Demo model badge with the fake model, and none with CONCH', () => {
  const { rerender } = render(<Analyzing status={makeStatus({ model: 'fake' })} />)
  expect(screen.getByText('Demo model')).toBeInTheDocument()
  rerender(<Analyzing status={makeStatus({ model: 'conch' })} />)
  expect(screen.queryByText('Demo model')).not.toBeInTheDocument()
})

test('once the tissue is found, shows the slide itself, with tiles lighting up as they are scored', () => {
  // analyzing runs from progress 0.2 to 0.9; 0.55 is halfway, so half of the 96 preview tiles are lit
  render(<Analyzing id="abc" status={makeStatus({ step: 'analyzing', progress: 0.55 })} />)
  expect(screen.getByRole('img', { name: /your slide/i })).toHaveAttribute('src', '/api/jobs/abc/display.png')
  const tiles = screen.getAllByTestId('preview-tile')
  expect(tiles).toHaveLength(96)
  expect(tiles.filter((t) => t.dataset.lit === 'true')).toHaveLength(48)
})

test('before the tissue is found there is no image yet', () => {
  render(<Analyzing id="abc" status={makeStatus({ step: 'finding_tissue', progress: 0.05 })} />)
  expect(screen.queryByRole('img', { name: /your slide/i })).not.toBeInTheDocument()
  expect(screen.getByText(/looking for tissue/i)).toBeInTheDocument()
})
