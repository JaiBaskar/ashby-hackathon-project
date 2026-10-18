import { redirect } from 'next/navigation'

// The history list became the worklist on the home page; old links still land there.
export default function HistoryPage() {
  redirect('/')
}
