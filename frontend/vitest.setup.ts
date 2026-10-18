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

// Newer Node versions define their own `localStorage` global (undefined without --localstorage-file), which
// hides jsdom's. Give the tests a working in-memory one.
if (typeof window !== 'undefined' && !(globalThis.localStorage && typeof globalThis.localStorage.clear === 'function')) {
  class MemoryStorage implements Storage {
    private data = new Map<string, string>()
    get length() {
      return this.data.size
    }
    clear() {
      this.data.clear()
    }
    getItem(key: string) {
      return this.data.has(key) ? this.data.get(key)! : null
    }
    key(i: number) {
      return [...this.data.keys()][i] ?? null
    }
    removeItem(key: string) {
      this.data.delete(key)
    }
    setItem(key: string, value: string) {
      this.data.set(key, String(value))
    }
  }
  const storage = new MemoryStorage()
  // Object.keys(localStorage) lists stored keys, as in a browser.
  const proxied = new Proxy(storage, {
    ownKeys: (t) => [...(t as unknown as { data: Map<string, string> }).data.keys()],
    getOwnPropertyDescriptor: (t, k) =>
      (t as unknown as { data: Map<string, string> }).data.has(String(k))
        ? { enumerable: true, configurable: true, value: storage.getItem(String(k)) }
        : undefined,
    get: (t, k) => {
      const v = Reflect.get(t, k)
      return typeof v === 'function' ? v.bind(t) : v
    },
  })
  for (const target of [globalThis, window]) {
    Object.defineProperty(target, 'localStorage', { configurable: true, value: proxied })
  }
}
