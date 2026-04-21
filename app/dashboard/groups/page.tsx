import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { Users, PlusCircle } from 'lucide-react'
import { formatUSDT, formatDate } from '@/lib/utils'

export default async function GroupsPage() {
  const session = await getServerSession(authOptions)
  const user = await prisma.user.findUnique({
    where: { email: session!.user!.email! },
    include: {
      groups: {
        include: { group: { include: { members: true } } },
        orderBy: { joinedAt: 'desc' },
      },
    },
  })
  if (!user) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">My Groups</h1>
          <p className="mt-1 text-ink-300">All savings groups you&apos;re part of.</p>
        </div>
        <Link href="/dashboard/create" className="btn-gold">
          <PlusCircle size={16} /> Create Group
        </Link>
      </div>

      {user.groups.length === 0 ? (
        <div className="card p-12 text-center">
          <Users size={40} className="mx-auto text-ink-500" />
          <p className="mt-3 font-medium text-ink-100">No groups yet</p>
          <p className="mt-1 text-sm text-ink-400">Create your first group to get started.</p>
          <Link href="/dashboard/create" className="btn-gold mt-4 inline-flex">
            <PlusCircle size={16} /> Create Group
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {user.groups.map((gm) => {
            const g = gm.group
            const pot = g.contributionAmount * g.members.length
            const progress = g.maxMembers > 0 ? (g.currentCycle / g.maxMembers) * 100 : 0
            const statusClass =
              g.status === 'active'
                ? 'badge-active'
                : g.status === 'completed'
                ? 'badge-completed'
                : 'badge-pending'
            return (
              <Link
                key={g.id}
                href={`/dashboard/groups/${g.id}`}
                className="card p-5 hover:border-gold/40 hover:shadow-gold transition group"
              >
                <div className="flex items-start justify-between">
                  <h3 className="font-semibold text-ink-50 group-hover:text-gold">
                    {g.name}
                  </h3>
                  <span className={statusClass}>{g.status}</span>
                </div>
                <p className="mt-1 text-sm text-ink-300 line-clamp-2 min-h-[40px]">
                  {g.description}
                </p>

                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-ink-300 mb-1.5">
                    <span>
                      Cycle {g.currentCycle} / {g.maxMembers}
                    </span>
                    <span>{Math.round(progress)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-ink-700 overflow-hidden">
                    <div
                      className="h-full bg-gold"
                      style={{ width: `${Math.min(100, progress)}%` }}
                    />
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-ink-400">Members</p>
                    <p className="text-ink-100 font-medium">
                      {g.members.length}/{g.maxMembers}
                    </p>
                  </div>
                  <div>
                    <p className="text-ink-400">Per cycle</p>
                    <p className="text-ink-100 font-medium">
                      {formatUSDT(g.contributionAmount)}
                    </p>
                  </div>
                  <div>
                    <p className="text-ink-400">Pot</p>
                    <p className="gold-text font-semibold">{formatUSDT(pot)}</p>
                  </div>
                </div>

                <p className="mt-4 text-xs text-ink-400">
                  Starts {formatDate(g.startDate)}
                </p>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
