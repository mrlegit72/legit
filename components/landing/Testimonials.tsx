'use client'

import { motion } from 'framer-motion'
import Image from 'next/image'
import { Star } from 'lucide-react'

const testimonials = [
  {
    name: 'Adaeze Okafor',
    role: 'Market trader, Lagos',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Adaeze',
    quote:
      'I used to lose sleep hoping our coordinator would show up. With AjoVault, I can see every contribution and the pot is untouchable. My group moved fully onto it last year.',
  },
  {
    name: 'Kwame Mensah',
    role: 'Contractor, Accra',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Kwame',
    quote:
      'We completed a full 8-month susu with members across 3 cities. Payout hit my bank 4 minutes after the cycle ended. This is how savings should work.',
  },
  {
    name: 'Fatima Abubakar',
    role: 'Founder, Kano',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Fatima',
    quote:
      'Finally a product that respects how we save. The crypto part was scary at first, but the USDT stays steady and the cash-out to Naira is seamless.',
  },
]

export function Testimonials() {
  return (
    <section className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-2xl mx-auto"
        >
          <p className="text-sm font-medium text-gold uppercase tracking-widest">
            Loved across Africa
          </p>
          <h2 className="mt-3 text-3xl sm:text-5xl font-bold tracking-tight">
            Real groups. Real payouts.
          </h2>
        </motion.div>

        <div className="mt-14 grid gap-6 lg:grid-cols-3">
          {testimonials.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="card p-6 flex flex-col"
            >
              <div className="flex text-gold gap-0.5 mb-4">
                {[...Array(5)].map((_, idx) => (
                  <Star key={idx} size={16} fill="currentColor" />
                ))}
              </div>
              <p className="text-ink-100 leading-relaxed">&ldquo;{t.quote}&rdquo;</p>
              <div className="mt-6 pt-6 border-t border-ink-700 flex items-center gap-3">
                <Image
                  src={t.avatar}
                  alt={t.name}
                  width={44}
                  height={44}
                  className="rounded-full bg-ink-700"
                  unoptimized
                />
                <div>
                  <p className="font-semibold text-ink-50">{t.name}</p>
                  <p className="text-xs text-ink-300">{t.role}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
