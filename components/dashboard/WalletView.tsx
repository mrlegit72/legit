'use client'

import { useState } from 'react'
import { ArrowDownToLine, ArrowUpToLine, Wallet, Info } from 'lucide-react'
import toast from 'react-hot-toast'
import { formatUSDT, formatDateTime } from '@/lib/utils'
import { DepositModal } from '@/components/wallet/DepositModal'
import { cn } from '@/lib/utils'

type Tx = {
  id: string
  type: string
  amount: number
  currency: string
  status: string
  description: string | null
  createdAt: string
}

export function WalletView({
  balance,
  transactions,
  coinbaseConfigured,
}: {
  balance: number
  transactions: Tx[]
  coinbaseConfigured: boolean
}) {
  const [depositOpen, setDepositOpen] = useState(false)
  const [withdrawForm, setWithdrawForm] = useState({
    bankName: '',
    accountNumber: '',
    accountName: '',
    amount: '',
  })
  const [withdrawing, setWithdrawing] = useState(false)

  async function submitWithdraw(e: React.FormEvent) {
    e.preventDefault()
    setWithdrawing(true)
    try {
      const res = await fetch('/api/wallet/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...withdrawForm,
          amount: Number(withdrawForm.amount),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed')
      toast.success('Withdrawal request submitted')
      setWithdrawForm({ bankName: '', accountNumber: '', accountName: '', amount: '' })
    } catch (e: any) {
      toast.error(e.message || 'Withdrawal failed')
    } finally {
      setWithdrawing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Wallet</h1>
        <p className="mt-1 text-ink-300">Deposit USDT, withdraw to your bank, review activity.</p>
      </div>

      {!coinbaseConfigured && (
        <div className="rounded-xl border border-gold/30 bg-gold/5 p-4 flex items-start gap-3 text-sm">
          <Info size={18} className="text-gold mt-0.5" />
          <div>
            <p className="text-ink-100 font-medium">Coinbase Commerce is not configured</p>
            <p className="text-ink-300 mt-1">
              Add <code className="text-gold">COINBASE_COMMERCE_API_KEY</code> to{' '}
              <code className="text-gold">.env.local</code> to enable real crypto deposits.
              The deposit modal still works in demo mode.
            </p>
          </div>
        </div>
      )}

      {/* Balance card */}
      <div className="relative overflow-hidden rounded-2xl border border-gold/30 bg-gradient-to-br from-gold/20 via-ink-800 to-ink-900 p-8">
        <div className="absolute -top-20 -right-20 h-64 w-64 rounded-full bg-gold/20 blur-3xl" />
        <div className="relative flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-sm text-ink-200 flex items-center gap-2">
              <Wallet size={14} /> Available balance
            </p>
            <p className="mt-2 text-5xl font-bold gold-text tabular-nums">
              {formatUSDT(balance)}
            </p>
            <p className="mt-1 text-sm text-ink-200">USDT</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setDepositOpen(true)} className="btn-gold">
              <ArrowDownToLine size={16} /> Deposit USDT
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Withdraw */}
        <form onSubmit={submitWithdraw} className="card p-6 space-y-4">
          <div className="flex items-center gap-2 text-ink-50">
            <ArrowUpToLine size={18} className="text-gold" />
            <h3 className="font-semibold">Withdraw to bank</h3>
          </div>
          <p className="text-sm text-ink-300">
            Cash out your USDT in Naira or Cedi via our licensed off-ramp partners.
          </p>
          <div>
            <label className="label">Bank name</label>
            <input
              required
              value={withdrawForm.bankName}
              onChange={(e) => setWithdrawForm({ ...withdrawForm, bankName: e.target.value })}
              placeholder="GTBank"
              className="input"
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Account number</label>
              <input
                required
                value={withdrawForm.accountNumber}
                onChange={(e) =>
                  setWithdrawForm({ ...withdrawForm, accountNumber: e.target.value })
                }
                placeholder="0123456789"
                className="input"
              />
            </div>
            <div>
              <label className="label">Account name</label>
              <input
                required
                value={withdrawForm.accountName}
                onChange={(e) =>
                  setWithdrawForm({ ...withdrawForm, accountName: e.target.value })
                }
                placeholder="As shown on your statement"
                className="input"
              />
            </div>
          </div>
          <div>
            <label className="label">Amount (USDT)</label>
            <input
              required
              type="number"
              min="1"
              step="0.01"
              max={balance}
              value={withdrawForm.amount}
              onChange={(e) => setWithdrawForm({ ...withdrawForm, amount: e.target.value })}
              placeholder="0.00"
              className="input"
            />
            <p className="mt-1 text-xs text-ink-400">
              Max: {formatUSDT(balance)} USDT
            </p>
          </div>
          <button type="submit" disabled={withdrawing || balance <= 0} className="btn-gold w-full">
            {withdrawing ? 'Submitting…' : 'Submit withdrawal'}
          </button>
        </form>

        {/* Recent activity */}
        <div className="card overflow-hidden">
          <div className="p-6 border-b border-ink-700">
            <h3 className="font-semibold text-ink-50">Recent activity</h3>
            <p className="text-sm text-ink-300">Last 30 wallet transactions</p>
          </div>
          {transactions.length === 0 ? (
            <p className="p-6 text-sm text-ink-400">No transactions yet.</p>
          ) : (
            <div className="max-h-[420px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-ink-400 bg-ink-900 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">Date</th>
                    <th className="text-left px-4 py-2 font-medium">Type</th>
                    <th className="text-left px-4 py-2 font-medium">Amount</th>
                    <th className="text-left px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((t) => (
                    <tr key={t.id} className="border-b border-ink-700/60">
                      <td className="px-4 py-2.5 text-ink-400 whitespace-nowrap">
                        {formatDateTime(t.createdAt)}
                      </td>
                      <td className="px-4 py-2.5 capitalize text-ink-100">{t.type}</td>
                      <td
                        className={cn(
                          'px-4 py-2.5 font-medium whitespace-nowrap',
                          t.type === 'payout' || t.type === 'deposit'
                            ? 'text-emerald-400'
                            : 'text-ink-100'
                        )}
                      >
                        {t.type === 'payout' || t.type === 'deposit' ? '+' : '-'}
                        {formatUSDT(t.amount)}
                      </td>
                      <td className="px-4 py-2.5">
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
      </div>

      <DepositModal
        open={depositOpen}
        onClose={() => setDepositOpen(false)}
        coinbaseConfigured={coinbaseConfigured}
      />
    </div>
  )
}
