import { getServerSession } from 'next-auth'
import { headers } from 'next/headers'
import { authOptions } from './auth'
import { prisma } from './prisma'

/**
 * Enforce admin access. Returns the admin user, or null if the caller is not admin
 * (or not signed in, or frozen).
 */
export async function requireAdmin() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) return null
  const user = await prisma.user.findUnique({
    where: { email: session.user.email },
  })
  if (!user || user.role !== 'admin' || user.status !== 'active') return null
  return user
}

/**
 * Append an entry to the audit log. Fail-open: a logging error never breaks
 * the actual admin action.
 */
export async function audit(params: {
  actorId?: string | null
  action: string
  target?: string
  details?: Record<string, unknown> | string
}) {
  try {
    let ip: string | null = null
    let userAgent: string | null = null
    try {
      const h = headers()
      ip = h.get('x-forwarded-for') || h.get('x-real-ip')
      userAgent = h.get('user-agent')
    } catch {
      /* headers() unavailable outside a request */
    }
    await prisma.auditLog.create({
      data: {
        actorId: params.actorId || null,
        action: params.action,
        target: params.target,
        details:
          typeof params.details === 'string'
            ? params.details
            : params.details
              ? JSON.stringify(params.details)
              : null,
        ip: ip || null,
        userAgent: userAgent || null,
      },
    })
  } catch (e) {
    console.error('[audit] failed:', e)
  }
}
