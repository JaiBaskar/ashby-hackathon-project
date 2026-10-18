import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ShortcutSheet from './ShortcutSheet'

test('? opens the shortcut sheet and Escape closes it; typing in a field does not', async () => {
  render(
    <>
      <input aria-label="somewhere to type" />
      <ShortcutSheet />
    </>,
  )
  await userEvent.click(screen.getByRole('textbox'))
  await userEvent.keyboard('?')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  ;(document.activeElement as HTMLElement).blur()
  await userEvent.keyboard('?')
  const sheet = screen.getByRole('dialog', { name: /keyboard shortcuts/i })
  expect(within(sheet).getByText('Toggle the tumor heatmap')).toBeInTheDocument()
  expect(within(sheet).getByText('Next case')).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('the header button opens it too', async () => {
  render(<ShortcutSheet />)
  await userEvent.click(screen.getByRole('button', { name: /shortcuts/i }))
  expect(screen.getByRole('dialog', { name: /keyboard shortcuts/i })).toBeInTheDocument()
})
