import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'project',
  description: 'Suggests the best regions to sample on an H&E biopsy slide. Research prototype.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
