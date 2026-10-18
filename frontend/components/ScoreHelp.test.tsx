import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { settings } from '@/lib/format'
import { makeMeasured, makeResult } from '@/test/fixtures'
import FreeBoxPanel from './FreeBoxPanel'
import ScoreHelp from './ScoreHelp'

const trigger = () => screen.getByRole('button', { name: 'How the score is calculated' })

test('a question-mark button with an accessible name; the explanation is hidden at first', () => {
  render(<ScoreHelp />)
  expect(trigger()).toHaveTextContent('?')
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})

test('hovering shows the formula with the weights from config.yaml', async () => {
  render(<ScoreHelp />)
  await userEvent.hover(trigger())
  const tip = screen.getByRole('tooltip')
  expect(settings.scoreWeights).toEqual({ necrosis: 1, variation: 0.5 })
  expect(tip).toHaveTextContent('Score = tumor − 1 × necrosis − 0.5 × unevenness')
  expect(tip).toHaveTextContent(/standard deviation/)
  expect(trigger()).toHaveAttribute('aria-describedby', tip.id)
  await userEvent.unhover(trigger())
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})

test('keyboard focus shows it, and Escape hides it', async () => {
  render(<ScoreHelp />)
  await userEvent.tab()
  expect(trigger()).toHaveFocus()
  expect(screen.getByRole('tooltip')).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})

test('a tap (click) opens it, for touch screens', async () => {
  render(<ScoreHelp />)
  trigger().focus()
  await userEvent.keyboard('{Escape}')
  await userEvent.click(trigger())
  expect(screen.getByRole('tooltip')).toBeInTheDocument()
})

test("the user's own box shows the same help next to its score", () => {
  render(
    <FreeBoxPanel measured={makeMeasured(200, 200, 400, 300)} measuring={false} error={null} result={makeResult()} threshold={0.2} onRemove={() => {}} />,
  )
  expect(trigger()).toBeInTheDocument()
})
