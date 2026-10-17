import { render, screen } from '@testing-library/react'
import Home from './page'

test('home has a headline, a one-line explanation and an "Analyze a slide" button to the upload screen', () => {
  render(<Home />)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/sample/i)
  expect(screen.getByText(/upload a photo or scan of an h&e slide/i)).toBeInTheDocument()
  const cta = screen.getByRole('link', { name: 'Analyze a slide' })
  expect(cta).toHaveAttribute('href', '/upload')
})

test('home carries the research-use notice', () => {
  render(<Home />)
  expect(screen.getByText(/research prototype/i)).toBeInTheDocument()
})
