import type { Metadata } from 'next'
import localFont from 'next/font/local'
import SiteHeader from '@/components/SiteHeader'
import './globals.css'

// Fonts ship with the @fontsource packages, so builds and tests need no internet (DESIGN.md, "Type").
const instrument = localFont({
  src: [
    { path: '../node_modules/@fontsource-variable/instrument-sans/files/instrument-sans-latin-wght-normal.woff2', style: 'normal' },
    { path: '../node_modules/@fontsource-variable/instrument-sans/files/instrument-sans-latin-wght-italic.woff2', style: 'italic' },
  ],
  weight: '400 700',
  display: 'swap',
  variable: '--font-instrument',
})

const plexMono = localFont({
  src: [
    { path: '../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2', weight: '400' },
    { path: '../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2', weight: '500' },
    { path: '../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-600-normal.woff2', weight: '600' },
  ],
  display: 'swap',
  variable: '--font-plex-mono',
})

export const metadata: Metadata = {
  title: 'Sampling-site finder',
  description: 'Suggests the best regions to sample on an H&E biopsy slide. Research prototype.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${instrument.variable} ${plexMono.variable}`}>
      <body className="min-h-dvh">
        <SiteHeader />
        {children}
      </body>
    </html>
  )
}
