import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin } from '@/lib/admin'

export async function GET(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const url = new URL(req.url)
  const q = (url.searchParams.get('q') || '').trim()
  const limit = Math.min(100, Number(url.searchParams.get('limit')) || 50)

  const users = await prisma.user.findMany({
    where: q
      ? {
          OR: [
            { email: { contains: q } },
            { name: { contains: q } },
            { phone: { contains: q } },
          ],
        }
      : {},
    include: { wallet: true, groups: true, _count: { select: { amlFlags: true } } },
    orderBy: { createdAt: 'desc' },
    take: limit,
  })

  return NextResponse.json({
    users: users.map((u) => ({
      id: u.id,
      name: u.name,
      email: u.email,
      phone: u.phone,
      country: u.country,
      image: u.image,
      role: u.role,
      status: u.status,
      kycStatus: u.kycStatus,
      twoFAEnabled: u.twoFAEnabled,
      balance: u.wallet?.balance ?? 0,
      groupCount: u.groups.length,
      amlFlagCount: u._count.amlFlags,
      createdAt: u.createdAt,
    })),
  })
}
