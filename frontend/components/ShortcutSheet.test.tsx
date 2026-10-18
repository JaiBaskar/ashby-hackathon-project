import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ShortcutSheet from './ShortcutSheet'

test('the header button opens the shortcut sheet and Escape closes it', async () => {
  render(<ShortcutSheet />)
  await userEvent.click(screen.getByRole('button', { name: /shortcuts/i }))
  const sheet = screen.getByRole('dialog', { name: /keyboard shortcuts/i })
  expect(within(sheet).getByText('Toggle the tumor heatmap')).toBeInTheDocument()
  expect(within(sheet).getByText('Next case')).toBeInTheDocument()
  expect(within(sheet).queryByText('Show these shortcuts')).not.toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('? does not open the sheet', async () => {
  render(<ShortcutSheet />)
  await userEvent.keyboard('?')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
