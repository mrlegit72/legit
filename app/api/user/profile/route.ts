import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function PATCH(req: Request) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    const { name, phone, country, image } = await req.json()

    const user = await prisma.user.update({
      where: { email: session.user.email },
      data: {
        name: name || undefined,
        phone: phone ?? undefined,
        country: country || undefined,
        image: image ?? undefined,
      },
    })

    return NextResponse.json({ id: user.id })
  } catch (e) {
    console.error('profile update', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
