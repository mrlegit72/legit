import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin } from '@/lib/admin'

export async function GET() {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const now = new Date()
  const d30 = new Date(now.getTime() - 30 * 86400000)
  const d7 = new Date(now.getTime() - 7 * 86400000)
  const d1 = new Date(now.getTime() - 1 * 86400000)

  const [
    userCount,
    dau,
    wau,
    mau,
    groupPending,
    groupActive,
    groupCompleted,
    totalBalance,
    completedCyclesRaw,
    volume30dRaw,
    revenue30dRaw,
    pendingWithdrawals,
    openAmlFlags,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.user.count({ where: { updatedAt: { gte: d1 } } }),
    prisma.user.count({ where: { updatedAt: { gte: d7 } } }),
    prisma.user.count({ where: { updatedAt: { gte: d30 } } }),
    prisma.group.count({ where: { status: 'pending' } }),
    prisma.group.count({ where: { status: 'active' } }),
    prisma.group.count({ where: { status: 'completed' } }),
    prisma.wallet.aggregate({ _sum: { balance: true } }),
    prisma.group.findMany({
      where: { status: 'completed' },
      select: { currentCycle: true, maxMembers: true },
    }),
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: {
        status: 'completed',
        type: { in: ['deposit', 'contribution'] },
        createdAt: { gte: d30 },
      },
    }),
    // Revenue proxy: 1.5% of deposit volume
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: { status: 'completed', type: 'deposit', createdAt: { gte: d30 } },
    }),
    prisma.withdrawalRequest.count({ where: { status: 'pending' } }),
    prisma.amlFlag.count({ where: { resolvedAt: null } }),
  ])

  const cycleSuccess =
    completedCyclesRaw.length === 0
      ? 100
      : Math.round(
          (completedCyclesRaw.filter((g) => g.currentCycle >= g.maxMembers).length /
            completedCyclesRaw.length) * 100
        )

  // 30-day volume sparkline (daily totals)
  const sparkRaw = await prisma.transaction.findMany({
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
  for (const t of sparkRaw) {
    const k = t.createdAt.toISOString().slice(0, 10)
    if (k in buckets) buckets[k] += t.amount
  }
  const spark = Object.entries(buckets).map(([date, total]) => ({ date, total }))

  return NextResponse.json({
    users: { total: userCount, dau, wau, mau },
    groups: {
      pending: groupPending,
      active: groupActive,
      completed: groupCompleted,
      cycleSuccessPct: cycleSuccess,
    },
    treasury: {
      tvlUsdt: totalBalance._sum.balance ?? 0,
      pendingWithdrawals,
      openAmlFlags,
    },
    revenue: {
      volume30d: volume30dRaw._sum.amount ?? 0,
      estimatedRevenue30d: (revenue30dRaw._sum.amount ?? 0) * 0.015,
    },
    spark,
  })
}
