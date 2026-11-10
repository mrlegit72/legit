import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { createCharge, hasCoinbaseConfigured } from '@/lib/coinbase'

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const user = await prisma.user.findUnique({ where: { email: session.user.email } })
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const { amount, currency, description } = await req.json()
    const amt = Number(amount)
    if (!amt || amt <= 0) {
      return NextResponse.json({ error: 'Invalid amount' }, { status: 400 })
    }

    let chargeData: any

    if (hasCoinbaseConfigured()) {
      chargeData = await createCharge({
        userId: user.id,
        amount: String(amt),
        currency: currency || 'USD',
        description: description || 'AjoVault wallet deposit',
      })
    } else {
      // Demo-mode charge so the UI flow is fully testable without a Coinbase key.
      const now = Date.now()
      chargeData = {
        id: `demo-${now}`,
        code: `DEMO${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
        hosted_url: '#',
        expires_at: new Date(now + 60 * 60 * 1000).toISOString(),
        addresses: {
          bitcoin: 'bc1qdemoajovaultbtcaddressxxxxxxxxxxxxxxxxxx',
          ethereum: '0xDemoAjoVaultETHAddress0000000000000000000',
          usdt: '0xDemoAjoVaultUSDTAddress000000000000000000',
          usdc: '0xDemoAjoVaultUSDCAddress000000000000000000',
        },
        pricing: {
          local: { amount: String(amt), currency: currency || 'USD' },
          usdt: { amount: String(amt), currency: 'USDT' },
        },
      }
    }

    await prisma.charge.create({
      data: {
        userId: user.id,
        chargeId: chargeData.id,
        amount: amt,
        currency: currency || 'USD',
        status: 'pending',
      },
    })

    await prisma.transaction.create({
      data: {
        userId: user.id,
        type: 'deposit',
        amount: amt,
        currency: currency || 'USDT',
        status: 'pending',
        description: description || 'Coinbase Commerce deposit',
        chargeId: chargeData.id,
      },
    })

    return NextResponse.json({
      chargeId: chargeData.id,
      hostedUrl: chargeData.hosted_url,
      addresses: chargeData.addresses || {},
      pricing: chargeData.pricing || {},
      expiresAt: chargeData.expires_at,
    })
  } catch (e: any) {
    console.error('deposit error', e?.response?.data || e)
    return NextResponse.json({ error: 'Failed to create charge' }, { status: 500 })
  }
}
