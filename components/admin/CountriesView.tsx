'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Loader2 } from 'lucide-react'
import { cn, formatUSDT } from '@/lib/utils'

type Row = {
  code: string
  name: string
  flag: string
  currency: string
  currencySymbol: string
  enabled: boolean
  preferredProviderId: string | null
  platformFeePct: number
  volume30d: number
  users: number
}

const PROVIDERS = [
  { id: '', label: 'Auto (router picks)' },
  { id: 'bitnob', label: 'Bitnob' },
  { id: 'transak', label: 'Transak' },
  { id: 'demo', label: 'Demo' },
]

export function CountriesView() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [savingCode, setSavingCode] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    const res = await fetch('/api/admin/countries')
    const data = await res.json()
    setRows(data.countries || [])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  async function update(row: Row, patch: Partial<Row>) {
    setSavingCode(row.code)
    try {
      const res = await fetch('/api/admin/countries', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          countryCode: row.code,
          enabled: patch.enabled,
          preferredProviderId: patch.preferredProviderId,
          platformFeePct: patch.platformFeePct,
        }),
      })
      if (!res.ok) throw new Error()
      setRows((prev) => prev.map((r) => (r.code === row.code ? { ...r, ...patch } : r)))
      toast.success(`${row.flag} ${row.name} updated`)
    } catch {
      toast.error('Save failed')
    } finally {
      setSavingCode(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Countries</h1>
        <p className="mt-1 text-ink-300">
          Toggle countries, pin a preferred provider, and set per-country platform fees.
        </p>
      </div>

      {loading ? (
        <div className="card p-10 text-center text-ink-400">
          <Loader2 size={20} className="animate-spin mx-auto mb-2" />
          Loading countries…
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-ink-400 bg-ink-900">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Country</th>
                  <th className="text-left px-4 py-3 font-medium">Currency</th>
                  <th className="text-left px-4 py-3 font-medium">Enabled</th>
                  <th className="text-left px-4 py-3 font-medium">Preferred provider</th>
                  <th className="text-left px-4 py-3 font-medium">Platform fee %</th>
                  <th className="text-left px-4 py-3 font-medium">30d volume</th>
                  <th className="text-left px-4 py-3 font-medium">Users</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code} className="border-b border-ink-700/60">
                    <td className="px-4 py-3 text-ink-100">
                      <span className="text-xl mr-2">{r.flag}</span>
                      {r.name}
                    </td>
                    <td className="px-4 py-3 text-ink-200 font-mono text-xs">{r.currency}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => update(r, { enabled: !r.enabled })}
                        disabled={savingCode === r.code}
                        className={cn(
                          'relative h-5 w-9 rounded-full transition',
                          r.enabled ? 'bg-gold' : 'bg-ink-700'
                        )}
                      >
                        <span
                          className={cn(
                            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition',
                            r.enabled ? 'left-4.5' : 'left-0.5'
                          )}
                          style={r.enabled ? { left: 18 } : { left: 2 }}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={r.preferredProviderId || ''}
                        onChange={(e) => update(r, { preferredProviderId: e.target.value || null })}
                        disabled={savingCode === r.code}
                        className="input text-xs py-1 max-w-[140px]"
                      >
                        {PROVIDERS.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        step="0.1"
                        defaultValue={r.platformFeePct}
                        onBlur={(e) => {
                          const v = Number(e.target.value)
                          if (!isNaN(v) && v !== r.platformFeePct) update(r, { platformFeePct: v })
                        }}
                        className="input text-xs py-1 max-w-[80px]"
                      />
                    </td>
                    <td className="px-4 py-3 text-ink-100 gold-text font-medium">
                      {formatUSDT(r.volume30d)}
                    </td>
                    <td className="px-4 py-3 text-ink-200">{r.users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
