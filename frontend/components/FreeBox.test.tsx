import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse, makeMeasured, makeResult } from '@/test/fixtures'
import Results from './Results'

// The 2048 px display image is drawn 1024 px wide at the page origin: 1 rendered px = 2 display px.
const fetchMock = vi.fn()
beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation(async (url: string) => {
    const q = new URL(url, 'http://x').searchParams
    const [x, y, w, h] = ['x', 'y', 'w', 'h'].map((k) => Number(q.get(k)))
    return jsonResponse(makeMeasured(x, y, w, h))
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    () => ({ width: 1024, height: 768, x: 0, y: 0, top: 0, left: 0, right: 1024, bottom: 768, toJSON() {} }) as DOMRect,
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

const freeBox = () => screen.getByRole('group', { name: /your box/i })
const queryFreeBox = () => screen.queryByRole('group', { name: /your box/i })
const panel = () => within(screen.getByRole('region', { name: /region details/i }))
const measured = (i = -1) => new URL(fetchMock.mock.calls.at(i)![0], 'http://x').searchParams

function drag(target: Element, from: [number, number], to: [number, number]) {
  fireEvent.pointerDown(target, { clientX: from[0], clientY: from[1], button: 0 })
  fireEvent.pointerMove(window, { clientX: (from[0] + to[0]) / 2, clientY: (from[1] + to[1]) / 2 })
  fireEvent.pointerMove(window, { clientX: to[0], clientY: to[1] })
  fireEvent.pointerUp(window, { clientX: to[0], clientY: to[1] })
}

async function draw(from: [number, number], to: [number, number]) {
  await userEvent.click(screen.getByRole('button', { name: 'Draw a box' }))
  await act(async () => drag(screen.getByTestId('draw-surface'), from, to))
}

test('drag on the slide to draw a box of any shape, then see its numbers', async () => {
  render(<Results result={makeResult()} />)
  expect(screen.getByRole('button', { name: 'Draw a box' })).toHaveAttribute('aria-pressed', 'false')
  await draw([100, 100], [300, 250])

  expect(freeBox()).toHaveStyle({ left: '100px', top: '100px', width: '200px', height: '150px' })
  expect(Object.fromEntries(measured())).toEqual({ x: '200', y: '200', w: '400', h: '300' })
  expect(fetchMock.mock.calls[0][0]).toMatch(/^\/api\/jobs\/abc\/measure\?/)
  expect(await panel().findByRole('heading', { name: 'Your box' })).toBeInTheDocument()
  expect(panel().getByTestId('size')).toHaveTextContent('200 × 150 µm')
  expect(panel().getByTestId('tumor-vs-slide')).toHaveTextContent('44% here vs. 41% across the slide')
  expect(panel().getByText('Low necrosis (3%), which favors good DNA yield')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Draw a box' })).toHaveAttribute('aria-pressed', 'false') // one box per draw
})

test('drawing up and to the left gives the same box', async () => {
  render(<Results result={makeResult()} />)
  await draw([300, 250], [100, 100])
  expect(freeBox()).toHaveStyle({ left: '100px', top: '100px', width: '200px', height: '150px' })
})

test('a click without a drag draws nothing', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [101, 102])
  expect(queryFreeBox()).not.toBeInTheDocument()
  expect(fetchMock).not.toHaveBeenCalled()
})

test('Escape leaves drawing mode', async () => {
  render(<Results result={makeResult()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Draw a box' }))
  expect(screen.getByTestId('draw-surface')).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByTestId('draw-surface')).not.toBeInTheDocument()
})

test('drag a corner handle to resize it freely', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await act(async () => drag(within(freeBox()).getByTestId('handle-se'), [300, 250], [420, 290]))
  expect(freeBox()).toHaveStyle({ left: '100px', top: '100px', width: '320px', height: '190px' })
  expect(Object.fromEntries(measured())).toEqual({ x: '200', y: '200', w: '640', h: '380' })
})

test('drag an edge handle to change only that side, and past the other side to flip it', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await act(async () => drag(within(freeBox()).getByTestId('handle-n'), [200, 100], [200, 40]))
  expect(freeBox()).toHaveStyle({ left: '100px', top: '40px', width: '200px', height: '210px' })
  await act(async () => drag(within(freeBox()).getByTestId('handle-w'), [100, 150], [400, 150]))
  expect(freeBox()).toHaveStyle({ left: '300px', top: '40px', width: '100px', height: '210px' })
})

