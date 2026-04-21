import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { SettingsView } from '@/components/dashboard/SettingsView'

export default async function SettingsPage() {
  const session = await getServerSession(authOptions)
  const user = await prisma.user.findUnique({
    where: { email: session!.user!.email! },
  })
  if (!user) return null

  return (
    <SettingsView
      user={{
        name: user.name,
        email: user.email,
        phone: user.phone,
        country: user.country,
        image: user.image,
      }}
    />
  )
}
