'use client'

import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  X,
  Copy,
  Check,
  Loader2,
  CheckCircle2,
  Clock,
  ArrowRight,
  Banknote,
  Globe,
  Sparkles,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { cn, formatUSDT } from '@/lib/utils'

type CountryCode = string

type CountryOption = {
  code: CountryCode
  name: string
  flag: string
  currency: string
  currencySymbol: string
}

const COUNTRIES: CountryOption[] = [
  { code: 'NG', name: 'Nigeria', flag: '🇳🇬', currency: 'NGN', currencySymbol: '₦' },
  { code: 'GH', name: 'Ghana', flag: '🇬🇭', currency: 'GHS', currencySymbol: '₵' },
  { code: 'KE', name: 'Kenya', flag: '🇰🇪', currency: 'KES', currencySymbol: 'KSh' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦', currency: 'ZAR', currencySymbol: 'R' },
  { code: 'PH', name: 'Philippines', flag: '🇵🇭', currency: 'PHP', currencySymbol: '₱' },
  { code: 'IN', name: 'India', flag: '🇮🇳', currency: 'INR', currencySymbol: '₹' },
  { code: 'ID', name: 'Indonesia', flag: '🇮🇩', currency: 'IDR', currencySymbol: 'Rp' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽', currency: 'MXN', currencySymbol: '$' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷', currency: 'BRL', currencySymbol: 'R$' },
  { code: 'US', name: 'United States', flag: '🇺🇸', currency: 'USD', currencySymbol: '$' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', currency: 'GBP', currencySymbol: '£' },
  { code: 'EU', name: 'Europe', flag: '🇪🇺', currency: 'EUR', currencySymbol: '€' },
]

type Quote = {
  provider: string
  providerName: string
  fromCurrency: string
  fromAmount: number
  toAmount: number
  rate: number
  fee: number
  total: number
}

type Step = 'form' | 'quote' | 'instructions' | 'pending' | 'confirmed'

type OnRampResult = {
  externalId: string
  provider: string
  providerId: string
  hostedUrl?: string
  bankInstructions?: {
    bankName: string
    accountNumber: string
    accountName: string
    reference: string
    narration?: string
  }
  quote: Quote
}

export function FiatDepositModal({
  open,
  onClose,
  userCountry,
}: {
  open: boolean
  onClose: () => void
  userCountry: string
}) {
  const defaultCountry =
    COUNTRIES.find((c) => c.name === userCountry) || COUNTRIES[0]

  const [step, setStep] = useState<Step>('form')
  const [country, setCountry] = useState<CountryOption>(defaultCountry)
  const [amount, setAmount] = useState('10000')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [providerMeta, setProviderMeta] = useState<{
    name: string
    isConfigured: boolean
  } | null>(null)
  const [onRamp, setOnRamp] = useState<OnRampResult | null>(null)
  const [creating, setCreating] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setStep('form')
        setQuote(null)
        setOnRamp(null)
      }, 200)
    }
  }, [open])

  // Live-quote debounce
  useEffect(() => {
    if (step !== 'form') return
    const n = Number(amount)
    if (!n || n <= 0) {
      setQuote(null)
      return
    }
    const h = setTimeout(async () => {
      setQuoteLoading(true)
      try {
        const res = await fetch('/api/ramp/quote', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            country: country.code,
            currency: country.currency,
            amount: n,
          }),
        })
        const data = await res.json()
        if (res.ok) {
          setQuote(data.quote)
          setProviderMeta(data.provider)
        }
      } catch {
        /* ignore */
      } finally {
        setQuoteLoading(false)
      }
    }, 350)
    return () => clearTimeout(h)
  }, [country, amount, step])

  async function createOnRamp() {
    if (!quote) return
    setCreating(true)
    try {
      const res = await fetch('/api/ramp/onramp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country: country.code,
          currency: country.currency,
          amount: Number(amount),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed')
      setOnRamp(data)
      if (data.hostedUrl && data.hostedUrl !== '#') {
        // Redirect-based provider (Transak) — open hosted widget in a new tab.
        window.open(data.hostedUrl, '_blank', 'noopener')
        setStep('pending')
      } else if (data.bankInstructions) {
        setStep('instructions')
      } else {
        setStep('pending')
      }
    } catch (e: any) {
      toast.error(e.message || 'Could not start deposit')
    } finally {
      setCreating(false)
    }
  }

  const amountN = Number(amount) || 0
  const perUSD = quote ? quote.rate : null

  function copyRef() {
    if (!onRamp?.bankInstructions) return
    navigator.clipboard.writeText(onRamp.bankInstructions.reference).then(() => {
      setCopied(true)
      toast.success('Reference copied')
      setTimeout(() => setCopied(false), 1500)
    })
  }

  function markAsPaid() {
    // Demo helper: skip to the pending screen (webhook would normally confirm).
    setStep('pending')
    toast.success('Payment acknowledged. Awaiting partner confirmation…')
  }

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
              <div className="flex items-center gap-2">
                <Globe size={18} className="text-gold" />
                <h3 className="font-semibold text-ink-50">
                  {step === 'form' && 'Deposit local currency'}
                  {step === 'instructions' && 'Transfer & we take it from here'}
                  {step === 'pending' && 'Waiting for your bank'}
                  {step === 'confirmed' && 'Deposit confirmed'}
                </h3>
              </div>
              <button onClick={onClose} className="text-ink-400 hover:text-ink-100 p-1">
                <X size={18} />
              </button>
            </div>

            {step === 'form' && (
              <div className="p-6 space-y-5">
                <div>
                  <label className="label">Country</label>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {COUNTRIES.slice(0, 8).map((c) => (
                      <button
                        key={c.code}
                        type="button"
                        onClick={() => setCountry(c)}
                        className={cn(
                          'rounded-xl border px-2 py-2.5 text-xs flex flex-col items-center gap-1 transition',
                          country.code === c.code
                            ? 'border-gold bg-gold/10 text-gold'
                            : 'border-ink-700 bg-ink-900 text-ink-200 hover:border-gold/40'
                        )}
                      >
                        <span className="text-xl">{c.flag}</span>
                        <span>{c.currency}</span>
                      </button>
                    ))}
                  </div>
                  <select
                    value={country.code}
                    onChange={(e) =>
                      setCountry(COUNTRIES.find((c) => c.code === e.target.value) || COUNTRIES[0])
                    }
                    className="input mt-2 text-sm"
                  >
                    {COUNTRIES.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.flag} {c.name} ({c.currency})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="label">Amount</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-300 font-medium">
                      {country.currencySymbol}
                    </span>
                    <input
                      type="number"
                      min="1"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="input pl-10 text-xl font-semibold"
                    />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {['5000', '10000', '25000', '50000'].map((a) => (
                      <button
                        key={a}
                        type="button"
                        onClick={() => setAmount(a)}
                        className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-1 text-xs text-ink-200 hover:border-gold/40"
                      >
                        {country.currencySymbol}
                        {Number(a).toLocaleString()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-ink-700 bg-ink-900 p-4 space-y-2 text-sm">
                  {quoteLoading && (
                    <p className="text-ink-300 flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" /> Fetching live rate…
                    </p>
                  )}
                  {!quoteLoading && quote && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-ink-300">You pay</span>
                        <span className="text-ink-50 font-medium">
                          {country.currencySymbol}
                          {quote.total.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-ink-300">Rate</span>
                        <span className="text-ink-100">
                          1 USDT ≈ {country.currencySymbol}
                          {perUSD?.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-ink-300">Partner fee</span>
                        <span className="text-ink-100">
                          {country.currencySymbol}
                          {quote.fee.toLocaleString()}
                        </span>
                      </div>
                      <div className="h-px bg-ink-700 my-1" />
                      <div className="flex justify-between items-baseline">
                        <span className="text-ink-300">You get</span>
                        <span className="gold-text font-bold text-lg">
                          {formatUSDT(quote.toAmount)} USDT
                        </span>
                      </div>
                      {providerMeta && (
                        <p className="pt-2 text-xs text-ink-400 flex items-center gap-1.5">
                          <Sparkles size={12} className="text-gold" />
                          Routed via <span className="text-ink-200">{providerMeta.name}</span>
                          {!providerMeta.isConfigured && (
                            <span className="text-gold/80">(demo mode)</span>
                          )}
                        </p>
                      )}
                    </>
                  )}
                  {!quoteLoading && !quote && (
                    <p className="text-ink-400 text-xs">Enter an amount to see a live quote.</p>
                  )}
                </div>

                <button
                  onClick={createOnRamp}
                  disabled={!quote || creating || amountN <= 0}
                  className="btn-gold w-full"
                >
                  {creating ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Starting deposit…
                    </>
                  ) : (
                    <>
                      Continue <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>
            )}

            {step === 'instructions' && onRamp?.bankInstructions && (
              <div className="p-6 space-y-4">
                <p className="text-sm text-ink-300">
                  Transfer <span className="text-ink-50 font-semibold">
                    {country.currencySymbol}
                    {onRamp.quote.total.toLocaleString()}
                  </span>{' '}
                  from your bank app to this account. Your wallet credits automatically once{' '}
                  {onRamp.provider} confirms.
                </p>

                <div className="card p-4 space-y-3 bg-ink-900 border-ink-700">
                  <Field label="Bank" value={onRamp.bankInstructions.bankName} />
                  <Field label="Account number" value={onRamp.bankInstructions.accountNumber} mono />
                  <Field label="Account name" value={onRamp.bankInstructions.accountName} />
                  <div>
                    <p className="text-xs text-ink-400 mb-1">Reference (MUST include)</p>
                    <button
                      onClick={copyRef}
                      className="w-full flex items-center justify-between gap-2 rounded-lg border border-gold/40 bg-gold/5 px-3 py-2 text-sm font-mono text-gold hover:border-gold"
                    >
                      <span>{onRamp.bankInstructions.reference}</span>
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>

                <div className="rounded-lg bg-ink-900 border border-ink-700 p-3 text-xs text-ink-300 flex items-start gap-2">
                  <Clock size={14} className="mt-0.5 text-gold flex-shrink-0" />
                  Funds usually confirm within 2 minutes. You&apos;ll get{' '}
                  <strong className="text-ink-100">{formatUSDT(onRamp.quote.toAmount)} USDT</strong>{' '}
                  once settled.
                </div>

                <div className="flex gap-2">
                  <button onClick={markAsPaid} className="btn-gold flex-1">
                    I&apos;ve sent the transfer
                  </button>
                  <button onClick={onClose} className="btn-ghost flex-1">
                    Later
                  </button>
                </div>
              </div>
            )}

            {step === 'pending' && (
              <div className="p-10 text-center space-y-4">
                <div className="mx-auto h-16 w-16 rounded-full bg-gold/10 border border-gold flex items-center justify-center text-gold">
                  <Banknote size={28} />
                </div>
                <h3 className="text-xl font-bold text-ink-50">Transfer in flight</h3>
                <p className="text-ink-300 text-sm">
                  {onRamp?.provider || 'The partner'} is confirming your payment. This usually takes
                  2–10 minutes. You&apos;ll get a push + email once your USDT is credited.
                </p>
                <button onClick={onClose} className="btn-ghost w-full">
                  Close
                </button>
              </div>
            )}

            {step === 'confirmed' && (
              <div className="p-10 text-center space-y-4">
                <div className="mx-auto h-16 w-16 rounded-full bg-emerald-500/10 border border-emerald-500 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 size={28} />
                </div>
                <h3 className="text-xl font-bold text-ink-50">Deposit confirmed</h3>
                <p className="text-ink-300 text-sm">Your wallet balance has been updated.</p>
                <button onClick={onClose} className="btn-gold w-full">
                  Done
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-ink-400 mb-0.5">{label}</p>
      <p className={cn('text-sm text-ink-50', mono && 'font-mono tracking-wide')}>{value}</p>
    </div>
  )
}
