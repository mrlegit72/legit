'use client'

import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { QRCodeSVG } from 'qrcode.react'
import {
  X,
  Copy,
  Check,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Bitcoin,
  Coins,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { cn, formatUSDT } from '@/lib/utils'

type Step = 'amount' | 'pay' | 'success' | 'failed'

const CURRENCIES = [
  { code: 'USDT', label: 'Tether', icon: '₮', color: 'text-emerald-400' },
  { code: 'USDC', label: 'USD Coin', icon: 'Ⓤ', color: 'text-blue-400' },
  { code: 'ETH', label: 'Ethereum', icon: 'Ξ', color: 'text-indigo-400' },
  { code: 'BTC', label: 'Bitcoin', icon: '₿', color: 'text-orange-400' },
]

type ChargeData = {
  chargeId: string
  hostedUrl: string
  addresses: Record<string, string>
  pricing: Record<string, { amount: string; currency: string }>
  expiresAt: string
}

export function DepositModal({
  open,
  onClose,
  coinbaseConfigured,
}: {
  open: boolean
  onClose: () => void
  coinbaseConfigured: boolean
}) {
  const [step, setStep] = useState<Step>('amount')
  const [amount, setAmount] = useState('100')
  const [currency, setCurrency] = useState('USDT')
  const [selectedCoin, setSelectedCoin] = useState('USDT')
  const [charge, setCharge] = useState<ChargeData | null>(null)
  const [creating, setCreating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [expiresIn, setExpiresIn] = useState('60:00')

  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setStep('amount')
        setCharge(null)
        setAmount('100')
        setCurrency('USDT')
        setSelectedCoin('USDT')
      }, 200)
    }
  }, [open])

  // Countdown timer
  useEffect(() => {
    if (!charge?.expiresAt) return
    const iv = setInterval(() => {
      const ms = new Date(charge.expiresAt).getTime() - Date.now()
      if (ms <= 0) {
        setExpiresIn('00:00')
        setStep('failed')
        clearInterval(iv)
        return
      }
      const m = Math.floor(ms / 60000)
      const s = Math.floor((ms % 60000) / 1000)
      setExpiresIn(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`)
    }, 1000)
    return () => clearInterval(iv)
  }, [charge])

  // Poll status
  useEffect(() => {
    if (!charge || step !== 'pay') return
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`/api/wallet/charge/${charge.chargeId}`)
        const data = await res.json()
        if (data.status === 'CONFIRMED' || data.status === 'COMPLETED' || data.status === 'RESOLVED') {
          clearInterval(iv)
          setStep('success')
          toast.success('Payment confirmed!')
        } else if (data.status === 'EXPIRED' || data.status === 'CANCELED' || data.status === 'FAILED') {
          clearInterval(iv)
          setStep('failed')
        }
      } catch {
        /* ignore */
      }
    }, 8000)
    return () => clearInterval(iv)
  }, [charge, step])

  async function createCharge() {
    setCreating(true)
    try {
      const res = await fetch('/api/wallet/deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount,
          currency,
          description: `AjoVault wallet top-up`,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed')
      setCharge(data)
      setStep('pay')
    } catch (e: any) {
      toast.error(e.message || 'Could not create charge')
    } finally {
      setCreating(false)
    }
  }

  async function copyAddress() {
    if (!charge) return
    const addr = charge.addresses[selectedCoin.toLowerCase()] || Object.values(charge.addresses)[0]
    try {
      await navigator.clipboard.writeText(addr)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
      toast.success('Address copied')
    } catch {
      toast.error('Could not copy')
    }
  }

  const address = charge
    ? charge.addresses[selectedCoin.toLowerCase()] || Object.values(charge.addresses)[0]
    : ''

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            className="relative w-full max-w-lg bg-ink-800 border border-ink-700 rounded-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700">
              <h3 className="font-semibold text-ink-50">
                {step === 'amount' && 'Deposit crypto'}
                {step === 'pay' && 'Send payment'}
                {step === 'success' && 'Payment received'}
                {step === 'failed' && 'Payment failed'}
              </h3>
              <button onClick={onClose} className="text-ink-400 hover:text-ink-100 p-1">
                <X size={18} />
              </button>
            </div>

            {/* Step: Amount */}
            {step === 'amount' && (
              <div className="p-6 space-y-5">
                <div>
                  <label className="label">Amount</label>
                  <div className="relative">
                    <input
                      type="number"
                      min="1"
                      step="0.01"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="input pr-24 text-xl font-semibold"
                    />
                    <select
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-ink-700 border border-ink-600 rounded-lg text-sm px-2 py-1.5"
                    >
                      <option>USD</option>
                      <option>USDT</option>
                      <option>NGN</option>
                      <option>GHS</option>
                    </select>
                  </div>
                  <p className="mt-2 text-xs text-ink-400">
                    You&apos;ll be able to pay in USDT, USDC, ETH, or BTC on the next screen.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {['50', '100', '250', '500'].map((a) => (
                    <button
                      key={a}
                      type="button"
                      onClick={() => setAmount(a)}
                      className="rounded-xl border border-ink-700 bg-ink-900 py-2 text-sm text-ink-200 hover:border-gold/40"
                    >
                      {a} {currency}
                    </button>
                  ))}
                </div>

                {!coinbaseConfigured && (
                  <div className="rounded-xl border border-gold/20 bg-gold/5 p-3 text-xs text-ink-300">
                    Demo mode: a simulated charge will be created. To enable real deposits, add
                    your Coinbase Commerce API key.
                  </div>
                )}

                <button onClick={createCharge} disabled={creating} className="btn-gold w-full">
                  {creating ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Creating charge…
                    </>
                  ) : (
                    'Continue'
                  )}
                </button>
              </div>
            )}

            {/* Step: Pay */}
            {step === 'pay' && charge && (
              <div className="p-6 space-y-5">
                <div className="grid grid-cols-4 gap-2">
                  {CURRENCIES.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => setSelectedCoin(c.code)}
                      className={cn(
                        'flex flex-col items-center gap-1 rounded-xl border py-3 text-xs',
                        selectedCoin === c.code
                          ? 'border-gold bg-gold/10'
                          : 'border-ink-700 bg-ink-900 hover:border-gold/40'
                      )}
                    >
                      <span className={cn('text-xl font-bold', c.color)}>{c.icon}</span>
                      <span className="text-ink-200">{c.code}</span>
                    </button>
                  ))}
                </div>

                <div className="flex justify-center">
                  <div className="rounded-xl bg-white p-3">
                    <QRCodeSVG value={address} size={180} level="M" includeMargin={false} />
                  </div>
                </div>

                <div>
                  <p className="text-xs text-ink-400 mb-1">
                    Send {selectedCoin} to this address
                  </p>
                  <button
                    onClick={copyAddress}
                    className="w-full flex items-center justify-between gap-2 rounded-xl border border-ink-700 bg-ink-900 px-3 py-3 text-sm text-ink-100 hover:border-gold/40"
                  >
                    <span className="font-mono text-xs truncate">{address}</span>
                    {copied ? (
                      <Check size={16} className="text-emerald-400 flex-shrink-0" />
                    ) : (
                      <Copy size={16} className="flex-shrink-0" />
                    )}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl border border-ink-700 bg-ink-900 p-3">
                    <p className="text-xs text-ink-400">Amount due</p>
                    <p className="font-semibold text-ink-50">
                      {formatUSDT(Number(amount))} {currency}
                    </p>
                  </div>
                  <div className="rounded-xl border border-ink-700 bg-ink-900 p-3">
                    <p className="text-xs text-ink-400 flex items-center gap-1">
                      <Clock size={12} /> Expires in
                    </p>
                    <p className="font-semibold gold-text tabular-nums">{expiresIn}</p>
                  </div>
                </div>

                <div className="flex items-center justify-center gap-2 text-sm text-ink-300">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gold opacity-75" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-gold" />
                  </span>
                  Waiting for payment…
                </div>

                <a
                  href={charge.hostedUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-center text-xs text-gold hover:underline"
                >
                  Or pay via Coinbase hosted checkout →
                </a>
              </div>
            )}

            {/* Step: Success */}
            {step === 'success' && (
              <div className="p-10 text-center">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', duration: 0.6 }}
                  className="mx-auto h-20 w-20 rounded-full bg-emerald-500/10 border-2 border-emerald-500 flex items-center justify-center text-emerald-400"
                >
                  <CheckCircle2 size={40} />
                </motion.div>
                <h3 className="mt-5 text-xl font-bold text-ink-50">Payment confirmed!</h3>
                <p className="mt-2 text-ink-300">
                  Your balance has been updated. You can now join groups and contribute.
                </p>
                <button onClick={onClose} className="btn-gold mt-6 w-full">
                  Done
                </button>
              </div>
            )}

            {/* Step: Failed */}
            {step === 'failed' && (
              <div className="p-10 text-center">
                <div className="mx-auto h-20 w-20 rounded-full bg-red-500/10 border-2 border-red-500 flex items-center justify-center text-red-400">
                  <XCircle size={40} />
                </div>
                <h3 className="mt-5 text-xl font-bold text-ink-50">Payment failed or expired</h3>
                <p className="mt-2 text-ink-300">
                  Don&apos;t worry — nothing was charged. Start a new deposit when you&apos;re ready.
                </p>
                <div className="mt-6 flex gap-2">
                  <button
                    onClick={() => {
                      setCharge(null)
                      setStep('amount')
                    }}
                    className="btn-gold flex-1"
                  >
                    Try again
                  </button>
                  <button onClick={onClose} className="btn-ghost flex-1">
                    Close
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
