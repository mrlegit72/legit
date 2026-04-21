'use client'

import { useMemo, useState } from 'react'
import { Download, Filter, Receipt } from 'lucide-react'
import { cn, formatDateTime, formatUSDT } from '@/lib/utils'

type Tx = {
  id: string
  type: string
  amount: number
  currency: string
  status: string
  description: string | null
  createdAt: string
}

const TYPES = ['all', 'deposit', 'contribution', 'payout', 'withdrawal']
const STATUSES = ['all', 'completed', 'pending', 'failed']

export function TransactionsView({ transactions }: { transactions: Tx[] }) {
  const [type, setType] = useState('all')
  const [status, setStatus] = useState('all')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const filtered = useMemo(() => {
    return transactions.filter((t) => {
      if (type !== 'all' && t.type !== type) return false
      if (status !== 'all' && t.status !== status) return false
      const d = new Date(t.createdAt)
      if (from && d < new Date(from)) return false
      if (to && d > new Date(to + 'T23:59:59')) return false
      return true
    })
  }, [transactions, type, status, from, to])

  function exportCsv() {
    const header = ['Date', 'Type', 'Description', 'Amount', 'Currency', 'Status']
    const rows = filtered.map((t) => [
      new Date(t.createdAt).toISOString(),
      t.type,
      (t.description || '').replace(/"/g, "'"),
      t.amount.toString(),
      t.currency,
      t.status,
    ])
    const csv =
      [header, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `ajovault-transactions-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="card overflow-hidden">
      <div className="p-4 sm:p-6 border-b border-ink-700 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-ink-200 mr-2">
          <Filter size={14} /> Filters
        </div>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="input max-w-[160px] text-sm py-2"
        >
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All types' : t}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="input max-w-[160px] text-sm py-2"
        >
          {STATUSES.map((t) => (
            <option key={t} value={t}>
              {t === 'all' ? 'All statuses' : t}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          className="input max-w-[170px] text-sm py-2"
          placeholder="From"
        />
        <input
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="input max-w-[170px] text-sm py-2"
          placeholder="To"
        />
        <button onClick={exportCsv} className="btn-dark ml-auto text-sm">
          <Download size={14} /> Export CSV
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="p-12 text-center">
          <Receipt size={40} className="mx-auto text-ink-500" />
          <p className="mt-3 font-medium text-ink-100">No transactions match your filters</p>
          <p className="mt-1 text-sm text-ink-400">Try adjusting the filters above.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-ink-400 bg-ink-900">
              <tr>
                <th className="text-left px-6 py-3 font-medium">Date</th>
                <th className="text-left px-6 py-3 font-medium">Type</th>
                <th className="text-left px-6 py-3 font-medium">Description</th>
                <th className="text-left px-6 py-3 font-medium">Amount</th>
                <th className="text-left px-6 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-ink-700/60 hover:bg-ink-800/40"
                >
                  <td className="px-6 py-3 text-ink-300 whitespace-nowrap">
                    {formatDateTime(t.createdAt)}
                  </td>
                  <td className="px-6 py-3 capitalize text-ink-100">{t.type}</td>
                  <td className="px-6 py-3 text-ink-200">{t.description}</td>
                  <td
                    className={cn(
                      'px-6 py-3 font-medium whitespace-nowrap',
                      t.type === 'payout' || t.type === 'deposit'
                        ? 'text-emerald-400'
                        : 'text-ink-100'
                    )}
                  >
                    {t.type === 'payout' || t.type === 'deposit' ? '+' : '-'}
                    {formatUSDT(t.amount)} {t.currency}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={cn(
                        t.status === 'completed' && 'badge-active',
                        t.status === 'pending' && 'badge-pending',
                        t.status === 'failed' && 'badge-failed'
                      )}
                    >
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
