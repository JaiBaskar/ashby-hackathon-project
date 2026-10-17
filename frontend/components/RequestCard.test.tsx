import { render, screen } from '@testing-library/react'
import type { JobSummary } from '@/lib/api'
import RequestCard from './RequestCard'

const job = (overrides: Partial<JobSummary> = {}): JobSummary => ({
  id: '0123456789abcdef0123456789abcdef',
  created_at: '2026-10-17T14:05:00+00:00',
  status: 'done',
  model: 'conch',
  cancer_type: null,
  ...overrides,
})

test('the whole card links to the full results page', () => {
  render(<RequestCard job={job()} timeZone="UTC" />)
  expect(screen.getByRole('link')).toHaveAttribute('href', '/jobs/0123456789abcdef0123456789abcdef')
})

test('shows when the request was created, as a machine-readable time', () => {
  render(<RequestCard job={job()} timeZone="UTC" />)
  const time = screen.getByText('Oct 17, 2026, 2:05 PM')
  expect(time.tagName).toBe('TIME')
  expect(time).toHaveAttribute('dateTime', '2026-10-17T14:05:00+00:00')
})

test('shows the most likely cancer type when there is one', () => {
  render(<RequestCard job={job({ cancer_type: 'breast' })} timeZone="UTC" />)
  expect(screen.getByText('Cancer type').nextElementSibling).toHaveTextContent('Breast')
})

test('says the cancer type is not identified yet when there is none', () => {
  render(<RequestCard job={job()} timeZone="UTC" />)
  expect(screen.getByText('Cancer type').nextElementSibling).toHaveTextContent('Not identified yet')
})

test.each([
  ['done', 'Done'],
  ['running', 'Running'],
  ['error', 'Failed'],
] as const)('status %s reads "%s"', (status, label) => {
  render(<RequestCard job={job({ status })} timeZone="UTC" />)
  expect(screen.getByText(label)).toBeInTheDocument()
})

test('marks demo-model runs', () => {
  render(<RequestCard job={job({ model: 'fake' })} timeZone="UTC" />)
  expect(screen.getByText('Demo model')).toBeInTheDocument()
})
