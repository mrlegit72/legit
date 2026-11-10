'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Check, Loader2, Send, X } from 'lucide-react'
import { cn, formatUSDT } from '@/lib/utils'

type Row = {
  id: string
  userId: string
  userName: string
  userEmail: string
  userCountry: string
  userBalance: number
  amlFlagCount: number
  amount: number
  currency: string
  bankName: string
  accountNumber: string
  accountName: string
  status: string
  rejectionReason: string | null
  reviewedAt: string | null
  createdAt: string
}

export function WithdrawalsView() {
  const [list, setList] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<'pending' | 'all'>('pending')

  async function load() {
    setLoading(true)
    const res = await fetch(`/api/admin/withdrawals${status === 'all' ? '' : '?status=pending'}`)
    const data = await res.json()
    setList(data.withdrawals || [])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [status])

  async function act(row: Row, action: 'approve' | 'reject' | 'complete', reason?: string) {
    try {
      const res = await fetch('/api/admin/withdrawals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ withdrawalId: row.id, action, reason }),
      })
      if (!res.ok) throw new Error()
      toast.success(`${action}d`)
      load()
    } catch {
      toast.error('Failed')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Withdrawals</h1>
        <p className="mt-1 text-ink-300">Human-review queue for payouts to user bank accounts.</p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setStatus('pending')}
          className={cn(
            'rounded-xl border px-3 py-1.5 text-sm',
            status === 'pending'
              ? 'border-gold bg-gold/10 text-gold'
              : 'border-ink-700 bg-ink-900 text-ink-300'
          )}
        >
          Pending
        </button>
        <button
          onClick={() => setStatus('all')}
          className={cn(
            'rounded-xl border px-3 py-1.5 text-sm',
            status === 'all'
              ? 'border-gold bg-gold/10 text-gold'
              : 'border-ink-700 bg-ink-900 text-ink-300'
          )}
        >
          All
        </button>
      </div>

      {loading ? (
        <div className="card p-10 text-center text-ink-400">
          <Loader2 size={20} className="animate-spin mx-auto mb-2" />
          Loading…
        </div>
      ) : list.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-ink-100 font-medium">No withdrawals in queue</p>
          <p className="text-sm text-ink-400 mt-1">All caught up.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {list.map((w) => (
            <div key={w.id} className="card p-5">
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                  <p className="font-semibold text-ink-50">
                    {w.userName} ·{' '}
                    <span className="text-ink-300 text-sm font-normal">{w.userCountry}</span>
                  </p>
                  <p className="text-xs text-ink-400">
                    {w.userEmail} · wallet {formatUSDT(w.userBalance)} USDT
                  </p>
                  {w.amlFlagCount > 0 && (
                    <p className="mt-1 text-xs text-red-400">
                      ⚠ {w.amlFlagCount} unresolved AML flag(s)
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-xl font-bold gold-text">
                    {formatUSDT(w.amount)} {w.currency}
                  </p>
                  <span
                    className={cn(
                      'mt-1',
                      w.status === 'pending' && 'badge-pending',
                      w.status === 'approved' && 'badge-active',
                      w.status === 'completed' && 'badge-active',
                      w.status === 'rejected' && 'badge-failed'
                    )}
                  >
                    {w.status}
                  </span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-xs text-ink-400">Bank</p>
                  <p className="text-ink-100">{w.bankName}</p>
                </div>
                <div>
                  <p className="text-xs text-ink-400">Account number</p>
                  <p className="text-ink-100 font-mono text-xs">{w.accountNumber}</p>
                </div>
                <div>
                  <p className="text-xs text-ink-400">Account name</p>
                  <p className="text-ink-100">{w.accountName}</p>
                </div>
              </div>

              {w.rejectionReason && (
                <p className="mt-3 text-xs text-red-300 italic">Rejected: {w.rejectionReason}</p>
              )}

              {w.status === 'pending' && (
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => act(w, 'approve')}
                    className="btn-gold text-sm flex-1"
                  >
                    <Check size={14} /> Approve
                  </button>
                  <button
                    onClick={() => {
                      const r = prompt('Reason for rejection?')
                      if (r != null) act(w, 'reject', r)
                    }}
                    className="btn-ghost text-sm flex-1"
                  >
                    <X size={14} /> Reject
                  </button>
                </div>
              )}

              {w.status === 'approved' && (
                <div className="mt-4 flex gap-2">
                  <button onClick={() => act(w, 'complete')} className="btn-gold text-sm flex-1">
                    <Send size={14} /> Mark as paid out
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
