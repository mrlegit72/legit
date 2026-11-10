import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin, audit } from '@/lib/admin'

const DEFAULT_SETTINGS = {
  'platform.feePct': '0.5',
  'groups.minMembers': '5',
  'groups.maxMembers': '50',
  'groups.minContributionUsdt': '1',
  'groups.maxContributionUsdt': '10000',
  'groups.frequencies': 'weekly,monthly',
  'groups.defaultRotation': 'rotation',
  'disputes.escalationWindowHours': '24',
  'withdrawals.manualReviewThresholdUsdt': '500',
  'features.multiAdminGroups': 'off',
  'features.inAppChat': 'off',
  'features.smartContractEscrow': 'off',
  'sms.senderId': 'AJOVAULT',
  'email.fromAddress': 'alerts@ajovault.com',
}

export async function GET() {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const rows = await prisma.setting.findMany()
  const overrides = Object.fromEntries(rows.map((r) => [r.key, r.value]))
  const merged: Record<string, string> = { ...DEFAULT_SETTINGS, ...overrides }
  return NextResponse.json({ settings: merged })
}

export async function PATCH(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = (await req.json()) as { settings: Record<string, string> }
  if (!body?.settings) {
    return NextResponse.json({ error: 'settings required' }, { status: 400 })
  }

  const changed: string[] = []
  for (const [key, value] of Object.entries(body.settings)) {
    const strValue = String(value)
    const existing = await prisma.setting.findUnique({ where: { key } })
    if (existing?.value !== strValue) {
      await prisma.setting.upsert({
        where: { key },
        update: { value: strValue },
        create: { key, value: strValue },
      })
      changed.push(key)
    }
  }

  if (changed.length) {
    await audit({
      actorId: admin.id,
      action: 'settings.update',
      target: 'platform',
      details: { changed, values: Object.fromEntries(changed.map((k) => [k, body.settings[k]])) },
    })
  }

  return NextResponse.json({ ok: true, changed })
}
