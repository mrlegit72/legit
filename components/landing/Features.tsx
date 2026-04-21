'use client'

import { motion } from 'framer-motion'
import {
  RefreshCw,
  ShieldCheck,
  Zap,
  Scale,
  MessageSquare,
  Smartphone,
} from 'lucide-react'

const features = [
  {
    icon: RefreshCw,
    title: 'Smart Rotation',
    desc: 'Automated payout schedules. Fair, predictable, and configurable per group.',
  },
  {
    icon: ShieldCheck,
    title: 'Crypto Escrow',
    desc: 'Contributions lock in on-chain escrow — nobody can touch the pot alone.',
  },
  {
    icon: Zap,
    title: 'Instant Cash Out',
    desc: 'Off-ramp USDT to Naira or Cedi straight to your bank in minutes.',
  },
  {
    icon: Scale,
    title: 'Dispute Protection',
    desc: 'Built-in arbitration and transaction replay if anything goes sideways.',
  },
  {
    icon: MessageSquare,
    title: 'Group Chat',
    desc: 'Stay in sync with your group — reminders, receipts, and announcements.',
  },
  {
    icon: Smartphone,
    title: 'Mobile Ready',
    desc: 'Designed for African mobile networks. Works smoothly on 3G.',
  },
]

export function Features() {
  return (
    <section id="features" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-2xl mx-auto"
        >
          <p className="text-sm font-medium text-gold uppercase tracking-widest">Features</p>
          <h2 className="mt-3 text-3xl sm:text-5xl font-bold tracking-tight">
            Built for the way Africa actually saves
          </h2>
        </motion.div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: i * 0.06 }}
              className="group card p-6 hover:border-gold/40 hover:shadow-gold transition"
            >
              <div className="h-11 w-11 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center text-gold group-hover:bg-gold group-hover:text-ink-950 transition">
                <f.icon size={20} />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-ink-50">{f.title}</h3>
              <p className="mt-2 text-sm text-ink-300 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
