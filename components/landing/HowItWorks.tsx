'use client'

import { motion } from 'framer-motion'
import { Users, UserPlus, Wallet, Gift } from 'lucide-react'

const steps = [
  {
    icon: Users,
    title: 'Create a Group',
    desc: 'Set the members, contribution and rotation. Invite link generated instantly.',
  },
  {
    icon: UserPlus,
    title: 'Members Join',
    desc: 'Each member verifies, funds their wallet, and confirms their rotation slot.',
  },
  {
    icon: Wallet,
    title: 'Contribute USDT',
    desc: 'Auto-pull contributions each cycle. All funds sit in verified escrow, not a person.',
  },
  {
    icon: Gift,
    title: 'Receive Your Turn',
    desc: 'When your slot hits, payout is released automatically in stablecoin or local cash-out.',
  },
]

export function HowItWorks() {
  return (
    <section id="how" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-2xl mx-auto"
        >
          <p className="text-sm font-medium text-gold uppercase tracking-widest">How it works</p>
          <h2 className="mt-3 text-3xl sm:text-5xl font-bold tracking-tight">
            From contribution to payout in 4 simple steps
          </h2>
          <p className="mt-4 text-ink-300 text-lg">
            No spreadsheets. No chasing coordinators. Everything runs automatically on-chain.
          </p>
        </motion.div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative card p-6 hover:border-gold/40 transition group"
            >
              <div className="absolute -top-3 -left-3 h-8 w-8 rounded-full bg-gold text-ink-950 font-bold flex items-center justify-center text-sm">
                {i + 1}
              </div>
              <div className="h-12 w-12 rounded-xl bg-gold/10 border border-gold/20 flex items-center justify-center text-gold group-hover:scale-110 transition">
                <s.icon size={22} />
              </div>
              <h3 className="mt-5 font-semibold text-lg text-ink-50">{s.title}</h3>
              <p className="mt-2 text-sm text-ink-300">{s.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
