'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Beaker, CheckCircle2, Loader2, Save, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type Provider = {
  id: string
  name: string
  enabled: boolean
  hasKey: boolean
  hasWebhookSecret: boolean
  apiKeyMask: string | null
  webhookSecretMask: string | null
  feeOverridePct: number | null
  priority: number
  notes: string | null
  supportedCountries: string[]
  supportedCurrencies: string[]
  paymentMethods: string[]
  isEnvConfigured: boolean
}

export function ProvidersView() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    const res = await fetch('/api/admin/providers')
    const data = await res.json()
    setProviders(data.providers || [])
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Providers</h1>
        <p className="mt-1 text-ink-300">
          Partner on-ramp/off-ramp integrations. Keys are stored encrypted. Toggle enabled to
          control which providers are available to the router.
        </p>
      </div>

      {loading ? (
        <div className="card p-10 text-center text-ink-400">
          <Loader2 size={20} className="animate-spin mx-auto mb-2" />
          Loading providers…
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {providers.map((p) => (
            <ProviderCard key={p.id} provider={p} onChange={load} />
          ))}
        </div>
      )}
    </div>
  )
}

function ProviderCard({ provider, onChange }: { provider: Provider; onChange: () => void }) {
  const [form, setForm] = useState({
    enabled: provider.enabled,
    apiKey: '',
    webhookSecret: '',
    priority: provider.priority,
    feeOverridePct: provider.feeOverridePct ?? '',
    notes: provider.notes ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  async function save() {
    setSaving(true)
    const body: any = {
      providerId: provider.id,
      name: provider.name,
      enabled: form.enabled,
      priority: Number(form.priority),
      notes: form.notes || null,
      feeOverridePct:
        form.feeOverridePct === '' || form.feeOverridePct === null
          ? null
          : Number(form.feeOverridePct),
    }
    if (form.apiKey) body.apiKey = form.apiKey
    if (form.webhookSecret) body.webhookSecret = form.webhookSecret
    try {
      const res = await fetch('/api/admin/providers', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error()
      toast.success(`${provider.name} saved`)
      setForm({ ...form, apiKey: '', webhookSecret: '' })
      onChange()
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function test() {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch(`/api/admin/providers/${provider.id}/test`, { method: 'POST' })
      const data = await res.json()
      if (data.ok) {
        setTestResult({
          ok: true,
          message: `${data.latencyMs}ms · sample rate ${data.sampleQuote?.rate}`,
        })
      } else {
        setTestResult({ ok: false, message: data.error || 'Test failed' })
      }
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message || 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  const statusBadge = !form.enabled
    ? { cls: 'badge-failed', label: 'Disabled' }
    : provider.hasKey
      ? { cls: 'badge-active', label: 'Live' }
      : { cls: 'badge-pending', label: 'Demo mode' }

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-ink-50">{provider.name}</h3>
          <p className="text-xs text-ink-400 mt-0.5 font-mono">{provider.id}</p>
        </div>
        <span className={statusBadge.cls}>{statusBadge.label}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg bg-ink-900 border border-ink-700 p-3">
          <p className="text-ink-400">Countries</p>
          <p className="text-ink-100 mt-1">{provider.supportedCountries.join(', ')}</p>
        </div>
        <div className="rounded-lg bg-ink-900 border border-ink-700 p-3">
          <p className="text-ink-400">Payment methods</p>
          <p className="text-ink-100 mt-1 capitalize">{provider.paymentMethods.join(', ').replace(/_/g, ' ')}</p>
        </div>
      </div>

      <div className="flex items-center justify-between rounded-xl border border-ink-700 bg-ink-900 p-3">
        <div>
          <p className="text-sm font-medium text-ink-50">Enabled</p>
          <p className="text-xs text-ink-400">Disable to remove from router entirely</p>
        </div>
        <button
          type="button"
          onClick={() => setForm({ ...form, enabled: !form.enabled })}
          className={cn(
            'relative h-6 w-11 rounded-full transition',
            form.enabled ? 'bg-gold' : 'bg-ink-700'
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 h-5 w-5 rounded-full bg-white transition',
              form.enabled ? 'left-5' : 'left-0.5'
            )}
          />
        </button>
      </div>

      <div>
        <label className="label">API key</label>
        <input
          type="password"
          value={form.apiKey}
          onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
          placeholder={provider.apiKeyMask || (provider.isEnvConfigured ? 'Set via env var' : 'Not set')}
          className="input text-sm"
        />
        <p className="text-xs text-ink-400 mt-1">
          Current: {provider.apiKeyMask || (provider.isEnvConfigured ? 'env-configured' : 'none')}
        </p>
      </div>

      <div>
        <label className="label">Webhook secret</label>
        <input
          type="password"
          value={form.webhookSecret}
          onChange={(e) => setForm({ ...form, webhookSecret: e.target.value })}
          placeholder={provider.webhookSecretMask || 'Not set'}
          className="input text-sm"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Priority</label>
          <input
            type="number"
            min={1}
            max={10}
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            className="input text-sm"
          />
          <p className="text-xs text-ink-400 mt-1">1 (lowest) – 10 (highest)</p>
        </div>
        <div>
          <label className="label">Fee override (%)</label>
          <input
            type="number"
            step="0.01"
            value={form.feeOverridePct}
            onChange={(e) => setForm({ ...form, feeOverridePct: e.target.value as any })}
            placeholder="Partner default"
            className="input text-sm"
          />
        </div>
      </div>

      <div>
        <label className="label">Internal notes</label>
        <textarea
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          rows={2}
          className="input text-sm resize-none"
        />
      </div>

      {testResult && (
        <div
          className={cn(
            'rounded-lg border p-3 text-xs flex items-start gap-2',
            testResult.ok
              ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200'
              : 'border-red-500/30 bg-red-500/5 text-red-200'
          )}
        >
          {testResult.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {testResult.message}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button onClick={save} disabled={saving} className="btn-gold flex-1 text-sm">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </button>
        <button onClick={test} disabled={testing} className="btn-ghost flex-1 text-sm">
          {testing ? <Loader2 size={14} className="animate-spin" /> : <Beaker size={14} />}
          Test
        </button>
      </div>
    </div>
  )
}
