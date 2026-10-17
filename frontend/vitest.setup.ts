import '@testing-library/jest-dom/vitest'

// jsdom has no PointerEvent; a MouseEvent subclass carries clientX/clientY for the free-box drag tests.
if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  class PointerEvent extends MouseEvent {
    pointerId: number
    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init)
      this.pointerId = init.pointerId ?? 1
    }
  }
  Object.assign(window, { PointerEvent })
}
