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
