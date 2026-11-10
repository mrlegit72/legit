import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin, audit } from '@/lib/admin'

export async function GET(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  const url = new URL(req.url)
  const status = url.searchParams.get('status') || undefined

  const list = await prisma.withdrawalRequest.findMany({
    where: status ? { status } : {},
    include: { user: { include: { wallet: true, _count: { select: { amlFlags: true } } } } },
    orderBy: { createdAt: 'desc' },
    take: 100,
  })

  return NextResponse.json({
    withdrawals: list.map((w) => ({
      id: w.id,
      userId: w.userId,
      userName: w.user.name,
      userEmail: w.user.email,
      userCountry: w.user.country,
      userBalance: w.user.wallet?.balance ?? 0,
      amlFlagCount: w.user._count.amlFlags,
      amount: w.amount,
      currency: w.currency,
      bankName: w.bankName,
      accountNumber: w.accountNumber,
      accountName: w.accountName,
      status: w.status,
      rejectionReason: w.rejectionReason,
      reviewedAt: w.reviewedAt,
      reviewedById: w.reviewedById,
      createdAt: w.createdAt,
    })),
  })
}

export async function POST(req: Request) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = (await req.json()) as {
    withdrawalId: string
    action: 'approve' | 'reject' | 'complete'
    reason?: string
    externalId?: string
  }
  const w = await prisma.withdrawalRequest.findUnique({
    where: { id: body.withdrawalId },
    include: { user: { include: { wallet: true } } },
  })
  if (!w) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const now = new Date()
  if (body.action === 'approve') {
    // Status: pending -> approved. Balance already decremented when withdrawal
    // was requested (see /api/wallet/withdraw).
    await prisma.withdrawalRequest.update({
      where: { id: w.id },
      data: { status: 'approved', reviewedById: admin.id, reviewedAt: now },
    })
  } else if (body.action === 'reject') {
    // Refund the user's balance.
    await prisma.$transaction([
      prisma.withdrawalRequest.update({
        where: { id: w.id },
        data: {
          status: 'rejected',
          rejectionReason: body.reason || 'Rejected by admin',
          reviewedById: admin.id,
          reviewedAt: now,
        },
      }),
      prisma.wallet.update({
        where: { userId: w.userId },
        data: { balance: { increment: w.amount } },
      }),
      prisma.transaction.create({
        data: {
          userId: w.userId,
          type: 'deposit',
          amount: w.amount,
          currency: w.currency,
          status: 'completed',
          description: `Refund — withdrawal rejected: ${body.reason || 'no reason given'}`,
        },
      }),
      prisma.notification.create({
        data: {
          userId: w.userId,
          title: 'Withdrawal rejected',
          message: `Your withdrawal of ${w.amount} ${w.currency} was declined. Funds returned to wallet.`,
        },
      }),
    ])
  } else if (body.action === 'complete') {
    await prisma.$transaction([
      prisma.withdrawalRequest.update({
        where: { id: w.id },
        data: {
          status: 'completed',
          completedAt: now,
          payoutExternalId: body.externalId || null,
        },
      }),
      prisma.transaction.create({
        data: {
          userId: w.userId,
          type: 'withdrawal',
          amount: w.amount,
          currency: w.currency,
          status: 'completed',
          description: `Paid out to ${w.bankName} ****${w.accountNumber.slice(-4)}`,
        },
      }),
      prisma.notification.create({
        data: {
          userId: w.userId,
          title: 'Withdrawal completed',
          message: `${w.amount} ${w.currency} has been sent to ${w.bankName}.`,
        },
      }),
    ])
  }

  await audit({
    actorId: admin.id,
    action: `withdrawal.${body.action}`,
    target: `withdrawal:${w.id}`,
    details: { amount: w.amount, user: w.userId, reason: body.reason },
  })

  return NextResponse.json({ ok: true })
}