test('drag the box to move it; it stays inside the image', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await act(async () => drag(freeBox(), [150, 150], [200, 170]))
  expect(freeBox()).toHaveStyle({ left: '150px', top: '120px', width: '200px', height: '150px' })
  await act(async () => drag(freeBox(), [200, 200], [5000, 5000]))
  expect(freeBox()).toHaveStyle({ left: '824px', top: '618px', width: '200px', height: '150px' })
})

test('"Adjust this box" turns a suggested region into a box you can reshape', async () => {
  const result = makeResult()
  render(<Results result={result} />)
  await userEvent.click(screen.getByRole('button', { name: /^Region 3/ }))
  await userEvent.click(panel().getByRole('button', { name: 'Adjust this box' }))
  const r = result.regions[2]
  expect(freeBox()).toHaveStyle({ left: `${r.x / 2}px`, top: `${r.y / 2}px`, width: `${r.w / 2}px`, height: `${r.h / 2}px` })
  expect(Object.fromEntries(measured())).toEqual({ x: String(r.x), y: String(r.y), w: String(r.w), h: String(r.h) })
  expect(await panel().findByRole('heading', { name: 'Your box' })).toBeInTheDocument()
})

test('switching between a suggested region and your box, and removing your box', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await panel().findByRole('heading', { name: 'Your box' })

  await userEvent.click(screen.getByRole('button', { name: /^Region 2/ }))
  expect(panel().getByRole('heading', { name: /region 2/i })).toBeInTheDocument()
  expect(queryFreeBox()).toBeInTheDocument() // still drawn

  await userEvent.click(freeBox())
  expect(panel().getByRole('heading', { name: 'Your box' })).toBeInTheDocument()
  await userEvent.click(panel().getByRole('button', { name: 'Remove your box' }))
  expect(queryFreeBox()).not.toBeInTheDocument()
  expect(panel().getByRole('heading', { name: /region 1/i })).toBeInTheDocument()
})

test('the server\'s message shows when a box can\'t be measured', async () => {
  // Every request in the gesture fails (the box is scored mid-drag too, and the latest answer wins).
  fetchMock.mockImplementation(async () => jsonResponse({ detail: 'This box has no analyzed tissue in it. Move it over the tissue.' }, 400))
  render(<Results result={makeResult()} />)
  await draw([0, 0], [20, 20])
  expect(await panel().findByRole('alert')).toHaveTextContent('This box has no analyzed tissue in it.')
})

test('choosing "Draw a box" from the keyboard places a box you can then move with the keys', async () => {
  render(<Results result={makeResult()} />)
  screen.getByRole('button', { name: 'Draw a box' }).focus()
  await userEvent.keyboard('{Enter}')
  // The best region's size (256 display px = 128 rendered px), centered on the 1024 × 768 rendered image.
  expect(freeBox()).toHaveFocus()
  expect(freeBox()).toHaveStyle({ left: '448px', top: '320px', width: '128px', height: '128px' })
})

// --- every box is resizable, and the numbers follow the box while you drag --------------------------

function press(target: Element, at: [number, number]) {
  fireEvent.pointerDown(target, { clientX: at[0], clientY: at[1], button: 0 })
}
const moveTo = (at: [number, number]) => fireEvent.pointerMove(window, { clientX: at[0], clientY: at[1] })
const release = (at: [number, number]) => fireEvent.pointerUp(window, { clientX: at[0], clientY: at[1] })

test('the selected suggestion has handles: drag its corner to resize it, no extra button needed', async () => {
  const result = makeResult()
  render(<Results result={result} />)
  const r = result.regions[0] // selected at first; drawn at half size: (600, 150), 128 × 128 rendered px
  const best = screen.getByRole('button', { name: /^Region 1/ })
  await act(async () => drag(within(best).getByTestId('handle-se'), [728, 278], [828, 318]))
  expect(freeBox()).toHaveStyle({ left: `${r.x / 2}px`, top: `${r.y / 2}px`, width: '228px', height: '168px' })
  expect(Object.fromEntries(measured())).toEqual({ x: String(r.x), y: String(r.y), w: '456', h: '336' })
  expect(await panel().findByRole('heading', { name: 'Your box' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^Region 1/ })).toBeInTheDocument() // the suggestion stays for comparison
})

