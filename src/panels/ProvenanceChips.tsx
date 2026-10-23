/** Every panel header carries the same channel provenance strip (plan §4). */
export default function ProvenanceChips({ letterItems, letters, requests311, emails, site }: { letterItems: number; letters: number; requests311: number | null; emails: number; site: number }) {
  const chip = (label: string, kind: 'real' | 'simulated' | 'pending') => (
    <span key={label} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${kind === 'real' ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : kind === 'simulated' ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-stone-300 bg-stone-50 text-stone-500'}`}>
      <span aria-hidden>{kind === 'real' ? '●' : kind === 'simulated' ? '◌' : '○'}</span>
      {label}: {kind}
    </span>
  )
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Data provenance">
      {chip(`311${requests311 !== null ? ` (${requests311.toLocaleString()})` : ''}`, requests311 !== null ? 'real' : 'pending')}
      {chip(`Letters (${letterItems} items, ${letters})`, 'real')}
      {chip(`Email${emails ? ` (${emails})` : ''}`, emails ? 'simulated' : 'pending')}
      {chip(`Site${site ? ` (${site})` : ''}`, site ? 'simulated' : 'pending')}
    </div>
  )
}
