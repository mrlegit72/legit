import { prisma } from '@/lib/prisma'
import { ShieldCheck, Wallet, AlertTriangle, ExternalLink } from 'lucide-react'
import { StatCard } from '@/components/dashboard/StatCard'
import { formatUSDT } from '@/lib/utils'

export const dynamic = 'force-dynamic'

export default async function AdminTreasuryPage() {
  const [walletAgg, pendingWd, completedWd, depAgg, payoutAgg] = await Promise.all([
    prisma.wallet.aggregate({ _sum: { balance: true } }),
    prisma.withdrawalRequest.aggregate({
      _sum: { amount: true },
      where: { status: 'pending' },
    }),
    prisma.withdrawalRequest.aggregate({
      _sum: { amount: true },
      where: { status: 'completed' },
    }),
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: { status: 'completed', type: 'deposit' },
    }),
    prisma.transaction.aggregate({
      _sum: { amount: true },
      where: { status: 'completed', type: 'payout' },
    }),
  ])

  const tvl = walletAgg._sum.balance ?? 0
  const pending = pendingWd._sum.amount ?? 0
  const completed = completedWd._sum.amount ?? 0
  const deposits = depAgg._sum.amount ?? 0
  const payouts = payoutAgg._sum.amount ?? 0
  const reconciled = Math.abs(deposits - payouts - tvl - completed)

  const treasuryAddress = process.env.AJOVAULT_TREASURY_ADDRESS || '0xTreasuryAddressNotSet'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-ink-50">Treasury</h1>
        <p className="mt-1 text-ink-300">
          On-chain balance + reconciliation. Lifetime deposits should equal payouts + TVL +
          completed withdrawals (within fee drift).
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={ShieldCheck} label="TVL (sum of wallets)" value={`${formatUSDT(tvl)} USDT`} hint="Should match on-chain balance" />
        <StatCard icon={Wallet} label="Pending withdrawals" value={`${formatUSDT(pending)} USDT`} hint="Debited, awaiting payout" />
        <StatCard icon={Wallet} label="Lifetime deposits" value={`${formatUSDT(deposits)} USDT`} />
        <StatCard
          icon={reconciled < 1 ? ShieldCheck : AlertTriangle}
          label="Reconciliation drift"
          value={`${formatUSDT(reconciled)} USDT`}
          hint={reconciled < 1 ? '✅ matches' : 'Investigate'}
        />
      </div>

      <div className="card p-6 space-y-4">
        <h3 className="font-semibold text-ink-50">Treasury wallet</h3>
        <div className="rounded-xl border border-ink-700 bg-ink-900 p-4 space-y-2">
          <p className="text-xs text-ink-400">Address (AJOVAULT_TREASURY_ADDRESS)</p>
          <p className="font-mono text-sm text-ink-100 break-all">{treasuryAddress}</p>
          <a
            href={`https://polygonscan.com/address/${treasuryAddress}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-gold hover:underline mt-2"
          >
            View on Polygonscan <ExternalLink size={12} />
          </a>
        </div>

        <div className="rounded-xl border border-gold/20 bg-gold/5 p-4 text-sm text-ink-200">
          <p className="font-medium text-ink-50 mb-2">Next steps for real escrow</p>
          <ol className="list-decimal pl-5 space-y-1 text-ink-300">
            <li>Deploy an AjoEscrow smart contract on Polygon (OpenZeppelin TimelockController base).</li>
            <li>Replace this treasury EOA with the contract address.</li>
            <li>Route group deposits directly into the contract, with per-cycle release rules.</li>
            <li>Publish the contract on Polygonscan and link the audit here.</li>
            <li>Buy ~$500/mo of Nexus Mutual cover to display insurance badge on the landing page.</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
