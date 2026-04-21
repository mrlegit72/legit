import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { TransactionsView } from '@/components/dashboard/TransactionsView'

export default async function TransactionsPage() {
  const session = await getServerSession(authOptions)
  const user = await prisma.user.findUnique({
    where: { email: session!.user!.email! },
    include: {
      transactions: { orderBy: { createdAt: 'desc' } },
    },
  })
  if (!user) return null

  const plain = user.transactions.map((t) => ({
    id: t.id,
    type: t.type,
    amount: t.amount,
    currency: t.currency,
    status: t.status,
    description: t.description,
    createdAt: t.createdAt.toISOString(),
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Transactions</h1>
        <p className="mt-1 text-ink-300">
          Every deposit, contribution, payout, and withdrawal on your account.
        </p>
      </div>
      <TransactionsView transactions={plain} />
    </div>
  )
}
