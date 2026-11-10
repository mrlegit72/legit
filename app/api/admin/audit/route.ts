import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin } from '@/lib/admin'

export async function GET(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const url = new URL(req.url)
  const q = (url.searchParams.get('q') || '').trim()
  const limit = Math.min(200, Number(url.searchParams.get('limit')) || 100)

  const logs = await prisma.auditLog.findMany({
    where: q
      ? {
          OR: [
            { action: { contains: q } },
            { target: { contains: q } },
            { details: { contains: q } },
          ],
        }
      : {},
    include: { actor: { select: { name: true, email: true } } },
    orderBy: { createdAt: 'desc' },
    take: limit,
  })

  return NextResponse.json({
    entries: logs.map((l) => ({
      id: l.id,
      action: l.action,
      target: l.target,
      details: l.details,
      actorName: l.actor?.name || 'System',
      actorEmail: l.actor?.email || null,
      ip: l.ip,
      userAgent: l.userAgent,
      createdAt: l.createdAt,
    })),
  })
}
