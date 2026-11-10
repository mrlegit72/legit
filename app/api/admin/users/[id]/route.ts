import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { requireAdmin, audit } from '@/lib/admin'

export async function PATCH(
  req: Request,
  { params }: { params: { id: string } }
) {
  const admin = await requireAdmin()
  if (!admin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = (await req.json()) as {
    role?: 'user' | 'admin'
    status?: 'active' | 'frozen'
    kycStatus?: 'unverified' | 'pending' | 'verified' | 'rejected'
  }

  const before = await prisma.user.findUnique({ where: { id: params.id } })
  if (!before) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  // Guardrails: an admin can't demote themselves (prevent lockout).
  if (admin.id === params.id && body.role === 'user') {
    return NextResponse.json({ error: "Can't demote yourself" }, { status: 400 })
  }

  const data: any = {}
  if (body.role) data.role = body.role
  if (body.status) data.status = body.status
  if (body.kycStatus) data.kycStatus = body.kycStatus

  await prisma.user.update({ where: { id: params.id }, data })

  const changedFields = Object.keys(data)
  for (const field of changedFields) {
    await audit({
      actorId: admin.id,
      action: `user.${field}`,
      target: `user:${params.id}`,
      details: { from: (before as any)[field], to: (data as any)[field] },
    })
  }

  return NextResponse.json({ ok: true })
}
