import { NextResponse } from 'next/server'
import { requireAdmin, audit } from '@/lib/admin'
import { listProviders } from '@/lib/ramp/router'

export async function POST(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const providers = await listProviders()
  const provider = providers.find((p) => p.id === params.id)
  if (!provider) return NextResponse.json({ error: 'Unknown provider' }, { status: 404 })

  try {
    const start = Date.now()
    const quote = await provider.quote({
      fromCurrency: provider.supportedCurrencies[0],
      fromAmount: 1,
      country: provider.supportedCountries[0],
    })
    await audit({
      actorId: admin.id,
      action: 'provider.test',
      target: `provider:${params.id}`,
      details: { ok: true, rate: quote.rate, latencyMs: Date.now() - start },
    })
    return NextResponse.json({
      ok: true,
      latencyMs: Date.now() - start,
      sampleQuote: quote,
      isConfigured: provider.isConfigured(),
    })
  } catch (e: any) {
    await audit({
      actorId: admin.id,
      action: 'provider.test',
      target: `provider:${params.id}`,
      details: { ok: false, error: e?.message || 'unknown' },
    })
    return NextResponse.json({ ok: false, error: e?.message || 'Test failed' }, { status: 502 })
  }
}
