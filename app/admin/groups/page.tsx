import Link from 'next/link'
import { prisma } from '@/lib/prisma'
import { formatUSDT, formatDate } from '@/lib/utils'

export const dynamic = 'force-dynamic'

export default async function AdminGroupsPage() {
  const groups = await prisma.group.findMany({
    include: { members: { include: { user: { select: { country: true } } } } },
    orderBy: { createdAt: 'desc' },
    take: 100,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Groups</h1>
        <p className="mt-1 text-ink-300">All groups across the platform. Latest first.</p>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-ink-400 bg-ink-900">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Group</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Members</th>
                <th className="text-left px-4 py-3 font-medium">Cycle</th>
                <th className="text-left px-4 py-3 font-medium">Pot</th>
                <th className="text-left px-4 py-3 font-medium">Frequency</th>
                <th className="text-left px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => {
                const pot = g.contributionAmount * g.members.length
                const statusClass =
                  g.status === 'active'
                    ? 'badge-active'
                    : g.status === 'completed'
                      ? 'badge-completed'
                      : 'badge-pending'
                return (
                  <tr key={g.id} className="border-b border-ink-700/60">
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/groups/${g.id}`}
                        className="text-ink-50 font-medium hover:text-gold"
                      >
                        {g.name}
                      </Link>
                      <p className="text-xs text-ink-400">
                        {g.members[0]?.user.country || '—'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={statusClass}>{g.status}</span>
                    </td>
                    <td className="px-4 py-3 text-ink-200">
                      {g.members.length}/{g.maxMembers}
                    </td>
                    <td className="px-4 py-3 text-ink-200">
                      {g.currentCycle}/{g.maxMembers}
                    </td>
                    <td className="px-4 py-3 gold-text font-medium">{formatUSDT(pot)}</td>
                    <td className="px-4 py-3 capitalize text-ink-200">{g.frequency}</td>
                    <td className="px-4 py-3 text-ink-400 text-xs">{formatDate(g.startDate)}</td>
                  </tr>
                )
              })}
              {groups.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-ink-400">
                    No groups yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
