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
    const user = await prisma.user.findUnique({ where: { email: session.user.email } })
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const body = await req.json()
    const {
      name,
      description,
      maxMembers,
      contributionAmount,
      frequency,
      startDate,
      payoutOrder,
    } = body

    if (!name || !maxMembers || !contributionAmount || !frequency || !startDate) {
      return NextResponse.json({ error: 'Missing fields' }, { status: 400 })
    }

    const group = await prisma.group.create({
      data: {
        name,
        description: description || null,
        maxMembers: Number(maxMembers),
        contributionAmount: Number(contributionAmount),
        frequency,
        startDate: new Date(startDate),
        payoutOrder: payoutOrder || 'rotation',
        status: 'pending',
        members: {
          create: { userId: user.id, position: 1 },
        },
      },
    })

    await prisma.notification.create({
      data: {
        userId: user.id,
        title: 'Group created',
        message: `Your group "${group.name}" is live. Share the invite link to get members.`,
      },
    })

    return NextResponse.json({ id: group.id })
  } catch (e) {
    console.error('create group', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
