import Link from 'next/link'
import { button, ResearchNotice } from '@/components/ui'

const HOW = [
  ['Upload', 'A phone photo or a scanned slide: PNG, JPEG, TIFF or SVS.'],
  ['Analyze', 'The image is cut into tiles, and each tile is scored for six tissue types.'],
  ['Choose', 'Five non-overlapping regions, ranked, each with its tissue mix and the reasons it was picked.'],
]

export default function Home() {
  return (
    <main className="mx-auto grid max-w-6xl animate-enter gap-12 px-4 py-14 sm:px-6 sm:py-24 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-20">
      <section>
        <p className="text-sm font-semibold tracking-wide text-accent-strong">Biopsy sampling-site finder</p>
        <h1 className="mt-4 font-display text-xl font-normal text-balance sm:text-display">
          Find the best place to sample on a biopsy slide.
        </h1>
        <p className="mt-5 max-w-prose text-lg text-ink-muted">
          Upload a photo or scan of an H&amp;E slide, and get the five regions with the most tumor to sample.
        </p>
        <div className="mt-9">
          <Link href="/upload" className={button.primary}>
            Analyze a slide
          </Link>
        </div>
        <div className="mt-10">
          <ResearchNotice />
        </div>
      </section>

      <section aria-labelledby="how" className="lg:pt-10">
        <h2 id="how" className="text-sm font-semibold tracking-wide text-ink-muted">
          How it works
        </h2>
        <ol className="mt-4 border-t border-line">
          {HOW.map(([title, text], i) => (
            <li key={title} className="grid grid-cols-[2rem_1fr] gap-x-3 border-b border-line py-5">
              <span className="font-display text-lg text-accent-strong tabular-nums">{i + 1}</span>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-1 text-ink-muted">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  )
}
