import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin, audit } from '@/lib/admin'
import { encrypt, maskSecret, decrypt } from '@/lib/crypto'
import { describeProviders, invalidateRouterCache } from '@/lib/ramp/router'

export async function GET() {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const providers = await describeProviders()
  // For each provider, also fetch the masked API key preview from the DB.
  const rows = await prisma.providerConfig.findMany()
  const byId = new Map(rows.map((r) => [r.providerId, r]))
  return NextResponse.json({
    providers: providers.map((p) => {
      const row = byId.get(p.id)
      return {
        ...p,
        apiKeyMask: row?.apiKey ? maskSecret(decrypt(row.apiKey)) : null,
        webhookSecretMask: row?.webhookSecret ? maskSecret(decrypt(row.webhookSecret)) : null,
        notes: row?.notes || null,
        updatedAt: row?.updatedAt || null,
      }
    }),
  })
}

export async function PATCH(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = (await req.json()) as {
    providerId: string
    name?: string
    enabled?: boolean
    apiKey?: string | null // null = clear
    webhookSecret?: string | null
    feeOverridePct?: number | null
    priority?: number
    notes?: string | null
  }
  if (!body.providerId) {
    return NextResponse.json({ error: 'providerId required' }, { status: 400 })
  }

  const existing = await prisma.providerConfig.findUnique({
    where: { providerId: body.providerId },
  })

  const data: any = {
    providerId: body.providerId,
    name: body.name ?? existing?.name ?? body.providerId,
  }
  if (body.enabled !== undefined) data.enabled = body.enabled
  if (body.priority !== undefined) data.priority = body.priority
  if (body.feeOverridePct !== undefined) data.feeOverridePct = body.feeOverridePct
  if (body.notes !== undefined) data.notes = body.notes
  if (body.apiKey !== undefined) {
    data.apiKey = body.apiKey ? encrypt(body.apiKey) : null
  }
  if (body.webhookSecret !== undefined) {
    data.webhookSecret = body.webhookSecret ? encrypt(body.webhookSecret) : null
  }

  const row = await prisma.providerConfig.upsert({
    where: { providerId: body.providerId },
    update: data,
    create: data,
  })

  invalidateRouterCache()

  await audit({
    actorId: admin.id,
    action: 'provider.update',
    target: `provider:${body.providerId}`,
    details: {
      changedKeys: Object.keys(body).filter((k) => k !== 'providerId' && (body as any)[k] !== undefined),
      enabled: row.enabled,
      priority: row.priority,
    },
  })

  return NextResponse.json({ ok: true })
}
