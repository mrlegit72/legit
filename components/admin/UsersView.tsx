'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import toast from 'react-hot-toast'
import { Loader2, Search, ShieldAlert, ShieldCheck, Snowflake, Flame } from 'lucide-react'
import { cn, formatUSDT, initials } from '@/lib/utils'

type Row = {
  id: string
  name: string
  email: string
  phone: string | null
  country: string
  image: string | null
  role: 'user' | 'admin'
  status: 'active' | 'frozen'
  kycStatus: string
  twoFAEnabled: boolean
  balance: number
  groupCount: number
  amlFlagCount: number
  createdAt: string
}

export function UsersView() {
  const [users, setUsers] = useState<Row[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    const res = await fetch(`/api/admin/users?q=${encodeURIComponent(q)}`)
    const data = await res.json()
    setUsers(data.users || [])
    setLoading(false)
  }

  useEffect(() => {
    const h = setTimeout(load, 300)
    return () => clearTimeout(h)
  }, [q])

  async function update(user: Row, patch: Partial<Pick<Row, 'role' | 'status' | 'kycStatus'>>) {
    try {
      const res = await fetch(`/api/admin/users/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed')
      toast.success(`${user.name} updated`)
      setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, ...patch } : u)))
    } catch (e: any) {
      toast.error(e.message || 'Failed')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Users</h1>
        <p className="mt-1 text-ink-300">Freeze accounts, promote admins, review KYC flags.</p>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by email, name, or phone"
          className="input pl-10"
        />
      </div>

      {loading ? (
        <div className="card p-10 text-center text-ink-400">
          <Loader2 size={20} className="animate-spin mx-auto mb-2" />
          Loading users…
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-ink-400 bg-ink-900">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">User</th>
                  <th className="text-left px-4 py-3 font-medium">Country</th>
                  <th className="text-left px-4 py-3 font-medium">Balance</th>
                  <th className="text-left px-4 py-3 font-medium">Groups</th>
                  <th className="text-left px-4 py-3 font-medium">KYC</th>
                  <th className="text-left px-4 py-3 font-medium">Role</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-ink-700/60">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {u.image ? (
                          <Image
                            src={u.image}
                            alt={u.name}
                            width={32}
                            height={32}
                            className="h-8 w-8 rounded-full bg-ink-700"
                            unoptimized
                          />
                        ) : (
                          <span className="h-8 w-8 rounded-full bg-gold text-ink-950 text-xs font-bold flex items-center justify-center">
                            {initials(u.name)}
                          </span>
                        )}
                        <div>
                          <p className="text-ink-50 font-medium">{u.name}</p>
                          <p className="text-xs text-ink-400">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-200">{u.country}</td>
                    <td className="px-4 py-3 gold-text font-medium">{formatUSDT(u.balance)}</td>
                    <td className="px-4 py-3 text-ink-200">{u.groupCount}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.kycStatus}
                        onChange={(e) => update(u, { kycStatus: e.target.value })}
                        className="input text-xs py-1 max-w-[120px]"
                      >
                        <option value="unverified">unverified</option>
                        <option value="pending">pending</option>
                        <option value="verified">verified</option>
                        <option value="rejected">rejected</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'badge',
                          u.role === 'admin'
                            ? 'bg-gold/10 text-gold border border-gold/30'
                            : 'bg-ink-700 text-ink-200 border border-ink-600'
                        )}
                      >
                        {u.role === 'admin' && <ShieldCheck size={12} />}
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(u.status === 'active' ? 'badge-active' : 'badge-failed')}
                      >
                        {u.status === 'frozen' && <Snowflake size={12} />}
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            update(u, { status: u.status === 'active' ? 'frozen' : 'active' })
                          }
                          className="text-xs text-ink-300 hover:text-gold flex items-center gap-1"
                        >
                          {u.status === 'active' ? <Snowflake size={12} /> : <Flame size={12} />}
                          {u.status === 'active' ? 'Freeze' : 'Unfreeze'}
                        </button>
                        <button
                          onClick={() => update(u, { role: u.role === 'admin' ? 'user' : 'admin' })}
                          className="text-xs text-ink-300 hover:text-gold flex items-center gap-1"
                        >
                          <ShieldCheck size={12} />
                          {u.role === 'admin' ? 'Demote' : 'Promote'}
                        </button>
                        {u.amlFlagCount > 0 && (
                          <span className="text-xs text-red-400 flex items-center gap-1">
                            <ShieldAlert size={12} /> {u.amlFlagCount}
                          </span>
                        )}
                      </div>
                    </td>
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
