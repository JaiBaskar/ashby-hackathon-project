'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import Logo from './Logo'
import ShortcutSheet from './ShortcutSheet'

const NAV = [
  { href: '/', label: 'Worklist', match: (p: string) => p === '/' || p.startsWith('/jobs') },
  { href: '/upload', label: 'New case', match: (p: string) => p.startsWith('/upload') },
]

// The dark band across the top, in the same "scope" colors as the slide stage.
export default function SiteHeader() {
  const path = usePathname() ?? '/'
  return (
    <header className="on-stage bg-stage text-stage-ink print:hidden">
      <div className="mx-auto flex h-14 max-w-[90rem] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3 rounded-sm">
          <Logo className="h-4 w-10" />
          <span className="sr-only sm:not-sr-only sm:text-base sm:font-semibold sm:tracking-tight sm:whitespace-nowrap">
            Hotspot
            <span className="ml-2 hidden font-mono text-xs font-normal text-stage-muted sm:inline">research</span>
          </span>
        </Link>
        <nav aria-label="Main" className="ml-auto flex items-center gap-1 whitespace-nowrap">
          {NAV.map((n) => {
            const current = n.match(path)
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={current ? 'page' : undefined}
                className={`relative inline-flex min-h-11 items-center rounded-sm px-3 text-sm font-medium transition-colors duration-fast ${
                  current ? 'text-stage-ink' : 'text-stage-muted hover:text-stage-ink'
                }`}
              >
                {n.label}
                {current && <span aria-hidden className="absolute inset-x-3 bottom-1.5 h-0.5 rounded-full bg-eosin" />}
              </Link>
            )
          })}
          <span className="ml-2">
            <ShortcutSheet />
          </span>
        </nav>
      </div>
    </header>
  )
}
