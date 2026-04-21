import { NextResponse } from 'next/server'
import bcrypt from 'bcryptjs'
import { prisma } from '@/lib/prisma'

export async function POST(req: Request) {
  try {
    const { name, email, phone, password, country } = await req.json()

    if (!name || !email || !password) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 })
    }
    if (password.length < 6) {
      return NextResponse.json({ error: 'Password must be at least 6 characters' }, { status: 400 })
    }

    const normalized = email.toLowerCase().trim()
    const existing = await prisma.user.findUnique({ where: { email: normalized } })
    if (existing) {
      return NextResponse.json({ error: 'Email already in use' }, { status: 409 })
    }

    const hashed = await bcrypt.hash(password, 10)
    const user = await prisma.user.create({
      data: {
        name,
        email: normalized,
        phone,
        country: country || 'Nigeria',
        password: hashed,
        image: `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(name)}`,
        wallet: { create: { balance: 0 } },
        notifications: {
          create: {
            title: 'Welcome to AjoVault',
            message: 'Your wallet is ready. Start saving today.',
          },
        },
      },
    })

    return NextResponse.json({ id: user.id, email: user.email })
  } catch (e: any) {
    console.error('register error', e)
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}
