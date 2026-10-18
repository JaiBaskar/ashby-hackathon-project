'use client'

import { useCallback, useState, useSyncExternalStore } from 'react'

// What a pathologist adds to a case: a label (e.g. an accession or block ID), notes, a reviewed tick,
// and their own box. All of it stays in this browser (localStorage). It is never sent to the server or
// the shared history database, because labels and notes can identify a patient.

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export interface CaseEntry {
  label: string
  notes: string
  reviewed: boolean
  box: Rect | null
}

const EMPTY: CaseEntry = { label: '', notes: '', reviewed: false, box: null }
export const DEFAULT_THRESHOLD = 20
const CASE = (id: string) => `ssf.case.${id}`
const THRESHOLD = 'ssf.threshold'
const CHANGED = 'ssf:casebook'

// Storage can throw (private windows, blocked site data). Every read and write falls back quietly.
function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {}
  window.dispatchEvent(new Event(CHANGED))
}

function subscribe(onChange: () => void) {
  window.addEventListener('storage', onChange)
  window.addEventListener(CHANGED, onChange)
  return () => {
    window.removeEventListener('storage', onChange)
    window.removeEventListener(CHANGED, onChange)
  }
}

// Parsed values are cached by their raw string, so useSyncExternalStore sees a stable snapshot.
const parsed = new Map<string, CaseEntry>()
function parseCase(raw: string | null): CaseEntry {
  if (!raw) return EMPTY
  let hit = parsed.get(raw)
  if (!hit) {
    try {
      hit = { ...EMPTY, ...JSON.parse(raw) }
    } catch {
      hit = EMPTY
    }
    parsed.set(raw, hit!)
  }
  return hit!
}

export function readCase(id: string): CaseEntry {
  return parseCase(read(CASE(id)))
}

export function writeCase(id: string, patch: Partial<CaseEntry>) {
  const next = { ...readCase(id), ...patch }
  write(CASE(id), JSON.stringify(next))
}

// Without an id (a result shown on its own), the entry lives in component state only.
export function useCase(id: string | undefined): [CaseEntry, (patch: Partial<CaseEntry>) => void] {
  const stored = useSyncExternalStore(
    subscribe,
    () => (id ? readCase(id) : EMPTY),
    () => EMPTY,
  )
  const [local, setLocal] = useState(EMPTY)
  const update = useCallback(
    (patch: Partial<CaseEntry>) => (id ? writeCase(id, patch) : setLocal((e) => ({ ...e, ...patch }))),
    [id],
  )
  return [id ? stored : local, update]
}

// Every case this browser knows about, for the worklist.
export function useCasebook(): (id: string) => CaseEntry {
  const version = useSyncExternalStore(
    subscribe,
    () => {
      try {
        return Object.keys(localStorage)
          .filter((k) => k.startsWith('ssf.case.'))
          .map((k) => `${k}=${localStorage.getItem(k)}`)
          .join('\n')
      } catch {
        return ''
      }
    },
    () => '',
  )
  // A new function whenever any case changes, so lists that read cases re-render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useCallback((id: string) => readCase(id), [version])
}

function parseThreshold(raw: string | null): number {
  const n = Number(raw)
  return raw && Number.isFinite(n) && n >= 1 && n <= 100 ? n : DEFAULT_THRESHOLD
}

// The lab's minimum tumor fraction for sequencing, in percent.
export function useThreshold(): [number, (pct: number) => void] {
  const value = useSyncExternalStore(subscribe, () => parseThreshold(read(THRESHOLD)), () => DEFAULT_THRESHOLD)
  const set = useCallback((pct: number) => {
    if (Number.isFinite(pct) && pct >= 1 && pct <= 100) write(THRESHOLD, String(Math.round(pct)))
  }, [])
  return [value, set]
}

// Percentages are compared as shown (rounded), so a "20%" region never reads as below a 20% minimum.
export const meets = (tumorFraction: number, thresholdPct: number) => Math.round(tumorFraction * 100) >= thresholdPct
