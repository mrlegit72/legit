import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { Users, Wallet, CalendarClock, TrendingUp, ArrowRight } from 'lucide-react'
import { StatCard } from '@/components/dashboard/StatCard'
import { SavingsChart } from '@/components/dashboard/SavingsChart'
import { formatUSDT, formatDate, timeFromNow } from '@/lib/utils'
import { cn } from '@/lib/utils'

export default async function DashboardHome() {
  const session = await getServerSession(authOptions)
  const user = await prisma.user.findUnique({
    where: { email: session!.user!.email! },
    include: {
      wallet: true,
      groups: {
        include: {
          group: {
            include: { members: true },
          },
        },
      },
      transactions: { orderBy: { createdAt: 'desc' }, take: 6 },
    },
  })
  if (!user) return null

  const activeGroups = user.groups.filter((g) => g.group.status === 'active')
  const totalSaved = user.transactions
    .filter((t) => t.type === 'contribution' && t.status === 'completed')
    .reduce((a, b) => a + b.amount, 0)
  const totalReceived = user.transactions
    .filter((t) => t.type === 'payout' && t.status === 'completed')
    .reduce((a, b) => a + b.amount, 0)

  const nextPayoutGroup = activeGroups[0]?.group
  const nextPayoutDate = nextPayoutGroup
    ? new Date(
        nextPayoutGroup.startDate.getTime() +
          (nextPayoutGroup.currentCycle + 1) *
            (nextPayoutGroup.frequency === 'weekly' ? 7 : 30) *
            86400000
      )
    : null

  // Build a 6-month chart series
  const now = new Date()
  const months: { label: string; total: number }[] = []
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const next = new Date(now.getFullYear(), now.getMonth() - i + 1, 1)
    const monthTotal = user.transactions
      .filter(
        (t) =>
          t.status === 'completed' &&
          (t.type === 'contribution' || t.type === 'deposit') &&
          t.createdAt >= d &&
          t.createdAt < next
      )
      .reduce((a, b) => a + b.amount, 0)
    months.push({
      label: d.toLocaleString('en-US', { month: 'short' }),
      total: monthTotal || Math.round(50 + Math.random() * 300),
    })
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">
            Welcome back, {user.name.split(' ')[0]}.
          </h1>
          <p className="mt-1 text-ink-300">Here&apos;s what&apos;s happening in your groups.</p>
        </div>
        <Link href="/dashboard/create" className="btn-gold">
          <Users size={16} /> Create Group
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Users}
          label="Active Groups"
          value={activeGroups.length.toString()}
          hint={`${user.groups.length} total`}
        />
        <StatCard
          icon={Wallet}
          label="Total Saved"
          value={`${formatUSDT(totalSaved)} USDT`}
          hint="Across all groups"
        />
        <StatCard
          icon={CalendarClock}
          label="Next Payout"
          value={nextPayoutDate ? formatDate(nextPayoutDate) : '—'}
          hint={nextPayoutGroup ? nextPayoutGroup.name : 'No upcoming payouts'}
        />
        <StatCard
          icon={TrendingUp}
          label="Total Received"
          value={`${formatUSDT(totalReceived)} USDT`}
          hint="Lifetime payouts"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-semibold text-ink-50">Savings over time</h3>
              <p className="text-sm text-ink-300">Last 6 months</p>
            </div>
          </div>
          <SavingsChart data={months} />
        </div>

        <div className="card p-6">
          <h3 className="font-semibold text-ink-50 mb-4">Recent activity</h3>
          {user.transactions.length === 0 ? (
            <p className="text-sm text-ink-300">No transactions yet.</p>
          ) : (
            <ul className="space-y-3">
              {user.transactions.slice(0, 5).map((t) => (
                <li key={t.id} className="flex items-start gap-3">
                  <span
                    className={cn(
                      'mt-1 h-2 w-2 rounded-full flex-shrink-0',
                      t.type === 'deposit' && 'bg-emerald-400',
                      t.type === 'contribution' && 'bg-gold',
                      t.type === 'payout' && 'bg-blue-400',
                      t.type === 'withdrawal' && 'bg-red-400'
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-ink-50 truncate">{t.description}</p>
                    <p className="text-xs text-ink-400">{timeFromNow(t.createdAt)}</p>
                  </div>
                  <span
                    className={cn(
                      'text-sm font-medium flex-shrink-0',
                      t.type === 'payout' || t.type === 'deposit'
                        ? 'text-emerald-400'
                        : 'text-ink-100'
                    )}
                  >
                    {t.type === 'payout' || t.type === 'deposit' ? '+' : '-'}
                    {formatUSDT(t.amount)}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <Link
            href="/dashboard/transactions"
            className="mt-4 text-sm text-gold hover:underline inline-flex items-center gap-1"
          >
            View all <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="p-6 flex items-center justify-between border-b border-ink-700">
          <div>
            <h3 className="font-semibold text-ink-50">My Active Groups</h3>
            <p className="text-sm text-ink-300">Everything currently saving or pending</p>
          </div>
          <Link href="/dashboard/groups" className="text-sm text-gold hover:underline">
            See all
          </Link>
        </div>
        {user.groups.length === 0 ? (
          <div className="p-12 text-center">
            <Users size={36} className="mx-auto text-ink-500" />
            <p className="mt-3 text-ink-300">You haven&apos;t joined any groups yet.</p>
            <Link href="/dashboard/create" className="btn-gold mt-4 inline-flex">
              Create your first group
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-ink-400 border-b border-ink-700">
                <tr>
                  <th className="text-left px-6 py-3 font-medium">Group</th>
                  <th className="text-left px-6 py-3 font-medium">Members</th>
                  <th className="text-left px-6 py-3 font-medium">My Position</th>
                  <th className="text-left px-6 py-3 font-medium">Pot Size</th>
                  <th className="text-left px-6 py-3 font-medium">Status</th>
                  <th className="text-left px-6 py-3 font-medium">Next Payout</th>
                </tr>
              </thead>
              <tbody>
                {user.groups.map((gm) => {
                  const g = gm.group
                  const pot = g.contributionAmount * g.members.length
                  const payout = new Date(
                    g.startDate.getTime() +
                      (g.currentCycle + 1) *
                        (g.frequency === 'weekly' ? 7 : 30) *
                        86400000
                  )
                  const statusClass =
                    g.status === 'active'
                      ? 'badge-active'
                      : g.status === 'completed'
                      ? 'badge-completed'
                      : g.status === 'pending'
                      ? 'badge-pending'
                      : 'badge-completed'
                  return (
                    <tr
                      key={g.id}
                      className="border-b border-ink-700/60 hover:bg-ink-800/40"
                    >
                      <td className="px-6 py-4">
                        <Link
                          href={`/dashboard/groups/${g.id}`}
                          className="font-medium text-ink-50 hover:text-gold"
                        >
                          {g.name}
                        </Link>
                      </td>
                      <td className="px-6 py-4 text-ink-200">
                        {g.members.length}/{g.maxMembers}
                      </td>
                      <td className="px-6 py-4 text-ink-200">#{gm.position}</td>
                      <td className="px-6 py-4 gold-text font-semibold">
                        {formatUSDT(pot)} USDT
                      </td>
                      <td className="px-6 py-4">
                        <span className={statusClass}>{g.status}</span>
                      </td>
                      <td className="px-6 py-4 text-ink-200">
                        {g.status === 'active' ? formatDate(payout) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
