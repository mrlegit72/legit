import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { WalletView } from '@/components/dashboard/WalletView'
import { hasCoinbaseConfigured } from '@/lib/coinbase'

export default async function WalletPage() {
  const session = await getServerSession(authOptions)
  const user = await prisma.user.findUnique({
    where: { email: session!.user!.email! },
    include: {
      wallet: true,
      transactions: { orderBy: { createdAt: 'desc' }, take: 30 },
    },
  })
  if (!user) return null

  const txs = user.transactions.map((t) => ({
    id: t.id,
    type: t.type,
    amount: t.amount,
    currency: t.currency,
    status: t.status,
    description: t.description,
    createdAt: t.createdAt.toISOString(),
  }))

  return (
    <WalletView
      balance={user.wallet?.balance ?? 0}
      transactions={txs}
      coinbaseConfigured={hasCoinbaseConfigured()}
    />
  )
}
