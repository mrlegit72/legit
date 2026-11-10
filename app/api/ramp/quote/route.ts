import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { getBestQuote, pickProvider } from '@/lib/ramp'
import type { Country, FiatCurrency } from '@/lib/ramp'

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const { country, currency, amount } = (await req.json()) as {
      country: Country
      currency: FiatCurrency
      amount: number
    }
    if (!country || !currency || !amount || amount <= 0) {
      return NextResponse.json({ error: 'Invalid params' }, { status: 400 })
    }

    const provider = await pickProvider(country, currency)
    const quote = await getBestQuote({ country, currency, amount })

    return NextResponse.json({
      quote,
      provider: {
        id: provider.id,
        name: provider.name,
        isConfigured: provider.isConfigured(),
        paymentMethods: provider.paymentMethods,
      },
    })
  } catch (e) {
    console.error('quote error', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
