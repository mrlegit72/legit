import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin, audit } from '@/lib/admin'
import { invalidateRouterCache } from '@/lib/ramp/router'
import { COUNTRIES } from '@/lib/ramp/countries'

export async function GET() {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const rows = await prisma.countryConfig.findMany()
  const byCode = new Map(rows.map((r) => [r.countryCode, r]))

  // 30-day volume per country
  const since = new Date(Date.now() - 30 * 86400000)
  const volumeRows = await prisma.$queryRawUnsafe<{ country: string; total: number; users: number }[]>(
    `SELECT u.country as country,
            COALESCE(SUM(CASE WHEN t.type IN ('deposit','contribution') AND t.status='completed' THEN t.amount ELSE 0 END), 0) as total,
            COUNT(DISTINCT u.id) as users
     FROM User u
     LEFT JOIN "Transaction" t ON t.userId = u.id AND t.createdAt >= ?
     GROUP BY u.country`,
    since
  ).catch(() => [] as any[])
  const volumeByCountry = new Map<string, { total: number; users: number }>()
  for (const v of volumeRows) {
    volumeByCountry.set(v.country, { total: Number(v.total) || 0, users: Number(v.users) || 0 })
  }

  const countries = Object.values(COUNTRIES).map((c) => {
    const row = byCode.get(c.code)
    // Stats are keyed by the DB's free-text country field, not ISO code.
    const stat = volumeByCountry.get(c.name) || { total: 0, users: 0 }
    return {
      ...c,
      enabled: row?.enabled ?? true,
      preferredProviderId: row?.preferredProviderId ?? null,
      platformFeePct: row?.platformFeePct ?? 0.5,
      volume30d: stat.total,
      users: stat.users,
    }
  })

  return NextResponse.json({ countries })
}

export async function PATCH(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = (await req.json()) as {
    countryCode: string
    enabled?: boolean
    preferredProviderId?: string | null
    platformFeePct?: number
  }
  if (!body.countryCode) {
    return NextResponse.json({ error: 'countryCode required' }, { status: 400 })
  }

  const data: any = { countryCode: body.countryCode }
  if (body.enabled !== undefined) data.enabled = body.enabled
  if (body.preferredProviderId !== undefined) data.preferredProviderId = body.preferredProviderId
  if (body.platformFeePct !== undefined) data.platformFeePct = body.platformFeePct

  await prisma.countryConfig.upsert({
    where: { countryCode: body.countryCode },
    update: data,
    create: data,
  })
  invalidateRouterCache()

  await audit({
    actorId: admin.id,
    action: 'country.update',
    target: `country:${body.countryCode}`,
    details: body,
  })

  return NextResponse.json({ ok: true })
}
