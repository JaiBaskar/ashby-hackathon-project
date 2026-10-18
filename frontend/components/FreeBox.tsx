'use client'

import { forwardRef, useEffect, useRef } from 'react'

// A rectangle in display-image pixels, like the API's region boxes.
export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export type Handle = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
export const HANDLES: Exclude<Handle, 'move'>[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
const MIN_PX = 2 // display px: a side never collapses to nothing while resizing
export const KEY_STEP = 16 // display px per arrow key press

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

// Two corners → a rectangle inside the image, whichever way the drag went (like a screenshot selection).
export function fromCorners(ax: number, ay: number, bx: number, by: number, width: number, height: number): Rect {
  const [l, r] = [clamp(Math.min(ax, bx), 0, width), clamp(Math.max(ax, bx), 0, width)]
  const [t, b] = [clamp(Math.min(ay, by), 0, height), clamp(Math.max(ay, by), 0, height)]
  return { x: l, y: t, w: r - l, h: b - t }
}

// Moving keeps the size and stays inside the image; a handle moves only its own sides, and dragging a side
// past the opposite one flips the box.
export function dragRect(start: Rect, handle: Handle, dx: number, dy: number, width: number, height: number): Rect {
  if (handle === 'move') {
    return { ...start, x: clamp(start.x + dx, 0, width - start.w), y: clamp(start.y + dy, 0, height - start.h) }
  }
  let [l, r, t, b] = [start.x, start.x + start.w, start.y, start.y + start.h]
  if (handle.includes('w')) l += dx
  if (handle.includes('e')) r += dx
  if (handle.includes('n')) t += dy
  if (handle.includes('s')) b += dy
  const rect = fromCorners(l, t, r, b, width, height)
  return { ...rect, w: Math.max(rect.w, MIN_PX), h: Math.max(rect.h, MIN_PX) }
}

// Arrow keys move the box; with Shift they grow or shrink it from the right and bottom edges.
export function keyRect(rect: Rect, key: string, shift: boolean, width: number, height: number): Rect | null {
  const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[key]
  if (!d) return null
  const [dx, dy] = [d[0] * KEY_STEP, d[1] * KEY_STEP]
  return dragRect(rect, shift ? 'se' : 'move', dx, dy, width, height)
}

// Pointer drags: follow the pointer on window (so a fast drag can't escape the element), report every
// step in display px, and report the end only if the pointer actually moved.
export function useDrag<K>(scale: number, onDrag: (key: K, dx: number, dy: number, done: boolean) => void) {
  const latest = useRef(onDrag)
  useEffect(() => void (latest.current = onDrag))
  return (key: K, e: React.PointerEvent) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()
    const [sx, sy] = [e.clientX, e.clientY]
    let moved = false
    const step = (ev: PointerEvent, done: boolean) => latest.current(key, (ev.clientX - sx) / scale, (ev.clientY - sy) / scale, done)
    const move = (ev: PointerEvent) => {
      moved = true
      step(ev, false)
    }
    const up = (ev: PointerEvent) => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (moved) step(ev, true)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
}

export const HANDLE_POS: Record<Exclude<Handle, 'move'>, string> = {
  nw: '-top-1.5 -left-1.5 cursor-nwse-resize',
  n: '-top-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize',
  ne: '-top-1.5 -right-1.5 cursor-nesw-resize',
  e: 'top-1/2 -right-1.5 -translate-y-1/2 cursor-ew-resize',
  se: '-right-1.5 -bottom-1.5 cursor-nwse-resize',
  s: '-bottom-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize',
  sw: '-bottom-1.5 -left-1.5 cursor-nesw-resize',
  w: 'top-1/2 -left-1.5 -translate-y-1/2 cursor-ew-resize',
}

interface Props {
  rect: Rect
  scale: number
  bounds: { width: number; height: number }
  selected: boolean
  label: string
  onSelect: () => void
  onChange: (rect: Rect, when: 'drag' | 'now' | 'soon') => void
}

// The user's own box: drag inside to move, drag a handle to resize, arrow keys for keyboard users.
const FreeBox = forwardRef<HTMLDivElement, Props>(function FreeBox({ rect, scale, bounds, selected, label, onSelect, onChange }, ref) {
  const start = useRef(rect)
  const drag = useDrag<Handle>(scale, (handle, dx, dy, done) =>
    onChange(dragRect(start.current, handle, dx, dy, bounds.width, bounds.height), done ? 'now' : 'drag'),
  )
  const begin = (handle: Handle) => (e: React.PointerEvent) => {
    start.current = rect
    onSelect()
    drag(handle, e)
  }

  return (
    <div
      ref={ref}
      role="group"
      aria-roledescription="resizable box"
      aria-label={label}
      tabIndex={0}
      onPointerDown={begin('move')}
      onClick={onSelect}
      onKeyDown={(e) => {
        const next = keyRect(rect, e.key, e.shiftKey, bounds.width, bounds.height)
        if (!next) return
        e.preventDefault()
        onSelect()
        onChange(next, 'soon')
      }}
      style={{ left: `${rect.x * scale}px`, top: `${rect.y * scale}px`, width: `${rect.w * scale}px`, height: `${rect.h * scale}px` }}
      className={`free-box absolute cursor-move touch-none rounded-sm ${selected ? 'z-20' : 'z-10'}`}
    >
      <span className="absolute -top-0.5 -left-0.5 -translate-x-px -translate-y-px rounded-br-sm bg-box-outline px-1.5 py-0.5 text-xs font-semibold text-box-other">
        Yours
      </span>
      {HANDLES.map((h) => (
        <span
          key={h}
          aria-hidden
          data-testid={`handle-${h}`}
          onPointerDown={begin(h)}
          className={`free-box-handle absolute size-3 rounded-[2px] ${HANDLE_POS[h]}`}
        />
      ))}
    </div>
  )
})

export default FreeBox
