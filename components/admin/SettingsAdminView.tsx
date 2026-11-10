'use client'

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Loader2, Save } from 'lucide-react'

const GROUPS = [
  {
    title: 'Platform',
    keys: ['platform.feePct'],
  },
  {
    title: 'Groups',
    keys: [
      'groups.minMembers',
      'groups.maxMembers',
      'groups.minContributionUsdt',
      'groups.maxContributionUsdt',
      'groups.frequencies',
      'groups.defaultRotation',
    ],
  },
  {
    title: 'Disputes',
    keys: ['disputes.escalationWindowHours'],
  },
  {
    title: 'Withdrawals',
    keys: ['withdrawals.manualReviewThresholdUsdt'],
  },
  {
    title: 'Feature flags',
    keys: ['features.multiAdminGroups', 'features.inAppChat', 'features.smartContractEscrow'],
  },
  {
    title: 'Comms',
    keys: ['sms.senderId', 'email.fromAddress'],
  },
]

export function SettingsAdminView() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    const res = await fetch('/api/admin/settings')
    const data = await res.json()
    setSettings(data.settings || {})
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  async function save() {
    setSaving(true)
    try {
      const res = await fetch('/api/admin/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      })
      if (!res.ok) throw new Error()
      toast.success('Settings saved')
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Platform settings</h1>
        <p className="mt-1 text-ink-300">
          Knobs applied platform-wide. Feature flags gate incomplete surfaces.
        </p>
      </div>

      {loading ? (
        <div className="card p-10 text-center text-ink-400">
          <Loader2 size={20} className="animate-spin mx-auto mb-2" />
          Loading…
        </div>
      ) : (
        <>
          {GROUPS.map((g) => (
            <div key={g.title} className="card p-6">
              <h3 className="font-semibold text-ink-50 mb-4">{g.title}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {g.keys.map((k) => (
                  <div key={k}>
                    <label className="label font-mono text-xs">{k}</label>
                    <input
                      value={settings[k] ?? ''}
                      onChange={(e) => setSettings({ ...settings, [k]: e.target.value })}
                      className="input text-sm"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="sticky bottom-4 flex justify-end">
            <button onClick={save} disabled={saving} className="btn-gold">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Save all
            </button>
          </div>
        </>
      )}
    </div>
  )
}
