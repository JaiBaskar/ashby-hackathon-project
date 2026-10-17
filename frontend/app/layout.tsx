import type { Metadata } from 'next'
import localFont from 'next/font/local'
import Link from 'next/link'
import './globals.css'

// Fonts ship with the @fontsource packages, so builds and tests need no internet (DESIGN.md, "Type").
const newsreader = localFont({
  src: [
    { path: '../node_modules/@fontsource-variable/newsreader/files/newsreader-latin-wght-normal.woff2', style: 'normal' },
    { path: '../node_modules/@fontsource-variable/newsreader/files/newsreader-latin-wght-italic.woff2', style: 'italic' },
  ],
  weight: '200 800',
  display: 'swap',
  variable: '--font-newsreader',
})

const plex = localFont({
  src: [
    { path: '../node_modules/@fontsource-variable/ibm-plex-sans/files/ibm-plex-sans-latin-wght-normal.woff2', style: 'normal' },
    { path: '../node_modules/@fontsource-variable/ibm-plex-sans/files/ibm-plex-sans-latin-wght-italic.woff2', style: 'italic' },
  ],
  weight: '100 700',
  display: 'swap',
  variable: '--font-plex',
})

export const metadata: Metadata = {
  title: 'Sampling-site finder',
  description: 'Suggests the best regions to sample on an H&E biopsy slide. Research prototype.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${newsreader.variable} ${plex.variable}`}>
      <body className="min-h-dvh">
        <header className="border-b border-line">
          <div className="mx-auto flex h-14 max-w-6xl items-center px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 rounded-sm font-display text-lg font-medium text-ink">
              <span aria-hidden className="size-3 rounded-full border-2 border-accent-strong" />
              Sampling-site finder
            </Link>
          </div>
        </header>
        {children}
      </body>
    </html>
  )
}
