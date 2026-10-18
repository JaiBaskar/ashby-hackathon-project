// A glass slide seen from above: the frosted label end in eosin, a section of tissue on the glass,
// and one marker-ink box around the part worth sampling.
export default function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 16" aria-hidden className={className}>
      <rect x="0.75" y="0.75" width="38.5" height="14.5" rx="1.5" className="fill-stage-raised stroke-stage-muted" strokeWidth="1" />
      <rect x="1.5" y="1.5" width="10" height="13" rx="0.75" className="fill-eosin" />
      <path d="M17 9.5c0-3 2.4-5.2 5.6-5.2 2.6 0 3.4 1.6 5.6 1.6 2.4 0 4.3 1.3 4.3 3.4 0 2.6-2.6 3.6-5.2 3.6-2 0-2.9-.9-4.9-.9-2.6 0-5.4.2-5.4-2.5Z" className="fill-class-stroma" />
      <circle cx="23.5" cy="8.5" r="2.4" className="fill-class-tumor" />
      <rect x="20.2" y="5.2" width="6.6" height="6.6" className="fill-none stroke-box-best" strokeWidth="1.1" />
    </svg>
  )
}
