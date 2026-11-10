import { LucideIcon } from 'lucide-react'

export function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon
  label: string
  value: string
  hint?: string
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-300">{label}</p>
        <span className="h-9 w-9 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center text-gold">
          <Icon size={16} />
        </span>
      </div>
      <p className="mt-3 text-2xl font-bold text-ink-50">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
    </div>
  )
}
