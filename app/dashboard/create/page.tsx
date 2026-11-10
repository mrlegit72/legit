'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { Loader2, Users, Calendar, DollarSign, Shuffle, Sparkles } from 'lucide-react'
import { formatUSDT } from '@/lib/utils'

export default function CreateGroupPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    maxMembers: 10,
    contributionAmount: 100,
    frequency: 'weekly',
    startDate: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10),
    payoutOrder: 'rotation',
  })

  const pot = useMemo(
    () => form.contributionAmount * form.maxMembers,
    [form.contributionAmount, form.maxMembers]
  )
  const totalCycles = form.maxMembers
  const durationWeeks = form.frequency === 'weekly' ? totalCycles : totalCycles * 4

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch('/api/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        toast.error(data.error || 'Failed to create group')
        setLoading(false)
        return
      }
      toast.success('Group created!')
      router.push(`/dashboard/groups/${data.id}`)
    } catch {
      toast.error('Network error')
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Create a new group</h1>
        <p className="mt-1 text-ink-300">
          Set up your Ajo/Susu in under a minute. Members can join via an invite link.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <form onSubmit={onSubmit} className="lg:col-span-2 card p-6 space-y-5">
          <div>
            <label className="label">Group name</label>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Lagos Traders Circle"
              className="input"
            />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="What is this group saving for?"
              rows={3}
              className="input resize-none"
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Number of members (5 – 50)</label>
              <input
                type="number"
                min={5}
                max={50}
                value={form.maxMembers}
                onChange={(e) => setForm({ ...form, maxMembers: Number(e.target.value) })}
                className="input"
              />
            </div>
            <div>
              <label className="label">Contribution per cycle (USDT)</label>
              <input
                type="number"
                min={1}
                step="0.01"
                value={form.contributionAmount}
                onChange={(e) =>
                  setForm({ ...form, contributionAmount: Number(e.target.value) })
                }
                className="input"
              />
            </div>
            <div>
              <label className="label">Frequency</label>
              <select
                value={form.frequency}
                onChange={(e) => setForm({ ...form, frequency: e.target.value })}
                className="input"
              >
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
            <div>
              <label className="label">Start date</label>
              <input
                type="date"
                value={form.startDate}
                onChange={(e) => setForm({ ...form, startDate: e.target.value })}
                className="input"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label">Payout order</label>
              <div className="grid sm:grid-cols-2 gap-3">
                {[
                  { v: 'rotation', label: 'Rotation (randomly assigned)', icon: Shuffle },
                  { v: 'first_come', label: 'First come, first served', icon: Users },
                ].map((opt) => (
                  <button
                    type="button"
                    key={opt.v}
                    onClick={() => setForm({ ...form, payoutOrder: opt.v })}
                    className={`flex items-center gap-3 rounded-xl px-4 py-3 border text-sm text-left transition ${
                      form.payoutOrder === opt.v
                        ? 'border-gold bg-gold/10 text-gold'
                        : 'border-ink-700 bg-ink-900 text-ink-200 hover:border-gold/40'
                    }`}
                  >
                    <opt.icon size={16} /> {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button type="submit" disabled={loading} className="btn-gold w-full">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {loading ? 'Creating…' : 'Create group'}
          </button>
        </form>

        <aside className="card p-6 h-fit sticky top-20">
          <p className="text-sm font-medium text-gold uppercase tracking-wide">Preview</p>
          <h3 className="mt-2 text-xl font-bold text-ink-50">
            {form.name || 'Your group name'}
          </h3>
          <p className="mt-1 text-sm text-ink-300 line-clamp-2 min-h-[40px]">
            {form.description || 'Add a short description.'}
          </p>

          <div className="mt-6 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-ink-300 flex items-center gap-2">
                <Users size={14} /> Members
              </span>
              <span className="text-ink-50 font-medium">{form.maxMembers}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-300 flex items-center gap-2">
                <DollarSign size={14} /> Per cycle
              </span>
              <span className="text-ink-50 font-medium">
                {formatUSDT(form.contributionAmount)} USDT
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-300 flex items-center gap-2">
                <Calendar size={14} /> Frequency
              </span>
              <span className="text-ink-50 font-medium capitalize">{form.frequency}</span>
            </div>
            <div className="h-px bg-ink-700" />
            <div className="flex items-center justify-between">
              <span className="text-ink-300">Pot per cycle</span>
              <span className="gold-text font-bold text-lg">{formatUSDT(pot)} USDT</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-300">Duration</span>
              <span className="text-ink-50">
                ~{durationWeeks} {form.frequency === 'weekly' ? 'weeks' : 'weeks'}
              </span>
            </div>
          </div>

          <p className="mt-6 text-xs text-ink-400">
            An invite link will be generated once the group is created.
          </p>
        </aside>
      </div>
    </div>
  )
}
