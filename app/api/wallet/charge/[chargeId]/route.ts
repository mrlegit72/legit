import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { getCharge, hasCoinbaseConfigured } from '@/lib/coinbase'

export async function GET(
  _req: Request,
  { params }: { params: { chargeId: string } }
) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const user = await prisma.user.findUnique({
      where: { email: session.user.email },
      include: { wallet: true },
    })
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const chargeRecord = await prisma.charge.findUnique({
      where: { chargeId: params.chargeId },
    })
    if (!chargeRecord || chargeRecord.userId !== user.id) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 })
    }

    let latestStatus = chargeRecord.status.toUpperCase()
    let eventName = latestStatus

    if (hasCoinbaseConfigured()) {
      try {
        const data = await getCharge(params.chargeId)
        const timeline = data.timeline || []
        const last = timeline[timeline.length - 1]
        eventName = (last?.status || 'NEW').toUpperCase()
        latestStatus = eventName
      } catch (e) {
        console.error('getCharge failed', e)
      }
    } else if (chargeRecord.status === 'pending') {
      // Demo auto-confirm after 30 seconds so the UI flow can be demoed end-to-end.
      const ageMs = Date.now() - chargeRecord.createdAt.getTime()
      if (ageMs > 30000) {
        latestStatus = 'CONFIRMED'
        eventName = 'CONFIRMED'
      } else {
        latestStatus = 'PENDING'
        eventName = 'PENDING'
      }
    }

    if (
      (eventName === 'CONFIRMED' || eventName === 'COMPLETED' || eventName === 'RESOLVED') &&
      chargeRecord.status !== 'confirmed'
    ) {
      await prisma.$transaction([
        prisma.charge.update({
          where: { id: chargeRecord.id },
          data: { status: 'confirmed' },
        }),
        prisma.wallet.update({
          where: { userId: user.id },
          data: { balance: { increment: chargeRecord.amount } },
        }),
        prisma.transaction.updateMany({
          where: { chargeId: params.chargeId, userId: user.id },
          data: { status: 'completed' },
        }),
        prisma.notification.create({
          data: {
            userId: user.id,
            title: 'Deposit confirmed',
            message: `${chargeRecord.amount} USDT credited to your wallet.`,
          },
        }),
      ])
    } else if (eventName === 'FAILED' && chargeRecord.status !== 'failed') {
      await prisma.charge.update({
        where: { id: chargeRecord.id },
        data: { status: 'failed' },
      })
      await prisma.transaction.updateMany({
        where: { chargeId: params.chargeId, userId: user.id },
        data: { status: 'failed' },
      })
    } else if (eventName === 'EXPIRED' && chargeRecord.status !== 'expired') {
      await prisma.charge.update({
        where: { id: chargeRecord.id },
        data: { status: 'expired' },
      })
      await prisma.transaction.updateMany({
        where: { chargeId: params.chargeId, userId: user.id },
        data: { status: 'failed' },
      })
    }

    return NextResponse.json({
      chargeId: params.chargeId,
      status: latestStatus,
    })
  } catch (e) {
    console.error('charge status error', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
