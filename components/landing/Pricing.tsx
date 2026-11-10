'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const tiers = [
  {
    name: 'Free',
    price: '₦0',
    period: 'forever',
    desc: 'Perfect for small circles getting started.',
    features: [
      'Up to 5 members per group',
      '1 active group at a time',
      'Basic rotation scheduler',
      'USDT escrow included',
      'Community support',
    ],
    cta: 'Start free',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '₦2,999',
    period: '/month',
    desc: 'For serious groups that save at scale.',
    features: [
      'Up to 20 members per group',
      'Unlimited active groups',
      'Custom rotation orders',
      'Group chat + reminders',
      'Priority cash-out (under 10 min)',
      'Dispute arbitration',
    ],
    cta: 'Go Pro',
    highlighted: true,
  },
  {
    name: 'Business',
    price: '₦7,999',
    period: '/month',
    desc: 'For cooperatives and SACCOs.',
    features: [
      'Unlimited members & groups',
      'Multi-admin roles',
      'CSV exports & reports',
      'Dedicated account manager',
      'Custom branding',
      'API access',
    ],
    cta: 'Talk to sales',
    highlighted: false,
  },
]

export function Pricing() {
  return (
    <section id="pricing" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-2xl mx-auto"
        >
          <p className="text-sm font-medium text-gold uppercase tracking-widest">Pricing</p>
          <h2 className="mt-3 text-3xl sm:text-5xl font-bold tracking-tight">
            Simple pricing. Zero hidden fees.
          </h2>
          <p className="mt-4 text-ink-300 text-lg">
            Start free forever. Upgrade when your group grows.
          </p>
        </motion.div>

        <div className="mt-14 grid gap-6 lg:grid-cols-3">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className={cn(
                'relative rounded-2xl p-7 border',
                t.highlighted
                  ? 'bg-gradient-to-b from-gold/10 to-ink-800 border-gold shadow-gold-lg'
                  : 'bg-ink-800 border-ink-700'
              )}
            >
              {t.highlighted && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gold text-ink-950 text-xs font-bold px-3 py-1">
                  MOST POPULAR
                </span>
              )}
              <h3 className="text-lg font-semibold text-ink-50">{t.name}</h3>
              <p className="mt-1 text-sm text-ink-300">{t.desc}</p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className={cn('text-4xl font-bold', t.highlighted ? 'gold-text' : 'text-ink-50')}>
                  {t.price}
                </span>
                <span className="text-sm text-ink-300">{t.period}</span>
              </div>
              <ul className="mt-6 space-y-3">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-ink-100">
                    <Check size={16} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/auth/register"
                className={cn(
                  'mt-8 w-full',
                  t.highlighted ? 'btn-gold' : 'btn-ghost'
                )}
              >
                {t.cta}
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
