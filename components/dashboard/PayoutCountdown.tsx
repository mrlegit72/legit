'use client'

import { useEffect, useState } from 'react'

function diff(target: Date) {
  const ms = target.getTime() - Date.now()
  const clamp = Math.max(0, ms)
  const days = Math.floor(clamp / 86400000)
  const hours = Math.floor((clamp % 86400000) / 3600000)
  const mins = Math.floor((clamp % 3600000) / 60000)
  const secs = Math.floor((clamp % 60000) / 1000)
  return { days, hours, mins, secs, done: ms <= 0 }
}

export function PayoutCountdown({ date }: { date: string }) {
  const target = new Date(date)
  const [t, setT] = useState(() => diff(target))

  useEffect(() => {
    const id = setInterval(() => setT(diff(target)), 1000)
    return () => clearInterval(id)
  }, [date])

  if (t.done) {
    return <p className="text-xl font-semibold text-emerald-400">Payout releasing now…</p>
  }

  const units = [
    { v: t.days, l: 'Days' },
    { v: t.hours, l: 'Hours' },
    { v: t.mins, l: 'Minutes' },
    { v: t.secs, l: 'Seconds' },
  ]

  return (
    <div className="grid grid-cols-4 gap-3">
      {units.map((u) => (
        <div key={u.l} className="rounded-xl bg-ink-900 border border-ink-700 p-4 text-center">
          <p className="text-2xl sm:text-3xl font-bold gold-text tabular-nums">
            {String(u.v).padStart(2, '0')}
          </p>
          <p className="mt-1 text-xs text-ink-400 uppercase tracking-wide">{u.l}</p>
        </div>
      ))}
    </div>
  )
}
