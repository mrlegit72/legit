import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { pickProvider, countryToString } from '@/lib/ramp'
import type { Country, FiatCurrency } from '@/lib/ramp'

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const user = await prisma.user.findUnique({
      where: { email: session.user.email },
    })
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = (await req.json()) as {
      country?: Country
      currency: FiatCurrency
      amount: number
      redirectUrl?: string
    }
    const country = body.country || countryToString(user.country)
    const amount = Number(body.amount)
    if (!amount || amount <= 0) {
      return NextResponse.json({ error: 'Invalid amount' }, { status: 400 })
    }

    const provider = await pickProvider(country, body.currency)
    const result = await provider.createOnRamp({
      userId: user.id,
      userEmail: user.email,
      userName: user.name,
      country,
      fromCurrency: body.currency,
      fromAmount: amount,
      redirectUrl:
        body.redirectUrl ||
        `${process.env.NEXTAUTH_URL || ''}/dashboard/wallet?status=success`,
    })

    // Persist a pending Charge + Transaction so the wallet history reflects it.
    await prisma.charge.create({
      data: {
        userId: user.id,
        chargeId: result.externalId,
        amount: result.quote.toAmount,
        currency: body.currency,
        status: 'pending',
      },
    })
    await prisma.transaction.create({
      data: {
        userId: user.id,
        type: 'deposit',
        amount: result.quote.toAmount,
        currency: 'USDT',
        status: 'pending',
        description: `${provider.name} on-ramp — ${amount} ${body.currency}`,
        chargeId: result.externalId,
      },
    })

    return NextResponse.json({
      externalId: result.externalId,
      provider: provider.name,
      providerId: provider.id,
      hostedUrl: result.hostedUrl,
      bankInstructions: result.bankInstructions,
      expiresAt: result.expiresAt,
      quote: result.quote,
    })
  } catch (e) {
    console.error('onramp error', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
