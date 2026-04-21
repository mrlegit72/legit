'use client'

import { useState } from 'react'
import Image from 'next/image'
import toast from 'react-hot-toast'
import { Shield, Bell, User as UserIcon, Banknote, Upload } from 'lucide-react'
import { cn, initials } from '@/lib/utils'

const tabs = [
  { id: 'profile', label: 'Profile', icon: UserIcon },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'bank', label: 'Bank account', icon: Banknote },
]

export function SettingsView({
  user,
}: {
  user: {
    name: string
    email: string
    phone: string | null
    country: string
    image: string | null
  }
}) {
  const [tab, setTab] = useState('profile')
  const [profile, setProfile] = useState({
    name: user.name,
    phone: user.phone ?? '',
    country: user.country,
    image: user.image ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [security, setSecurity] = useState({ current: '', next: '', twoFA: false })
  const [notifs, setNotifs] = useState({ emailPayouts: true, emailContributions: true, inAppAll: true })
  const [bank, setBank] = useState({ bankName: '', accountNumber: '', accountName: '' })

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await fetch('/api/user/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })
      if (!res.ok) throw new Error('Failed')
      toast.success('Profile updated')
    } catch {
      toast.error('Could not save profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Settings</h1>
        <p className="mt-1 text-ink-300">Manage your profile, security, and payout preferences.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav className="card p-2 h-fit lg:sticky lg:top-20">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition',
                tab === t.id
                  ? 'bg-gold/10 text-gold'
                  : 'text-ink-200 hover:bg-ink-700/60'
              )}
            >
              <t.icon size={16} /> {t.label}
            </button>
          ))}
        </nav>

        <div>
          {tab === 'profile' && (
            <form onSubmit={saveProfile} className="card p-6 space-y-5">
              <div className="flex items-center gap-4">
                {profile.image ? (
                  <Image
                    src={profile.image}
                    alt={profile.name}
                    width={64}
                    height={64}
                    className="h-16 w-16 rounded-full bg-ink-700"
                    unoptimized
                  />
                ) : (
                  <span className="h-16 w-16 rounded-full bg-gold text-ink-950 text-xl font-bold flex items-center justify-center">
                    {initials(profile.name)}
                  </span>
                )}
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      const seed = encodeURIComponent(profile.name + Math.random().toString(36).slice(2))
                      setProfile({
                        ...profile,
                        image: `https://api.dicebear.com/7.x/avataaars/svg?seed=${seed}`,
                      })
                    }}
                    className="btn-dark text-sm"
                  >
                    <Upload size={14} /> Change avatar
                  </button>
                  <p className="mt-1 text-xs text-ink-400">PNG or SVG, up to 2MB.</p>
                </div>
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Full name</label>
                  <input
                    value={profile.name}
                    onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input value={user.email} disabled className="input opacity-60" />
                </div>
                <div>
                  <label className="label">Phone</label>
                  <input
                    value={profile.phone}
                    onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Country</label>
                  <select
                    value={profile.country}
                    onChange={(e) => setProfile({ ...profile, country: e.target.value })}
                    className="input"
                  >
                    <option>Nigeria</option>
                    <option>Ghana</option>
                  </select>
                </div>
              </div>
              <button type="submit" disabled={saving} className="btn-gold">
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </form>
          )}

          {tab === 'security' && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                toast.success('Password updated')
                setSecurity({ current: '', next: '', twoFA: security.twoFA })
              }}
              className="card p-6 space-y-5"
            >
              <h3 className="font-semibold text-ink-50">Change password</h3>
              <div>
                <label className="label">Current password</label>
                <input
                  type="password"
                  value={security.current}
                  onChange={(e) => setSecurity({ ...security, current: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="label">New password</label>
                <input
                  type="password"
                  value={security.next}
                  onChange={(e) => setSecurity({ ...security, next: e.target.value })}
                  className="input"
                />
              </div>

              <div className="flex items-center justify-between rounded-xl border border-ink-700 bg-ink-900 p-4">
                <div>
                  <p className="text-sm font-medium text-ink-50">Two-factor authentication</p>
                  <p className="text-xs text-ink-400">Require a code from your authenticator app.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setSecurity({ ...security, twoFA: !security.twoFA })}
                  className={cn(
                    'relative h-6 w-11 rounded-full transition',
                    security.twoFA ? 'bg-gold' : 'bg-ink-700'
                  )}
                >
                  <span
                    className={cn(
                      'absolute top-0.5 h-5 w-5 rounded-full bg-white transition',
                      security.twoFA ? 'left-5' : 'left-0.5'
                    )}
                  />
                </button>
              </div>

              <button className="btn-gold">Update security</button>
            </form>
          )}

          {tab === 'notifications' && (
            <div className="card p-6 space-y-4">
              {[
                { key: 'emailPayouts', label: 'Email me when I receive a payout', desc: 'Get notified the moment funds land in your wallet.' },
                { key: 'emailContributions', label: 'Email me on contribution receipts', desc: 'A confirmation for each cycle payment.' },
                { key: 'inAppAll', label: 'In-app notifications', desc: 'Show alerts inside the dashboard bell.' },
              ].map((opt) => (
                <div
                  key={opt.key}
                  className="flex items-center justify-between rounded-xl border border-ink-700 bg-ink-900 p-4"
                >
                  <div>
                    <p className="text-sm font-medium text-ink-50">{opt.label}</p>
                    <p className="text-xs text-ink-400">{opt.desc}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setNotifs({ ...notifs, [opt.key]: !(notifs as any)[opt.key] })}
                    className={cn(
                      'relative h-6 w-11 rounded-full transition',
                      (notifs as any)[opt.key] ? 'bg-gold' : 'bg-ink-700'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-0.5 h-5 w-5 rounded-full bg-white transition',
                        (notifs as any)[opt.key] ? 'left-5' : 'left-0.5'
                      )}
                    />
                  </button>
                </div>
              ))}
              <button
                onClick={() => toast.success('Preferences saved')}
                className="btn-gold"
              >
                Save preferences
              </button>
            </div>
          )}

          {tab === 'bank' && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                toast.success('Bank account saved')
              }}
              className="card p-6 space-y-4"
            >
              <h3 className="font-semibold text-ink-50">Bank account for withdrawals</h3>
              <p className="text-sm text-ink-300">
                Used when you cash out your USDT pot to Naira or Cedi.
              </p>
              <div>
                <label className="label">Bank name</label>
                <input
                  value={bank.bankName}
                  onChange={(e) => setBank({ ...bank, bankName: e.target.value })}
                  className="input"
                  placeholder="GTBank"
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Account number</label>
                  <input
                    value={bank.accountNumber}
                    onChange={(e) => setBank({ ...bank, accountNumber: e.target.value })}
                    className="input"
                    placeholder="0123456789"
                  />
                </div>
                <div>
                  <label className="label">Account name</label>
                  <input
                    value={bank.accountName}
                    onChange={(e) => setBank({ ...bank, accountName: e.target.value })}
                    className="input"
                    placeholder="As on statement"
                  />
                </div>
              </div>
              <button className="btn-gold">Save bank details</button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
