import UploadForm from '@/components/UploadForm'

export const metadata = { title: 'New case · Hotspot' }

export default function UploadPage() {
  return (
    <main className="mx-auto max-w-[90rem] animate-enter px-4 py-8 sm:px-6">
      <h1 className="text-xl font-semibold tracking-tight">New case</h1>
      <p className="mt-1 text-ink-muted">One slide or a whole batch. You can label each one now or later.</p>
      <div className="mt-6">
        <UploadForm />
      </div>
    </main>
  )
}
