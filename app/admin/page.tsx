import Link from 'next/link'
import {
  Users as UsersIcon,
  Boxes,
  Wallet,
  Banknote,
  AlertTriangle,
  TrendingUp,
  ShieldCheck,
  Globe2,
} from 'lucide-react'
import { prisma } from '@/lib/prisma'
import { formatUSDT } from '@/lib/utils'
import { StatCard } from '@/components/dashboard/StatCard'
import { SavingsChart } from '@/components/dashboard/SavingsChart'

export const dynamic = 'force-dynamic'

export default async function AdminOverview() {
  const now = new Date()
  const d30 = new Date(now.getTime() - 30 * 86400000)

  const [
    userCount,
    groupActive,
    groupPending,
    groupCompleted,
    tvlAgg,
    pendingWithdrawals,
    openFlags,
    volAgg,
    revAgg,
    completedGroups,
    recentTxs,
    recentLogs,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.group.count({ where: { status: 'active' } }),
    prisma.group.count({ where: { status: 'pending' } }),
    prisma.group.count({ where: { status: 'completed' } }),
    prisma.wallet.aggregate({ _sum: { balance: true } }),
    prisma.withdrawalRequest.count({ where: { status: 'pending' } }),
    prisma.amlFlag.count({ where: { resolvedAt: null } }),
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: {
        status: 'completed',
        type: { in: ['deposit', 'contribution'] },
        createdAt: { gte: d30 },
      },
    }),
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: { status: 'completed', type: 'deposit', createdAt: { gte: d30 } },
    }),
    prisma.group.findMany({
      where: { status: 'completed' },
      select: { currentCycle: true, maxMembers: true },
    }),
    prisma.transaction.findMany({
      orderBy: { createdAt: 'desc' },
      take: 6,
      include: { user: { select: { name: true, email: true } } },
    }),
    prisma.auditLog.findMany({
      orderBy: { createdAt: 'desc' },
      take: 6,
      include: { actor: { select: { name: true } } },
    }),
  ])

  const tvl = tvlAgg._sum.balance ?? 0
  const volume30d = volAgg._sum.amount ?? 0
  const revenue30d = (revAgg._sum.amount ?? 0) * 0.015
  const cycleSuccess =
    completedGroups.length === 0
      ? 100
      : Math.round(
          (completedGroups.filter((g) => g.currentCycle >= g.maxMembers).length /
            completedGroups.length) *
            100
        )

  // 30-day sparkline
  const txs = await prisma.transaction.findMany({
    where: {
      status: 'completed',
      type: { in: ['deposit', 'contribution'] },
      createdAt: { gte: d30 },
    },
    select: { amount: true, createdAt: true },
  })
  const buckets: Record<string, number> = {}
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000)
    buckets[d.toISOString().slice(0, 10)] = 0
  }
  for (const t of txs) {
    const k = t.createdAt.toISOString().slice(0, 10)
    if (k in buckets) buckets[k] += t.amount
  }
  const spark = Object.entries(buckets).map(([date, total]) => ({
    label: date.slice(5),
    total: Number(total.toFixed(2)),
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Overview</h1>
        <p className="mt-1 text-ink-300">Platform health, treasury, and queues at a glance.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={ShieldCheck} label="TVL (treasury)" value={`${formatUSDT(tvl)} USDT`} hint="Across all wallets" />
        <StatCard
          icon={TrendingUp}
          label="30-day volume"
          value={`${formatUSDT(volume30d)} USDT`}
          hint={`~${formatUSDT(revenue30d)} USDT est. revenue`}
        />
        <StatCard
          icon={UsersIcon}
          label="Users"
          value={userCount.toString()}
          hint={`${openFlags} open AML flags`}
        />
        <StatCard
          icon={Banknote}
          label="Withdrawals pending"
          value={pendingWithdrawals.toString()}
          hint="Awaiting review"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Boxes} label="Active groups" value={groupActive.toString()} hint={`${groupPending} pending`} />
        <StatCard icon={Boxes} label="Completed groups" value={groupCompleted.toString()} hint={`${cycleSuccess}% cycle success`} />
        <StatCard icon={Globe2} label="Countries live" value="12" hint="Default list" />
        <StatCard icon={AlertTriangle} label="Open issues" value={(pendingWithdrawals + openFlags).toString()} hint="Withdrawals + AML" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-semibold text-ink-50">Platform volume — last 30 days</h3>
              <p className="text-sm text-ink-300">Deposits + contributions, daily, USDT</p>
            </div>
          </div>
          <SavingsChart data={spark} />
        </div>

        <div className="card p-6">
          <h3 className="font-semibold text-ink-50 mb-4">Latest admin activity</h3>
          {recentLogs.length === 0 ? (
            <p className="text-sm text-ink-400">No admin actions yet.</p>
          ) : (
            <ul className="space-y-3">
              {recentLogs.map((l) => (
                <li key={l.id} className="text-sm">
                  <p className="text-ink-100">
                    <span className="text-gold">{l.actor?.name || 'System'}</span> ·{' '}
                    <code className="text-xs text-ink-200">{l.action}</code>
                  </p>
                  <p className="text-xs text-ink-400 mt-0.5">
                    {l.target} · {new Date(l.createdAt).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <Link href="/admin/audit" className="mt-4 text-sm text-gold hover:underline inline-block">
            Full audit log →
          </Link>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="p-6 border-b border-ink-700">
          <h3 className="font-semibold text-ink-50">Recent transactions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-ink-400 bg-ink-900">
              <tr>
                <th className="text-left px-6 py-3 font-medium">User</th>
                <th className="text-left px-6 py-3 font-medium">Type</th>
                <th className="text-left px-6 py-3 font-medium">Amount</th>
                <th className="text-left px-6 py-3 font-medium">Status</th>
                <th className="text-left px-6 py-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentTxs.map((t) => (
                <tr key={t.id} className="border-b border-ink-700/60">
                  <td className="px-6 py-3 text-ink-100">{t.user.name}</td>
                  <td className="px-6 py-3 capitalize text-ink-200">{t.type}</td>
                  <td className="px-6 py-3 text-ink-50">
                    {formatUSDT(t.amount)} {t.currency}
                  </td>
                  <td className="px-6 py-3">
                    <span className={t.status === 'completed' ? 'badge-active' : t.status === 'failed' ? 'badge-failed' : 'badge-pending'}>
                      {t.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-ink-400 text-xs">
                    {new Date(t.createdAt).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
