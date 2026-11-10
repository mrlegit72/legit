import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin } from '@/lib/admin'

export async function GET(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const url = new URL(req.url)
  const status = url.searchParams.get('status') || undefined

  const groups = await prisma.group.findMany({
    where: status ? { status } : {},
    include: { members: { include: { user: { select: { name: true, country: true } } } } },
    orderBy: { createdAt: 'desc' },
    take: 100,
  })
  return NextResponse.json({
    groups: groups.map((g) => ({
      id: g.id,
      name: g.name,
      status: g.status,
      contributionAmount: g.contributionAmount,
      maxMembers: g.maxMembers,
      memberCount: g.members.length,
      currentCycle: g.currentCycle,
      frequency: g.frequency,
      startDate: g.startDate,
      createdAt: g.createdAt,
      topCountry: g.members[0]?.user.country || null,
    })),
  })
}
