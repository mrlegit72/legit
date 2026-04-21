import { redirect } from 'next/navigation'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { DashboardShell } from '@/components/dashboard/DashboardShell'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.email) {
    redirect('/auth/login')
  }

  const user = await prisma.user.findUnique({
    where: { email: session.user.email },
    include: { wallet: true },
  })

  if (!user) redirect('/auth/login')

  const notifications = await prisma.notification.findMany({
    where: { userId: user.id, read: false },
    orderBy: { createdAt: 'desc' },
    take: 5,
  })

  return (
    <DashboardShell
      user={{
        id: user.id,
        name: user.name,
        email: user.email,
        image: user.image,
        balance: user.wallet?.balance ?? 0,
      }}
      unreadNotifications={notifications}
    >
      {children}
    </DashboardShell>
  )
}
