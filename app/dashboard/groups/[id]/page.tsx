import { notFound, redirect } from 'next/navigation'
import Image from 'next/image'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { Check, Clock, Trophy, Calendar, Users, DollarSign, Activity } from 'lucide-react'
import { formatUSDT, formatDate, timeFromNow, initials } from '@/lib/utils'
import { CopyInviteLink } from '@/components/dashboard/CopyInviteLink'
import { PayoutCountdown } from '@/components/dashboard/PayoutCountdown'

export default async function GroupDetailPage({
  params,
}: {
  params: { id: string }
}) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) redirect('/auth/login')

  const group = await prisma.group.findUnique({
    where: { id: params.id },
    include: {
      members: { include: { user: true }, orderBy: { position: 'asc' } },
      contributions: { orderBy: { cycle: 'desc' }, take: 50 },
    },
  })
  if (!group) notFound()

  const contributionsByMember = new Map<string, Set<number>>()
  for (const c of group.contributions) {
    if (!contributionsByMember.has(c.userId)) contributionsByMember.set(c.userId, new Set())
    if (c.status === 'confirmed') contributionsByMember.get(c.userId)!.add(c.cycle)
  }

  const pot = group.contributionAmount * group.members.length
  const progress = group.maxMembers > 0 ? (group.currentCycle / group.maxMembers) * 100 : 0
  const statusClass =
    group.status === 'active'
      ? 'badge-active'
      : group.status === 'completed'
      ? 'badge-completed'
      : 'badge-pending'
  const nextPayout = new Date(
    group.startDate.getTime() +
      (group.currentCycle + 1) * (group.frequency === 'weekly' ? 7 : 30) * 86400000
  )

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-ink-50">{group.name}</h1>
              <span className={statusClass}>{group.status}</span>
            </div>
            <p className="mt-1 text-ink-300">{group.description}</p>
          </div>
          <CopyInviteLink inviteCode={group.inviteCode} />
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-xs text-ink-300 mb-1.5">
            <span>
              Cycle {group.currentCycle} / {group.maxMembers}
            </span>
            <span>{Math.round(progress)}% complete</span>
          </div>
          <div className="h-2 rounded-full bg-ink-700 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-gold-600 to-gold"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-4">
          <InfoPill icon={Users} label="Members" value={`${group.members.length}/${group.maxMembers}`} />
          <InfoPill
            icon={DollarSign}
            label="Per cycle"
            value={`${formatUSDT(group.contributionAmount)} USDT`}
          />
          <InfoPill icon={Trophy} label="Pot per cycle" value={`${formatUSDT(pot)} USDT`} />
          <InfoPill
            icon={Calendar}
            label="Frequency"
            value={group.frequency.charAt(0).toUpperCase() + group.frequency.slice(1)}
          />
        </div>
      </div>

      {group.status === 'active' && (
        <div className="card p-6">
          <div className="flex items-center gap-2 text-sm text-ink-300 mb-3">
            <Clock size={16} /> Next payout
          </div>
          <PayoutCountdown date={nextPayout.toISOString()} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="p-6 border-b border-ink-700">
            <h3 className="font-semibold text-ink-50">Members</h3>
            <p className="text-sm text-ink-300">Rotation order & contribution status</p>
          </div>
          <ul className="divide-y divide-ink-700">
            {group.members.map((m) => {
              const confirmedSet = contributionsByMember.get(m.userId) || new Set()
              const allConfirmed = confirmedSet.size >= group.currentCycle && group.currentCycle > 0
              return (
                <li key={m.id} className="flex items-center gap-3 p-4">
                  <span className="h-8 w-8 rounded-full bg-gold text-ink-950 text-xs font-bold flex items-center justify-center">
                    #{m.position}
                  </span>
                  {m.user.image ? (
                    <Image
                      src={m.user.image}
                      alt={m.user.name}
                      width={36}
                      height={36}
                      className="h-9 w-9 rounded-full bg-ink-700"
                      unoptimized
                    />
                  ) : (
                    <span className="h-9 w-9 rounded-full bg-ink-700 flex items-center justify-center text-xs font-bold">
                      {initials(m.user.name)}
                    </span>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-ink-50 truncate">{m.user.name}</p>
                    <p className="text-xs text-ink-400">{m.user.country}</p>
                  </div>
                  {m.hasReceivedPot && (
                    <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <Trophy size={12} /> Received
                    </span>
                  )}
                  {allConfirmed ? (
                    <span className="h-7 w-7 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center">
                      <Check size={14} />
                    </span>
                  ) : (
                    <span className="h-7 w-7 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center">
                      <Clock size={14} />
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>

        <div className="space-y-6">
          <div className="card overflow-hidden">
            <div className="p-6 border-b border-ink-700">
              <h3 className="font-semibold text-ink-50">Contribution history</h3>
            </div>
            {group.contributions.length === 0 ? (
              <p className="p-6 text-sm text-ink-400">No contributions yet.</p>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-ink-400 bg-ink-900">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Cycle</th>
                      <th className="text-left px-4 py-2 font-medium">Amount</th>
                      <th className="text-left px-4 py-2 font-medium">Status</th>
                      <th className="text-left px-4 py-2 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.contributions.map((c) => (
                      <tr key={c.id} className="border-b border-ink-700/60">
                        <td className="px-4 py-2.5">{c.cycle}</td>
                        <td className="px-4 py-2.5 text-ink-100">{formatUSDT(c.amount)}</td>
                        <td className="px-4 py-2.5">
                          <span
                            className={
                              c.status === 'confirmed' ? 'badge-active' : 'badge-pending'
                            }
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-ink-400 text-xs">
                          {formatDate(c.createdAt)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card p-6">
            <div className="flex items-center gap-2 mb-3">
              <Activity size={16} className="text-gold" />
              <h3 className="font-semibold text-ink-50">Group activity</h3>
            </div>
            <ul className="space-y-3">
              <ActivityItem
                color="bg-emerald-400"
                title={`Cycle ${group.currentCycle} contributions received`}
                time="2h ago"
              />
              <ActivityItem
                color="bg-gold"
                title={`${group.members[0]?.user.name ?? 'A member'} joined the group`}
                time="2d ago"
              />
              <ActivityItem
                color="bg-blue-400"
                title="Group created"
                time={timeFromNow(group.createdAt)}
              />
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoPill({
  icon: Icon,
  label,
  value,
}: {
  icon: any
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900 p-4">
      <div className="flex items-center gap-2 text-xs text-ink-400">
        <Icon size={14} /> {label}
      </div>
      <p className="mt-1 text-ink-50 font-semibold">{value}</p>
    </div>
  )
}

function ActivityItem({
  color,
  title,
  time,
}: {
  color: string
  title: string
  time: string
}) {
  return (
    <li className="flex items-start gap-3">
      <span className={`mt-1.5 h-2 w-2 rounded-full ${color}`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink-100">{title}</p>
        <p className="text-xs text-ink-400">{time}</p>
      </div>
    </li>
  )
}
