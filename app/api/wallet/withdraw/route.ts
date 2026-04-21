import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const user = await prisma.user.findUnique({
      where: { email: session.user.email },
      include: { wallet: true },
    })
    if (!user || !user.wallet) {
      return NextResponse.json({ error: 'No wallet' }, { status: 400 })
    }

    const { amount, bankName, accountNumber, accountName } = await req.json()
    const amt = Number(amount)
    if (!amt || amt <= 0) {
      return NextResponse.json({ error: 'Invalid amount' }, { status: 400 })
    }
    if (amt > user.wallet.balance) {
      return NextResponse.json({ error: 'Insufficient balance' }, { status: 400 })
    }
    if (!bankName || !accountNumber || !accountName) {
      return NextResponse.json({ error: 'Missing bank details' }, { status: 400 })
    }

    await prisma.$transaction([
      prisma.wallet.update({
        where: { userId: user.id },
        data: { balance: { decrement: amt } },
      }),
      prisma.transaction.create({
        data: {
          userId: user.id,
          type: 'withdrawal',
          amount: amt,
          currency: 'USDT',
          status: 'pending',
          description: `Withdraw to ${bankName} ****${accountNumber.slice(-4)}`,
        },
      }),
      prisma.notification.create({
        data: {
          userId: user.id,
          title: 'Withdrawal submitted',
          message: `${amt} USDT withdrawal is being processed. You'll receive Naira/Cedi within 10 minutes.`,
        },
      }),
    ])

    return NextResponse.json({ ok: true })
  } catch (e) {
    console.error('withdraw error', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