test('only the selected suggestion shows handles', async () => {
  render(<Results result={makeResult()} />)
  const [first, second] = screen.getAllByRole('button', { name: /^Region \d/ })
  expect(within(first).queryByTestId('handle-se')).toBeInTheDocument()
  expect(within(second).queryByTestId('handle-se')).not.toBeInTheDocument()
  await userEvent.click(second)
  expect(within(second).queryByTestId('handle-se')).toBeInTheDocument()
})

test('a corner drags the box out to the whole image and down to almost nothing', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await act(async () => drag(within(freeBox()).getByTestId('handle-nw'), [100, 100], [-500, -500]))
  await act(async () => drag(within(freeBox()).getByTestId('handle-se'), [300, 250], [5000, 5000]))
  expect(freeBox()).toHaveStyle({ left: '0px', top: '0px', width: '1024px', height: '768px' })
  expect(Object.fromEntries(measured())).toEqual({ x: '0', y: '0', w: '2048', h: '1536' })

  await act(async () => drag(within(freeBox()).getByTestId('handle-se'), [1024, 768], [0, 0]))
  expect(freeBox()).toHaveStyle({ left: '0px', top: '0px', width: '1px', height: '1px' }) // 2 display px, the minimum
})

test('the score is recalculated while the corner is still held, not only on release', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await panel().findByText('0.37')
  const before = fetchMock.mock.calls.length
  fetchMock.mockImplementation(async (url: string) => {
    const q = new URL(url, 'http://x').searchParams
    const w = Number(q.get('w'))
    return jsonResponse(makeMeasured(Number(q.get('x')), Number(q.get('y')), w, Number(q.get('h')), { score: w / 1000 }))
  })

  const handle = within(freeBox()).getByTestId('handle-se')
  await act(async () => {
    press(handle, [300, 250])
    moveTo([350, 250])
  })
  expect(Object.fromEntries(measured())).toEqual({ x: '200', y: '200', w: '500', h: '300' })
  expect(await panel().findByText('0.50')).toBeInTheDocument() // updated mid-drag
  await act(async () => moveTo([400, 300]))
  expect(await panel().findByText('0.60')).toBeInTheDocument()
  await act(async () => release([400, 300]))
  expect(fetchMock.mock.calls.length).toBeGreaterThan(before + 1)
  expect(Object.fromEntries(measured())).toEqual({ x: '200', y: '200', w: '600', h: '400' })
})

test('while one score request is out, moves wait and only the newest box is sent next', async () => {
  render(<Results result={makeResult()} />)
  await draw([100, 100], [300, 250])
  await panel().findByText('0.37')
  const answers: ((r: Response) => void)[] = []
  fetchMock.mockImplementation(
    (url: string) =>
      new Promise<Response>((resolve) => {
        const q = new URL(url, 'http://x').searchParams
        const [x, y, w, h] = ['x', 'y', 'w', 'h'].map((k) => Number(q.get(k)))
        answers.push(() => resolve(jsonResponse(makeMeasured(x, y, w, h, { score: w / 1000 }))))
      }),
  )
  const calls = fetchMock.mock.calls.length
  const handle = within(freeBox()).getByTestId('handle-se')
  await act(async () => {
    press(handle, [300, 250])
    moveTo([310, 250])
    moveTo([320, 250])
    moveTo([330, 250])
  })
  expect(fetchMock.mock.calls.length).toBe(calls + 1) // one in flight, the rest held back
  await act(async () => answers.shift()!(new Response()))
  expect(fetchMock.mock.calls.length).toBe(calls + 2)
  expect(measured().get('w')).toBe('460') // the newest box (330 rendered px wide edge), not the in-between ones
  await act(async () => answers.shift()!(new Response()))
  expect(await panel().findByText('0.46')).toBeInTheDocument()
})
