import UploadForm from '@/components/UploadForm'

export const metadata = { title: 'Analyze a slide · Sampling-site finder' }

export default function UploadPage() {
  return (
    <main className="mx-auto max-w-3xl animate-enter px-4 py-10 sm:px-6 sm:py-16">
      <h1 className="font-display text-xl font-normal">Analyze a slide</h1>
      <p className="mt-2 text-ink-muted">One image at a time. It&apos;s deleted from the server once the analysis ends.</p>
      <div className="mt-8">
        <UploadForm />
      </div>
    </main>
  )
}
