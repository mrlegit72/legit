import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { verifyWebhookSignature } from '@/lib/coinbase'

export async function POST(req: Request) {
  try {
    const raw = await req.text()
    const signature = req.headers.get('x-cc-webhook-signature') || ''
    const secret = process.env.COINBASE_COMMERCE_WEBHOOK_SECRET || ''

    if (secret) {
      const ok = verifyWebhookSignature(raw, signature, secret)
      if (!ok) {
        return NextResponse.json({ error: 'Invalid signature' }, { status: 401 })
      }
    }

    const payload = JSON.parse(raw)
    const event = payload?.event
    const type: string = event?.type || ''
    const charge = event?.data
    const chargeId: string = charge?.id

    if (!chargeId) return NextResponse.json({ ok: true })

    const record = await prisma.charge.findUnique({ where: { chargeId } })
    if (!record) return NextResponse.json({ ok: true })

    if (type === 'charge:confirmed') {
      if (record.status !== 'confirmed') {
        await prisma.$transaction([
          prisma.charge.update({
            where: { id: record.id },
            data: { status: 'confirmed' },
          }),
          prisma.wallet.update({
            where: { userId: record.userId },
            data: { balance: { increment: record.amount } },
          }),
          prisma.transaction.updateMany({
            where: { chargeId, userId: record.userId },
            data: { status: 'completed' },
          }),
          prisma.notification.create({
            data: {
              userId: record.userId,
              title: 'Deposit confirmed',
              message: `${record.amount} USDT credited to your wallet via Coinbase Commerce.`,
            },
          }),
        ])
      }
    } else if (type === 'charge:failed') {
      await prisma.charge.update({
        where: { id: record.id },
        data: { status: 'failed' },
      })
      await prisma.transaction.updateMany({
        where: { chargeId, userId: record.userId },
        data: { status: 'failed' },
      })
    } else if (type === 'charge:delayed' || type === 'charge:expired') {
      await prisma.charge.update({
        where: { id: record.id },
        data: { status: 'expired' },
      })
      await prisma.transaction.updateMany({
        where: { chargeId, userId: record.userId },
        data: { status: 'failed' },
      })
    }

    return NextResponse.json({ ok: true })
  } catch (e) {
    console.error('webhook error', e)
    return NextResponse.json({ ok: true })
  }
}
